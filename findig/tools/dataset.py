from abc import ABCMeta, abstractmethod
from collections.abc import Callable, Iterable, Mapping, MutableMapping
from contextlib import contextmanager
from itertools import islice

from werkzeug.utils import cached_property

from findig.context import ctx
from findig.utils import extremum


class AbstractDataSet(Iterable, metaclass=ABCMeta):
    """
    An abstract data set is a representation of a collection of items.

    Concrete implementations must provide *at least* an implementation
    for ``__iter__``, which should return an iterator of
    :class:`AbstractRecord` instances.

    """

    def __str__(self):
        return "[{}]".format(
            ", ".join(str(item) for item in self)
        )

    def fetch(self, **search_spec):
        """
        Fetch an :class:`AbstractRecord` matching the search specification.

        If this is called outside a request, a lazy record is returned
        immediately (i.e., the backend isn't hit until the record is
        explicitly queried).
        """
        allowed_methods = ('get', 'head')

        if hasattr(ctx, 'request') \
                and ctx.request.method.lower() in allowed_methods:
            # We're inside a GET request, so we can immediately grab a
            # record and return it
            return self.fetch_now(**search_spec)

        else:
            # We're not inside a request; we don't wan't to hit the
            # database searching for the record unless the record is
            # explicitly accessed.
            cls = LazyMutableRecord \
                if isinstance(self, MutableDataSet) \
                else LazyRecord
            return cls(lambda: self.fetch_now(**search_spec))

    def fetch_now(self, **search_spec):
        """
        Fetch an :class:`AbstractRecord` matching the search specification.

        Unlike :meth:`fetch`, this function will always hit the backend.
        """
        for record in self:
            if FilteredDataSet.check_match(record, search_spec):
                return record
        else:
            raise LookupError("No matching item found.")

    def filtered(self, **search_spec):
        """
        Return a filtered view of this data set.

        Each keyword represents the name of a field that is checked, and
        the corresponding argument indicates what it is checked against. If
        the argument is :class:`~collections.abc.Callable`, then it should
        be a predicate that returns ``True`` if the field is valid (be aware
        that the predicate will passed be ``None`` if the field isn't
        present on the record), otherwise it is compared against the field
        for equality.
        """
        return FilteredDataSet(self, **search_spec)

    def limit(self, count, offset=0):
        """
        Return a limited version of this data set.

        :param offset: The number of items to skip from the beginning
        :param count: The maximum number of items to return

        """
        return DataSetSlice(self, offset, offset+count)

    def sorted(self, *sort_spec, descending=False):
        """
        Return a sorted view of this data set.

        The method takes a variable number of arguments that specify its
        sort specification.

        If a single, callable argument is provided, it is taken as a
        sort key for a record.

        Otherwise, the arguments are taken as field names to be sorted,
        in the same order given in the argument list. Records that omit
        one of these fields appear later in the sorted set than
        those that don't.

        """
        return OrderedDataSet(self, *sort_spec, descending=descending)


class MutableDataSet(AbstractDataSet, metaclass=ABCMeta):
    """
    An abstract data set that can add new child elements.
    """

    @abstractmethod
    def add(self, data):
        """Add a new child item to the data set."""


class AbstractRecord(Mapping, metaclass=ABCMeta):
    """
    An representation of an item belonging to a collection.
    """
    def __iter__(self):
        yield from self.cached_data

    def __len__(self):
        return len(self.cached_data)

    def __getitem__(self, key):
        return self.cached_data[key]

    def __str__(self):
        return "{{{}}}".format(
            ", ".join("{!r} : {}".format(k, v)
                      for k, v in self.items())
        )

    @cached_property
    def cached_data(self):
        return self.read()

    @abstractmethod
    def read(self):
        """
        Read the record's data and return a mapping of fields to
        values.
        """


class MutableRecord(MutableMapping, AbstractRecord, metaclass=ABCMeta):
    """
    An abstract record that can update or delete itself.
    """
    def __setitem__(self, field, val):
        self.patch({field: val})

    def __delitem__(self, field):
        self.patch({}, (field,))

    def invalidate(self, new_data=None):
        if new_data is None:
            self.__dict__.pop('cached_data', None)
        else:
            self.__dict__['cached_data'] = new_data

    def start_edit_block(self):
        """
        Start a transaction to the backend.

        Backend edits made through this object should be grouped together
        until :meth:`close_edit_block` is called.

        :return: A token that is passed into :meth:`close_edit_block`.

        """
        raise NotImplementedError

    def close_edit_block(self, token):
        """
        End a transaction started by :meth:`start_edit_block`.
        """
        raise NotImplementedError

    def update(self, E=None, **add_data):
        add_data.update({} if E is None else E)
        self.patch(add_data, ())

    @contextmanager
    def edit_block(self):
        """
        A context manager for grouping a chain of edits together.
        Some subclasses may not support performing reads inside an
        edit block.
        """
        token = self.start_edit_block()
        yield token
        self.close_edit_block(token)

    @abstractmethod
    def delete(self):
        """
        Delete the record's data.
        """

    @abstractmethod
    def patch(self, add_data, remove_fields):
        """
        Update the record's data with the new data.
        """


