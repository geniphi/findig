from functools import singledispatch
import warnings

from werkzeug.routing import Rule

from findig.resource import Resource

class Dispatcher:
    """A collector of routes and dispatcher of requests."""

    def __init__(self):
        self.route = singledispatch(self.route)
        self.route.register(str, self.route_decorator)

        self.resources = {}
        self.routes = []
        self.endpoints = {}


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
        if not isinstance(resource, Resource):
            resource = self.resource(resource)

        self.routes.append((resource, rulestr, ruleargs))

        return resource

    def route_decorator(self, rulestr, **ruleargs):
        """See :meth:route."""
        def decorator(resource):
            # Turn regular old function into resources
            if not isinstance(resource, Resource):
                resource = self.resource(resource)

            # Collect the rule
            self.route(resource, rulestr, **ruleargs)

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
        resource = self.endpoints[rule.endpoint]
        return resource.handle_request(request, url_values)

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