from abc import ABCMeta, abstractmethod
from collections.abc import Callable, Mapping, MutableMapping

from findig.dataset import MutableDataSet, MutableRecord


class AbstractDataModel(Mapping, metaclass=ABCMeta):
    """
    An object responsible for managing the data for a specific resource.
    Essentially, it is a mapping of data operations to the functions
    that perform.

    The following data operations and their signatures are supported:

    :read(): Retrieve the data for the resource.
    :write(new_data): Replace a resource's data completely with the new
                      data given. Further, if the resource doesn't yet
                      exist, create it.
    :delete(): Completely obliterate a resource's data; in general the
               resource should be thought to no longer exist after this
               occurs.
    :make(data)->dict_of_ids: Create a child resource of this
                              resource and return its identifying
                              data.

    To implement this abstract base class, do *either* of the following:

    * Implement methods on your subclass with the names 
      of the data operations you want your model to support. For example,
      the following model implements read and write actions::

        class ReadWriteModel(AbstractDataModel):
            def read():
                '''Perform backend read.'''

            def write(new_data):
                '''Perform backend write.'''

    * Re-implement the mapping interface on your subclasses, such that
      instances will map from a data operation (str) to a function that
      implements it. This requires implementing ``__iter__``, 
      ``__len__`` and ``__getitem__`` at a minimum. For an example,
      take a look at the source code for this class.
    """

    all_actions = ('read', 'write', 'delete', 'make')

    def compose(self, other):
        if isinstance(other, Mapping):
            composite = dict(other)
            composite.update(self)
            return DictDataModel(composite)
        else:
            return DictDataModel(self)

    def __get_impl_actions(self):
        return {action: func 
                for action, func in
                ((a, getattr(self, a, None)) for a in self.all_actions) 
                if isinstance(func, Callable)}

    def __iter__(self):
        yield from self.__get_impl_actions()

    def __len__(self):
        return len(self.__get_impl_actions())

    def __getitem__(self, k):
        return self.__get_impl_actions()[k]


class DictDataModel(dict, AbstractDataModel):
    def __init__(self, mapping):
        self.update(mapping)


class DataModel(AbstractDataModel, MutableMapping):
    """
    A generic, concrete implementation of :class:AbstractDataModel

    This class is implemented as a mutable mapping, so implementation
    functions for data operations can be set, accessed and deleted
    using the mapping interface::

        >>> dm = DataModel()
        >>> dm['read'] = lambda: ()
        >>> 'read' in dm
        True

    Also, be aware that data model instances can be called to return
    a decorator for a specific data operation::

        >>> @dm('write')
        ... def write_some_data(data):
        ...    pass
        ...
        >>> dm['write'] == write_some_data
        True

    """
    def __init__(self):
        self.registry = {}

    def __setitem__(self, action, func):
        if action not in self.all_actions:
            raise ValueError("Unsupported action: {}".format(action))

        elif not isinstance(func, Callable):
            raise TypeError("Item must be callable.")

        else:
            setattr(self, action, func)

    def __delitem__(self, action):
        if action not in self.all_actions:
            raise ValueError("Unsupported action: {}".format(action))

        elif not hasattr(self, action):
            raise KeyError(action)

        else:
            delattr(self, action)

    def __call__(self, action):
        def decorator(func):
            self[action] = func
            return func
        
        return decorator

class DataSetDataModel(AbstractDataModel):
    def __init__(self, dataset):
        self.ds = dataset

    def __iter__(self):
        yield 'read'

        if isinstance(self.ds, MutableDataSet):
            yield 'make'

        if isinstance(self.ds, MutableRecord):
            yield 'write'
            yield 'delete'

    def __len__(self):
        length = 1
        if isinstance(self.ds, MutableDataSet):
            length += 1
        if isinstance(self.ds, MutableRecord):
            length += 2
        return length

    def __getitem__(self, action):
        if action == 'read':
            return lambda: self.ds
        elif action == 'make':
            return self.ds.add
        elif action == 'write':
            return lambda data: self.ds.patch(data, (), replace=True)
        elif action == 'delete':
            return self.ds.delete


__all__ = ['AbstractDataModel', 'DictDataModel', 'DataModel']