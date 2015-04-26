from functools import singledispatch
import warnings
import traceback

from werkzeug.exceptions import HTTPException
from werkzeug.routing import Rule
from werkzeug.wrappers import Response, BaseResponse

from findig.content import ErrorHandler, Formatter, Parser
from findig.context import ctx
from findig.resource import Resource, AbstractResource

class Dispatcher:
    """A collector of routes and dispatcher of requests."""

    response_class = Response

    def __init__(self, formatter=None, parser=None, error_handler=None):
        self.route = singledispatch(self.route)
        self.route.register(str, self.route_decorator)

        if error_handler is None:
            error_handler = ErrorHandler()
            error_handler.register(BaseException, self._handle_exception)
            error_handler.register(HTTPException, self._handle_http_exception)

        if parser is None:
            parser = Parser()
        
        if formatter is None:
            formatter = Formatter()
            formatter.register('text/plain', str, default=True)

        self.formatter = formatter
        self.parser = parser
        self.error_handler = error_handler

        self.resources = {}
        self.routes = []
        self.endpoints = {}

    def _handle_exception(self, err):
        # TODO: log error
        traceback.print_exc()
        return Response("An internal application error has been logged.",
                        status=500)

    def _handle_http_exception(self, http_err):
        response = http_err.get_response(ctx.request)

        headers = response.headers
        del headers['Content-Type']
        del headers['Content-Length']

        return Response(http_err.description, status=response.status, 
                        headers=response.headers)


    def resource(self, wrapped=None, **args):
        """
        Create a :class:Resource instance.

        :param wrapped: A wrapped function for the resource. In most cases,
                        this should be a function that takes named
                        route arguments for the resource and returns a
                        dictionary with the resource's data.
               
        The keyword arguments are passed on directly to the constructor
        for :class:Resource, with the exception that *name* will default to 
        {module}.{name} of the wrapped function if not given.

        This method may also be used as a decorator factory::

            @dispatcher.resource(name='my-very-special-resource')
            def my_resource(route, param):
                return {'id': 10, ... }

        In this case the decorated function will be replaced by a
        :class:Resource instance that wraps it. Any keyword arguments
        passed to the decorator factory will be handed over to the
        :class:Resource constructor. If no keyword arguments 
        are required, then ``@resource`` may be used instead of
        ``@resource()``.

        .. note:: If this function is used as a decorator factory, then
                  a keyword parameter for *wrapped* must not be used.

        """
        def decorator(wrapped):
            args['wrapped'] = wrapped
            args.setdefault(
                'name', "{0.__module__}.{0.__qualname__}".format(wrapped))
            resource = Resource(**args)
            self.resources[resource.name] = resource
            return resource

        if wrapped is not None:
            return decorator(wrapped)

        else:
            return decorator

    def route(self, resource, rulestr, **ruleargs):
        """
        Add a route to a resource.

        Adding a URL route to a resource allows Findig to dispatch
        incoming requests to it.

        :param resource: The resource that the route will be created for.
        :type resource: :class:Resource or function
        :param rulestr: A URL rule, according to
                        :ref:`werkzeug's specification <werkzeug:routing>`.
        :type rulestr: str
        
        See :py:class:`werkzeug.routing.Rule` for valid rule parameters.

        This method can also be used as a decorator factory to assign
        route to resources using declarative syntax::
        
            @route("/index")
            @resource(name='index')
            def index_generator():
                return ( ... )

        """
        if not isinstance(resource, AbstractResource):
            resource = self.resource(resource)

        self.routes.append((resource, rulestr, ruleargs))

        return resource

    def route_decorator(self, rulestr, **ruleargs):
        """See :meth:route."""
        def decorator(resource):
            # Collect the rule
            resource = self.route(resource, rulestr, **ruleargs)

            # return the resource
            return resource

        return decorator

    def build_rules(self):
        """
        Return a generator for all of the url rules collected by the
        :class:Dispatcher.

        :param warn_routes: If True, the function will emit a warning
                            about resources that have no routes assigned
                            to them.
        :rtype: Iterable of :class:werkzeug.routing.Rule

        .. note:: This method will 'freeze' resource names; do not change
                  resource names after this function is invoked.

        """
        self.endpoints.clear()

        # Refresh the resource dict so that up-to-date resource names
        # are used in dictionaries
        self.resources = dict((r.name, r) for r in self.resources.values())

        # Build the URL rules
        for resource, string, args in self.routes:
            # Set up the callback endpoint
            args.setdefault('endpoint', resource.name)
            self.endpoints[args['endpoint']] = resource

            # And the supported methods
            supported_methods = resource.get_supported_methods()
            restricted_methods = set(
                map(str.upper, args.get('methods', supported_methods)))
            args['methods'] = supported_methods.intersection(restricted_methods)
            # warn about unsupported methods
            
            unsupported_methods = list(set(restricted_methods) - supported_methods)
            if unsupported_methods:
                warnings.warn(
                    "Error building rule: {string}\n"
                    "The following HTTP methods have been declared, but "
                    "are not supported by the data model for {resource.name}: "
                    "{unsupported_methods}.".format(**locals())
                    )

            # Initialize the rule, and yield it
            yield Rule(string, **args)

    def dispatch(self, request, rule, url_values):
        """
        Dispatch a request to the appropriate resource, based on
        which resource the rule applies to.
        """
        # TODO: document request context variables.
        ctx.dispatcher = self
        ctx.resource = resource = self.endpoints[rule.endpoint]
        ctx.url_values = url_values
        ctx.response = response = {} # response arguments

        try:
            data = resource.handle_request(request, url_values)

            if isinstance(data, (self.response_class, BaseResponse)):
                return data

            else:
                format = Formatter.compose(
                    getattr(resource, 'formatter', Formatter()),
                    self.formatter
                )

                mime_type, formatted = format(data)   
                response = {k:v for k,v in response.items() 
                            if k in ('status', 'headers')}
                response['mimetype'] = mime_type
                response['response'] = formatted
                return self.response_class(**response)
        except BaseException as err:
            return self.error_handler(err)

    @property
    def unrouted_resources(self):
        """
        A list of resources created by the dispatcher which have no
        routes to them.
        """
        routed = set()
        for resource in self.endpoints.values():
            if resource.name in self.resources:
                routed.add(resource.name)
        else:
            return list(map(self.resources.get, 
                            set(self.resources) - routed))