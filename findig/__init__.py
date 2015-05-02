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
    request_class = Request
    local_manager = LocalManager()


    def __init__(self, autolist=False):
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
        the function yields are value, it is made available as an
        attribute on ``findig.context.ctx`` with the same name as the
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
            >>> with app.build_context(): # don't use this unless you're testing, but this is how Findig sets up your request context
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
        self.cleanup_hooks.append(func)
        return func

    def __cleanup(self):
        self.local_manager.cleanup()
        for hook in self.cleanup_hooks:
            try:
                hook()
            except:
                pass

    def build_context(self):
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

    def __call__(self, environ, start_response):
        # Set up the application context and run the
        # app inside it.
        with self.build_context():
            return self.wsgi_app(environ, start_response)

    def wsgi_app(self, environ, start_response):
        """
        Run the WSGI application

        :param environ: A WSGI environment
        :param start_response: A WSGI file handle for the HTTP response.
        :return: A response stream
        """
        try:
            ctx.app = self
            ctx.url_adapter = adapter = self.url_map.bind_to_environ(environ)
            ctx.request = request = self.request_class(environ)
            rule, url_values = adapter.match(return_rule=True)
            response = self.dispatch(request, rule, url_values)
        except BaseException as err:
            try:
                response = self.error_handler(err)
            except:
                traceback.print_exc()
                response = BaseResponse(None, status=500)
        finally:
            return response(environ, start_response)

    def iter_resource_rules(self, resource):
        """An iterable for all the url rules registered for a resource."""
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
            yield dispatcher.endpoints[endpoint]


    @cached_property
    def url_map(self):
        return Map([r for r in self.build_rules()])