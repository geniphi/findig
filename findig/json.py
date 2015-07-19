from collections.abc import Iterable, Mapping
import json
import re
import traceback

from werkzeug.exceptions import BadRequest, HTTPException
from werkzeug.routing import BuildError as URLBuildError
from werkzeug.wrappers import Response

from findig import App as App_
from findig.content import ErrorHandler, Formatter, Parser
from findig.context import ctx, request
from findig.dispatcher import Dispatcher as Dispatcher_
from findig.resource import AbstractResource, Collection, Resource


class CustomEncoder(json.JSONEncoder):
    """
    A custom :class:`json.JSONEncoder` that goes a bit further to coerce
    data into json.

    Any Python mapping is converted to a javascript object.

    Any Python iterable that isn't a mapping is converted to a list.

    The encoder also provides an object representation for
    :class:`~findig.resource.AbstractResource`.

    """

    #: A pattern that matches the variable parts of a URL rule.
    value_pattern = re.compile("<(?:.*?:)?(.*?)>")

    def default(self, obj):
        if isinstance(obj, Mapping):
            return dict(obj)
        elif isinstance(obj, Iterable):
            return list(obj)
        elif isinstance(obj, AbstractResource):
            rule = next(ctx.app.iter_resource_rules(obj))

            d = {
                'methods': rule.methods,
            }

            try:
                url = ctx.url_adapter.build(obj.name)
                d['url'] = url
            except URLBuildError:
                url = self.value_pattern.sub(r":\1", rule.rule)
                d['url_rule'] = url
                d['url'] = None

            if isinstance(obj, Resource):
                d['is_strict_collection'] = isinstance(obj, Collection)

            return d

        else:
            return super().default(obj)


class JSONMixin:
    def __init__(self, indent=None, encoder_cls=None, **args):
        self.indent = indent
        self.encoder_cls = CustomEncoder \
            if encoder_cls is None \
            else encoder_cls
        super().__init__(**args)

        self.error_handler = ErrorHandler()
        self.error_handler.register(BaseException, self._respond_error)
        self.error_handler.register(HTTPException, self._respond_http_error)

        self.formatter = Formatter()
        self.formatter.register(
            'application/json', self.serialize, default=True)

        self.parser = Parser()
        self.parser.register(
            'application/json', self.deserialize, default=True)

    def _respond_error(self, err):
        # TODO: log error
        traceback.print_exc()
        return self.make_response({"message": "internal error"}, status=500)

    def _respond_http_error(self, http_err):
        response = http_err.get_response(request)

        headers = response.headers
        del headers['Content-Type']
        del headers['Content-Length']

        return self.make_response({"message": http_err.description},
                                  status=response.status,
                                  headers=response.headers)

    def make_response(self, data, **args):
        """
        make_response(data, status=None, headers=None)

        Construct a JSON response from the given data.
        """
        args.pop("mimetype", None)
        args.pop("content_type", None)

        jsonified = self.serialize(data)
        return Response(jsonified, mimetype="application/json", **args)

    def serialize(self, data):
        jsonified = json.dumps(data, indent=self.indent, cls=self.encoder_cls)
        return jsonified

    def deserialize(self, byte_string, **opts):
        byte_string = b"" if byte_string is None else byte_string
        try:
            jsonified = byte_string.decode(opts.get('charset', 'utf8'))
            data = json.loads(jsonified) if jsonified else {}
        except UnicodeDecodeError:
            raise BadRequest("Cannot decode request data")
        except ValueError as err:
            raise BadRequest("Can't parse request data {}".format(err))
        else:
            if isinstance(data, dict):
                return request.parameter_storage_class(data)
            else:
                return data


class Dispatcher(JSONMixin, Dispatcher_):
    """A :class:`Dispatcher` for use with JSON applications."""


class App(JSONMixin, App_):
    """
    App(indent=None, encoder_cls=None, autolist=False)

    A :class:`findig.App` that works with application/json data.

    This app is pre-configured to parse incoming ``application/json`` data,
    output ``application/json`` data by default and convert errors to
    ``application/json`` responses.

    :param indent: The number of spaces to indent by when outputting
        JSON. By default, no indentation is used.
    :param encoder_cls: A :class:`json.JSONEncoder` subclass that should be
        used to serialize data into JSON. By default, an encoder that
        converts all mappings to JSON objects and all other iterables to
        JSON lists in addition to the normally supported simplejson types
        (int, float, str) is used.
    :param autolist: Same as the *autolist* parameter in
        :class:`findig.App`.

    """

__all__ = ["Dispatcher", "App"]
