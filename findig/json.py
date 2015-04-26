from collections.abc import Iterable, Mapping
import json
import traceback

from werkzeug.exceptions import HTTPException
from werkzeug.wrappers import Response

from findig import App as App_
from findig.dispatcher import Dispatcher as Dispatcher_
from findig.content import *
from findig.context import request


class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Mapping):
            return dict(obj)
        elif isinstance(obj, Iterable):
            return list(obj)
        else:
            return super().default(obj)


class JSONMixin:
    def __init__(self, indent=None, encoder_cls=None):
        self.indent = indent
        self.encoder_cls = CustomEncoder if encoder_cls is None else encoder_cls
        super().__init__()

        self.error_handler = ErrorHandler()
        self.error_handler.register(BaseException, self._respond_error)
        self.error_handler.register(HTTPException, self._respond_http_error)
        
        self.formatter = Formatter()
        self.formatter.register('application/json', self.serialize, default=True)

        self.parser = Parser()
        self.parser.register('application/json', self.deserialize, default=True)

    def _respond_error(self, err):
        # TODO: log error
        traceback.print_exc()
        return Response(self.serialize({"message": "internal error"}), 
                        mimetype="application/json", status=500)

    def _respond_http_error(self, http_err):
        response = http_err.get_response(request)

        headers = response.headers
        del headers['Content-Type']
        del headers['Content-Length']

        return Response(self.serialize({"message": http_err.description}),
                        mimetype="application/json", 
                        status=response.status, headers=response.headers)

    def serialize(self, data):
        jsonified = json.dumps(data, indent=self.indent, cls=self.encoder_cls)
        return jsonified

    def deserialize(self, byte_string, **opts):
        byte_string = b"" if byte_string is None else byte_string
        try:
            jsonified = byte_string.decode(opts.get('charset', 'utf8'))
            data = json.loads(jsonified)
        except UnicodeDecodeError:
            raise BadRequest("Cannot decode request data")
        except ValueError as err:
            raise BadRequest("Can't parse request data {}".format(err))
        else:
            return request.parameter_storage_class(data)


class Dispatcher(JSONMixin, Dispatcher_):
    """A :class:Dispatcher for use with JSON applications."""


class App(JSONMixin, App_):
    """
    An :class:App that works with application/json data.

    This app is pre-configured to parse incoming application/json data,
    output application/json data by default and convert errors to
    application/json responses.

    """

__all__ = ["Dispatcher", "App"]