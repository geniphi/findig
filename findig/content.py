from abc import ABCMeta, abstractmethod
from collections.abc import Callable
from functools import partial

from werkzeug.datastructures import MIMEAccept
from werkzeug.exceptions import NotAcceptable, UnsupportedMediaType
from werkzeug.http import parse_accept_header, parse_options_header

from findig.context import ctx
from findig.utils import tryeach


class HandlerAggregator:
    def __init__(self):
        self.handlers = {}

    def register(self, key=None, handler=None):
        def register_handler(handler):
            self.handlers[key] = handler
            return handler

        if handler is None:
            return register_handler

        else:
            if not isinstance(handler, Callable):
                raise ValueError("Argument handler: must be callable.")

            register_handler(handler)


class ErrorHandler(HandlerAggregator):
    """
    A generic implementation of a error handler 'function'.

    A :class:ErrorHandler collects handler functions for specific
    exception types, so that when it is called, it looks up the 
    appropriate handler for the exception that it is called with.
    The handler used is the closest superclass of the exception's type.

    """

    def register(self, err_type=None, handler=None):
        if not issubclass(err_type, BaseException):
            raise ValueError("Argument 'err_type': must be an "
                             "exception type.")
        return super().register(err_type, handler)

    def choose_best_handler(self, err):
        # Try to find the most specific error handler for this method
        best_htype = BaseException
        err_type = type(err)

        for htype in self.handlers:
            if issubclass(err_type, htype):
                if issubclass(htype, best_htype):
                    best_htype = htype

        if best_htype in self.handlers:
            return self.handlers[best_htype]

        else:
            # Re-raise the exception
            raise err

    def __call__(self, err):
        handler = self.choose_best_handler(err)
        return handler(err)


class ContentPipe(HandlerAggregator, metaclass=ABCMeta):
    def register(self, mime_type, handler=None, default=False):
        if mime_type.count("/") != 1:
            raise ValueError("Argument 'mime_type': doesn't appear to be a "
                             "valid mime-type")
        if default:
            self.default = mime_type

        return super().register(mime_type, handler)

    def __call__(self, obj):
        mime_type, handler = self.choose_best_handler()
        return mime_type, handler(obj)

    @abstractmethod
    def choose_best_handler(self):
        pass

    
class Formatter(ContentPipe):
    """
    A generic implementation of a formatter 'function'.

    A :class:Formatter collects handler functions for specific mime-types,
    so that when it is called, it looks up the the appropriate function
    to call in turn, according to the mime-type specified by the request's
    ``Accept`` header

    .. note:: Instances of this class require an active request context
              in order to work properly.

    """

    def choose_best_handler(self):
        # The best handler for the formatter instance depends on the
        # request; in particular it relies on what the client has 
        # indicated it can accept

        # Get the accept header
        accept_header = ctx.request.headers.get("Accept")
        
        if accept_header == "*/*" or accept_header is None:
            if hasattr(self, 'default'):
                return self.default, self.handlers[self.default]

            else:
                try:
                    return next(iter(self.handlers.items()))
                except StopIteration:
                    raise ValueError("No handlers have been registered "
                                     "for this formatter.")

        else:
            accept = parse_accept_header(accept_header, MIMEAccept)
            mime_type = accept.best_match(self.handlers)

            if mime_type is not None:
                return mime_type, self.handlers[mime_type]

            else:
                raise NotAcceptable

        # Parse the Accept header
        accept = parse_accept_header(
            ctx.request.headers.get("Accept", "*/*"),
            MIMEAccept
        )

        mime_type = accept.best_match(self.handlers)

        if mime_type is not None:            
            return mime_type, self.handlers[mime_type]

        elif "*/*" in accept.values():
            for mimetype in self.handlers:
                return self.handlers[mimetype]
            else:
                # The requesting client will accept anything, but we
                # don't have handlers at all. This is a LookupError
                raise LookupError("No formatter handlers available at "
                                  "all; cannot format this data.")

        else:
            # The output format that the requesting client asked for
            # isn't supported. This is NotAcceptable
            raise NotAcceptable

    @staticmethod
    def compose(first, second, *rest):
        formatters = [first, second]
        formatters.extend(rest)

        if all(map(lambda f: isinstance(f, Formatter), formatters)):
            new_formatter = Formatter()
            for inst in reversed(formatters):
                new_formatter.handlers.update(inst.handlers)
                if getattr(inst, 'default', None) is not None:
                    new_formatter.default = inst.default
            return new_formatter
        else:
            return partial(tryeach, formatters)


class Parser(ContentPipe):
    """
    A generic implementation of a parser 'function'.

    A :class:Parser collects handler functions for specific mime-types,
    so that when it is called, it looks up the the appropriate function
    to call in turn, according to the mime-type specified by the request's
    ``Content-Type`` header

    .. note:: Instances of this class require an active request context
              in order to work properly.

    """
    def choose_best_handler(self):
        content_type, options = ctx.request.headers.get(
            "content-type", type=parse_options_header
        )

        if content_type in self.handlers:
            return content_type, partial(self.handlers[content_type], **options)

        elif hasattr(self, 'default'):
            return self.default, partial(self.handlers[self.default], **options)

        else:
            raise UnsupportedMediaType

__all__ = "Formatter", "Parser", "ErrorHandler"
