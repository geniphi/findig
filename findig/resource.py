import abc
import collections
import functools
import inspect
import itertools
import uuid
from collections.abc import Mapping
from functools import partial

from werkzeug.exceptions import MethodNotAllowed, NotFound
from werkzeug.routing import BuildError as URLBuildError
from werkzeug.utils import cached_property, validate_arguments

from findig.content import ErrorHandler, Formatter, Parser
from findig.context import url_adapter, request, ctx
from findig.data_model import DataModel, DataSetDataModel, DictDataModel


class AbstractResource(metaclass=abc.ABCMeta):
    """
    Represents a very low-level web resource to be handled by Findig.

    Findigs apps are essentially a collection of routed resources. Each
    resource is expected to be responsible for handling some requests to
    a set of one or more URLs. When requests to such a URL is received,
    Findig looks-up what resource is responsible, and hands the request
    object over to the resource for processing.

    Custom implementations of the abstract class are possible. However,
    this class operates at a very low level in the Findig stack, so it is
    recommended that they are only used for extreme cases where those
    low-level operations are needed.

    In addition to the methods defined here, resources should have a
    name attribute, which is a string that uniquely identifies it within
    the app. Optional *parser* and *formatter* attributes corresponding to
    :class:`findig.content.AbstractParser` and 
    :class:`finding.content.AbstractFormatter` instances respectively, 
    will also be used if added.
    """

    @abc.abstractmethod
    def get_supported_methods(self):
        """
        Return a Python set of HTTP methods to be supported by the resource.
        """
        
    @abc.abstractmethod
    def handle_request(self, request, url_values):
        """
        Handle a request to one of the resource URLs.

        :param request: An object encapsulating information about the
                        request. It is the same as 
                        :py:data:`findig.context.request`.
        :type request: :class:`~findig.wrappers.Request`, which
                       in turn is a subclass of
                       :py:class:`werkzeug.wrappers.Request`
        :param url_values: A dictionary of arguments that have been parsed
                           from the URL routes, which may help to better
                           identify the request. For example, if a resource
                           is set up to handle URLs matching the rule
                           ``/items/<int:id>`` and a request is sent to
                           ``/items/43``, then *url_values* will be
                           ``{'id': 43}``.
        :return: This function should return data that will be transformed
                 into an HTTP response. This is usually a dictionary, but
                 depending on how formatting is configured, it may be
                 any object the output formatter configured for the
                 resource will accept.
        """


class Resource(AbstractResource):
    """
    Resource(wrapped=None, lazy=None, name=None, model=None, formatter=None, parser=None, error_handler=None)

    A concrete implementation of :class:`AbstractResource`.

    This accepts keyword arguments only.

    :keyword wrapped: A function which the resource wraps; it
                        typically returns the data for that particular
                        resource.
    :keyword lazy: Indicates whether the wrapped resource function
                    returns lazy resource data; i.e. data is not 
                    retrieved when the function is called, but at some
                    later point when the data is accessed. Setting this
                    allows Findig to evaluate the function's return
                    value after all resources have been declared to
                    determine if it returns anything useful (for
                    example, a :class:DataRecord which can be used as
                    a model).
    :keyword name: A name that uniquely identifies the resource.
                    If not given, it will be randomly generated.
    :keyword model: A data-model that describes how to read and write
                    the resource's data. By default, a generic
                    :class:`findig.data_model.DataModel` is attached.
    :keyword formatter: A function that should be used to format the 
                        resource's data. By default, a generic
                        :class:`findig.content.Formatter` is attached.
    :keyword parser: A function
                        that should be used to parse request content
                        for the resource. By default, a generic
                        :class:`findig.content.Parser` is attached.
    :keyword error_handler: A function that should be used to convert
        exception into :class:`Responses <werkzeug.wrappers.BaseResponse>`.
        By default, a :class:`findig.content.ErrorHandler` is used.

    """
    def __init__(self, **args):        
        self.name = args.get('name', str(uuid.uuid4()))
        self.model = args.get('model', DataModel())
        self.lazy = args.get('lazy', False)
        self.parser = args.get('parser', Parser())
        self.formatter = args.get('formatter', Formatter())

        if 'error_handler' not in args:
            args['error_handler'] = eh = ErrorHandler()
            args['error_handler'].register(LookupError, self._on_lookup_err)
            
        self.error_handler = args.get('error_handler')

        wrapped = args.get('wrapped', lambda **_: {})        
        functools.update_wrapper(self, wrapped)

    def _on_lookup_err(self, err):
        raise NotFound

    def __call__(self, **kwargs):
        return self.__wrapped__(**kwargs)

    def compose_model(self, wrapper_args=None):
        """
        :noindex:

        Make a composite model for the resource by combining a
        lazy data handler (if present) and the model specified on
        the resource.

        :param wrapper_args: A set of arguments to call the wrapped
                             function with, so that a lazy data handler
                             can be retrieved. If none is given, then
                             fake data values are passed to the wrapped
                             function. In this case, the data-model
                             returned *must not* be used.
        :returns: A data-model for the resource

        **This is an internal method.**
        """
        if self.lazy:
            if wrapper_args is None:
                # Pass in some fake ass argument values to the wrapper
                # so we can get a pretend data-set for inspection.
                argspec = inspect.getfullargspec(self.__wrapped__)
                wrapper_args = {
                    name : None for name in
                    itertools.chain(argspec.args, argspec.kwonlyargs)
                    }

            dataset = self.__wrapped__(**wrapper_args)
            dsdm = DataSetDataModel(dataset)
            return self.model.compose(dsdm)
        elif wrapper_args is not None and 'read' not in self.model:
            # Add a 'read' method to the model that just calls this
            # model.
            new_model = DictDataModel({
                'read': lambda: self.__wrapped__(**wrapper_args)
            })
            return self.model.compose(new_model)
        else:
            return self.model

    def get_supported_methods(self, model=None):
        """
        Return a set of HTTP methods supported by the resource.

        :param model: The data-model to use to determine what methods
                      supported. If none is given, a composite data model
                      is built from ``self.model`` and any data source
                      returned by the resource's wrapped function.
        """
        model = self.compose_model() if model is None else model
        supported_methods = {'GET'}

        if 'delete' in model:
            supported_methods.add('DELETE')

        if 'write' in model:
            supported_methods.add('PUT')

        return supported_methods

    def handle_request(self, request, wrapper_args):
        """
        Dispatch a request to a resource.
        
        See :py:meth:`AbstractResource.handle_request` for accepted
        parameters.
        
        """
        method = request.method.upper()
        try:
            model = self.compose_model(wrapper_args)
            handler = self._extract_handler(request, method, model)

            args, kwargs = validate_arguments(handler.func, handler.args, wrapper_args)
            return handler.func(*args, **kwargs)
            
        except BaseException as err:
            return self.error_handler(err)

    def _extract_handler(self, request, method, model):
        supported_methods = self.get_supported_methods(model)

        if method not in supported_methods and method != 'HEAD':
            raise MethodNotAllowed(list(supported_methods))

        elif method == 'GET' or method == 'HEAD':
            return partial(model['read'])

        elif method == 'DELETE':
            return partial(model['delete'])

        elif method == 'PUT':
            return partial(model['write'], request.input)

        else:
            raise ValueError    
        
    def collection(self, wrapped=None, **args):
        """
        Create a :class:`Collection` instance

        :param wrapped: A wrapped function for the collection. In most
            cases, this should be a function that returns an iterable of
            resource data.

        The keyword arguments are passed on to the constructor for
        :class:Collection, except that if no *name* is given, it defaults
        to {module}.{name} of the wrapped function.

        This function may also be used as a decorator factory::

            @resource.collection(include_urls=True)
            def mycollection(self):
                pass

        The decorated function will be replaced in its namespace by a 
        :class:`Collection` that wraps it. Any keyword arguments
        passed to the decorator factory will be handed over to the
        :class:Collection constructor. If no keyword arguments 
        are required, then ``@collection`` may be used instead of
        ``@collection()``.

        """
        def decorator(wrapped):
            args['wrapped'] = wrapped
            args.setdefault(
                'name', "{0.__module__}.{0.__qualname__}".format(wrapped))
            return Collection(self, **args)

        if wrapped is not None:
            return decorator(wrapped)

        else:
            return decorator