class LazyRecord(AbstractRecord):
    def __init__(self, func):
        self.func = func

    def read(self):
        return self.record

    @cached_property
    def record(self):
        return self.func()


class LazyMutableRecord(MutableRecord, LazyRecord):
    def __init__(self, func):
        self.func = func

    def patch(self, *args, **kwargs):
        self.record.patch(*args, **kwargs)

    def start_edit_block(self):
        return self.record.start_edit_block()

    def close_edit_block(self, token):
        self.record.close_edit_block(token)

    def delete(self):
        self.record.delete()


class FilteredDataSet(AbstractDataSet):
    """
    A concrete implementation of a data set that wraps another data
    to only expose items that pass a through a filter.

    :param dataset: A dataset that is filtered
    :type dataset: :class:AbstractDataSet

    The filter is specified through keyword arguments to the instance.
    Each keyword represents the name of a field that is checked, and
    the corresponding argument indicates what it is checked against. If
    the argument is :class:`~collections.abc.Callable`, then it should
    be a predicate that returns ``True`` if the field is valid (be aware
    that the predicate will passed be ``None`` if the field isn't
    present on the record), otherwise it is compared against the field
    for equality. The function :meth:FilteredDataSet.check_match
    implements this checking procedure.
    """

    def __init__(self, dataset, **filter_spec):
        self.ds = dataset
        self.fs = filter_spec

    def __iter__(self):
        for record in self.ds:
            if self.check_match(record, self.fs):
                yield record

    def __repr__(self):
        return "<filtered-view({!r})|{}".format(
            self.ds,
            ",".join("{}={!r}".format(k, v) for k, v in self.fs.items())
        )

    @staticmethod
    def check_match(record, spec):
        """
        Check that a record matches the search specification.

        :param record: A record against which the specification is checked.
        :type record: :class:collections.abc.Mapping
        :param spec: A dictionary of field names and their expected values.
                     If an "expected value" is callable, it is treated as
                     a predicate that returns ``True`` if the field's
                     value is considered a match.
        """

        for field, expected in spec.items():
            val = record.get(field)
            if isinstance(expected, Callable):
                if not expected(val):
                    return False
            elif not val == expected:
                return False
        else:
            return True


class DataSetSlice(AbstractDataSet):
    """
    A concrete implementation of a data set that wraps another data set
    to expose only a slice of the original set.

    :param start: Items before this zero based, index are skipped.
    :type start: positive integer
    :param stop: If given, this is the first item to be skipped after
                 the slice.
    :type stop: positive integer
    :param step: If given, step - 1 items are skipped between every
                 item in the slice.
    """
    def __init__(self, dataset, start, stop=None, step=None):
        self.ds = dataset
        self.start = start
        self.stop = stop
        self.step = step

    def __iter__(self):
        yield from islice(self.ds, self.start, self.stop, self.step)

    def __repr__(self):
        return "{!r}[{}:{}]".format(
            self.ds,
            self.start,
            "" if self.stop is None else self.stop
        )


class OrderedDataSet(AbstractDataSet):
    """
    A concrete implementation of a data set that wraps another data set
    and returns its items in order.
    """
    def __init__(self, dataset, *sort_spec, descending=False):
        self.ds = dataset
        self.ss = sort_spec
        self.rv = descending

    def __iter__(self):
        yield from sorted(
            self.ds, key=self.make_key(*self.ss), reverse=self.rv)

    def __repr__(self):
        return "<sorted-view[{}] of {!r}>".format(
            ", ".join(self.ss),
            self.ds
        )

    @staticmethod
    def make_key(*sort_spec):
        if len(sort_spec) == 1 and isinstance(sort_spec[0], Callable):
            return sort_spec[0]
        elif any(isinstance(si, Callable) for si in sort_spec):
            raise ValueError("If a key function is used, it must be the "
                             "only argument.")
        else:
            def keyfunc(record):
                return tuple(record.get(k, extremum()) for k in sort_spec)
            return keyfunc

__all__ = ['AbstractDataSet', 'AbstractRecord', 'MutableDataSet',
           'MutableRecord', 'FilteredDataSet', 'DataSetSlice',
           'OrderedDataSet']
