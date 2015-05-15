"""
The core Findig namespace defines the Findig :class:App class, which
is essential to building Findig applications. Every :class:App is
capable of registering resources as well as URL routes that point to them,
and is a WSGI callable that can be passed to any WSGI complaint server.

"""

from contextlib import contextmanager, ExitStack
from functools import wraps
from os.path import join, dirname
import traceback

from werkzeug.local import LocalManager
from werkzeug.routing import Map, RuleFactory
from werkzeug.utils import cached_property
from werkzeug.wrappers import BaseResponse

from findig.context import *
from findig.dispatcher import Dispatcher
from findig.wrappers import Request


with open(join(dirname(__file__), "VERSION")) as fh:
    __version__ = fh.read().strip()


class App(Dispatcher):
    #: The class used to wrap WSGI environments by this App instance.
    request_class = Request
    # This is used internally to track and clean up context variables
    local_manager = LocalManager() 


    def __init__(self, autolist=False):
        """
        Create a new App instance.

        :param autolist: If true, a "lister" resource is created and 
            registered at the URL ``/``. This resource will list all
            of the resources registered with the application which have
            URL rules.

        """
        super(App, self).__init__()

        self.local_manager.locals.append(ctx)
        self.context_hooks = []
        self.cleanup_hooks = []

        if autolist:
            self.route(self.iter_resources, "/")

    def context(self, func):
        """
        Register a request context manager for the application.

        A request context manager is a function that yields once, that is
        used to wrap request contexts. It is called at the beginning of a 
        request context, during which it yields control to Findig, and 
        regains control sometime after findig processes the request. If 
        the function yields a value, it is made available as an
        attribute on :data:`findig.context.ctx` with the same name as the
        function.

        Example::

            >>> from findig.context import ctx
            >>> from findig import App
            >>> 
            >>> app = App()
            >>> items = []
            >>> @app.context
            ... def meaning():
            ...     items.extend(["Life", "Universe", "Everything"])
            ...     yield 42
            ...     items.clear()
            ...
            >>> with app.test_context(create_route=True):
            ...     print("The meaning of", end=" ")
            ...     print(*items, sep=", ", end=": ")
            ...     print(ctx.meaning)
            ...
            The meaning of Life, Universe, Everything: 42
            >>> items
            []

        """
        self.context_hooks.append(contextmanager(func))
        return func

    def cleanup_hook(self, func):
        """
        Register a function that should run after each request in the
        application.
        """
        self.cleanup_hooks.append(func)
        return func

    def __cleanup(self):
        self.local_manager.cleanup()
        for hook in self.cleanup_hooks:
            try:
                hook()
            except:
                pass

    def build_context(self, environ):
        """
        Start a request context.

        :param environ: A WSGI environment.
        :return: A context manager for the request. When the context
            manager exits, the request context variables are destroyed and
            all cleanup hooks are run.

        .. note:: This method is intended for internal use; Findig will
            call this method internally on its own. It is *not* re-entrant
            with a single request.

        """
        ctx.app = self
        ctx.url_adapter = adapter = self.url_map.bind_to_environ(environ)
        ctx.request = self.request_class(environ) # ALWAYS set this after adapter

        rule, url_values = adapter.match(return_rule=True)
        dispatcher = self #self.get_dispatcher(rule)

        # Set up context variables
        ctx.url_values = url_values
        ctx.dispatcher = dispatcher
        ctx.resource = dispatcher.get_resource(rule)

        context = ExitStack()
        context.callback(self.__cleanup)
        # Add all the application's context managers to
        # the exit stack. If any of them return a value,
        # we'll add the value to the application context
        # with the function name.
        for hook in self.context_hooks:
            retval = context.enter_context(hook())
            if retval is not None:
                setattr(ctx, hook.__name__, retval)
        return context

    def test_context(self, create_route=False, **args):
        """
        Make a mock request context for testing.

        A mock request context is generated using the arguments here.
        In other words, context variables are set up and callbacks are
        registered. The returned object is intended to be used as a
        context manager::

            app = App()
            with app.test_context():
                # This will set up request context variables
                # that are needed by some findig code.
                do_some_stuff_in_the_request_context()
            
            # After the with statement exits, the request context
            # variables are cleared. 

        This method is really just a shortcut for creating a fake
        WSGI environ with :py:class:`werkzeug.test.EnvironBuilder` and
        passing that to :meth:`build_context`. It takes the very same
        keyword parameters as :py:class:`~werkzeug.test.EnvironBuilder`;
        the arguments given here are passed directly in.

        :keyword create_route: Create a URL rule routing to a mock resource,
            which will match the path of the mock request. This must be set to True if the mock
            request being generated doesn't already have a route registered
            for the request path, otherwise this method will raise a
            :py:class:`werkzeug.exceptions.NotFound` error. 

        :return: A context manager for a mock request.
        """
        from werkzeug.test import EnvironBuilder

        if create_route:
            path = args.get('path', '/')
            self.route(lambda: {}, path)


        ctx.testing = True
        builder = EnvironBuilder(**args)
        return self.build_context(builder.get_environ())


    def __call__(self, environ, start_response):
        # Set up the application context and run the
        # app inside it.
        try:
            with self.build_context(environ):
                response = ctx.dispatcher.dispatch()
        except BaseException as err:
            try:
                response = self.error_handler(err)
            except:
                traceback.print_exc()
                response = BaseResponse(None, status=500)
        finally:
            return response(environ, start_response)

    def iter_resource_rules(self, resource):
        yield from self.url_map.iter_rules(resource.name)

    def iter_resources(self, adapter=None):
        # The app iters through all registered resources that have been
        # hooked up to a route, for which we can build URLs.
        endpoints = {}
        adapter = ctx.url_adapter if adapter is None else adapter
        
        for rule in self.url_map.iter_rules():
            endpoints[rule.endpoint] = rule

        for endpoint in endpoints:
            # TODO: implement dispatcher API
            dispatcher = self
            yield dispatcher.get_resource(endpoints[endpoint])


    @cached_property
    def url_map(self):
        return Map([r for r in self.build_rules()])