class Collection(Resource):
    """
    Collection(of, include_urls=False, bindargs=None, **keywords)

    A :class:`Resource` that acts as a collection of other resources.

    :param of: The type of resource to be collected.
    :type of: :class:`Resource`
    :param include_urls: If ``True``, the collection will attempt to
        insert a ``url`` field on each of the child items that it returns. 
        Note that this only works if the child already has enough information
        in its fields to build a url (i.e., if the URL for the child
        contains an ``:id`` fragment, then the child must have an id
        field, which is then used to build its URL.
    :param bindargs: A dictionary mapping field names to URL variables.
        For example: a child resource may have the URL variable ``:id``,
        but have a corresponding field named ``user_id``; the appropriate
        value for *bindargs* in this case would be ``{'user_id': 'id'}``.

    """
    def __init__(self, of, **args):
        super(Collection, self).__init__(**args)
        self.include_urls = args.pop('include_urls', False)
        bindargs = args.pop('bindargs', {})
        self.collects = collections.namedtuple(
            "collected_resource", "resource binding")(of, bindargs)

    def get_supported_methods(self, model=None):
        model = self.compose_model() if model is None else model
        supported = super().get_supported_methods(model)
        
        if 'make' in model:
            supported.add('POST')

        return supported


    def _extract_handler(self, request, method, model):
        if method == 'POST':
            return partial(model['make'], request.input)
        else:
            return super()._extract_handler(request, method, model)

    def handle_request(self, request, wrapper_args):
        ret = super().handle_request(request, wrapper_args)

        if request.method.lower() == 'post':
            ctx.response.setdefault('status', 201)

            url = self._try_build_item_url(data)
            if url is not None:
                ctx.response['headers'].setdefault('Location', url)

        elif method == 'GET' and self.include_urls:
            ret = map(self._include_url_in_item, ret)

        return ret

    def _include_url_in_item(self, item):
        url = self._try_build_item_url(item)
        if url is not None:
            if isinstance(item, Mapping):
                item = dict(item)
                item.setdefault('url', url)
            else:
                try:
                    item.url = url
                except:
                    pass

        return item

    def _try_build_item_url(self, data):
        child, bind_args = self.collects
        if not isinstance(data, Mapping):
            data = data.__dict__
        args = {(bind_args[k] if k in bind_args else k):data[k]
                for k in data}
        try:
            url = url_adapter.build(child.name, args, append_unknown=False)
        except URLBuildError:
            pass
        else:
            return url


__all__ = ['AbstractResource', 'Resource', 'Collection']