import sys
from os.path import dirname, join

from werkzeug.local import LocalManager
from werkzeug.routing import Map
from werkzeug.wrappers import Request

from findig.context import *
from findig.data import JSONErrorHandler, JSONFormatter, JSONParser
from findig.manager import Manager


with open(join(dirname(__file__), "VERSION")) as fh:
    __version__ = fh.read().strip()


class App(Manager):
    request_class = Request
    local_manager = LocalManager()


    def __init__(self, **args):
        super(App, self).__init__(**args)

        self.local_manager.locals.append(ctx)

        self.managers = [self]

    def __call__(self, environ, start_response):
        wsgi_app = self.local_manager.make_middleware(self.wsgi_app)
        return wsgi_app(environ, start_response)

    def wsgi_app(self, environ, start_response):
        request = self.request_class(environ)
        response = self.dispatch(request)
        return response(environ, start_response)

    def dispatch(self, request):
        ctx.app = self
        ctx.request = request
        ctx.url_adapter = adapter = self.url_map.bind_to_environ(
            request.environ)

        try:
            rule, url_values = adapter.match(return_rule=True)

            # Bind the url values to the resource object that was
            # stored as the rule endpoint, creating a bound resource.
            resource = rule.endpoint.bind(**url_values)

            # Ask the resource manager to handle the request
            response = resource.manager.handle(request, resource)

        except Exception as e:
            tp, m, tb = sys.exc_info()
            return self.exceptions.handle(e, tp, m, tb, top_level=True)
        else:
            return response

    def add_manager(self, manager):
        if manager not in self.managers:
            self.managers.append(manager)

    def rebuild_url_map(self):
        self._url_map = map = Map()

        for manager in self.managers:
            map.add(manager)
        
        return map

    @property
    def url_map(self):
        if not hasattr(self, '_url_map'):
            return self.rebuild_url_map()
        else:
            return self._url_map


class JSONApp(App):
    def __init__(self, **args):
        args.setdefault("formatter", JSONFormatter())
        args.setdefault("exceptions", JSONErrorHandler())
        args.setdefault("parser", JSONParser())
        super(JSONApp, self).__init__(**args)