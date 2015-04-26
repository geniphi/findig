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
        accept_header = ctx.request.get("Accept")
        
        if accept_header is None:
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
                if hasattr(inst, 'default'):
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
            return partial(self.handlers[content_type], **options)

        elif hasattr(self, 'default'):
            return partial(self.handlers[self.default], **options)

        else:
            raise UnsupportedMediaType


#class AbstractFormatter(metaclass=ABCMeta):
#    @abstractmethod
#    def get_supported_mimes(self):
#        """
#        Return a list of content-types that this converter supports.
#        """

#    @abstractmethod
#    def format(self, mime, data):
#        """
#        Convert the data into a Response based on the data that was
#        passed in.

#        :param mime: The content-type that the data should be formatted
#                     to. It's guaranteed to be one of the types returned
#                     by :meth:get_supported_mimes.
#        :type mime: str
#        :param data: Data that should be converted to output
#        :type data: object
#        :rtype: Response
#        """

#    @staticmethod
#    def resolve(*instances):
#        """
#        Return the formatter best suited for handling the current
#        requested content-type.

#        Formatters that appear earlier in the argument list are given
#        priority in tie-breaking (when two or more formatters support
#        the same content type).

#        If no content-type is requested, and a formatter supports
#        a content-type called 'default', that formatter will be returned.

#        If no formatter in the list supports 'default', and no formatter
#        otherwise matches the requested content-type, but the request will
#        support any content-type, the first formatter that supports a
#        content-type will be returned.

#        If no formatter can be resolved for the requested content types,
#        then NotAcceptable is raised.

#        :return: The matched mime and formatter
#        :rtype: (str, AbstractFormatter)
#        :raises ValueError: if the request supports any content type, but
#                            there's no formatter that supports at least
#                            one mime.
#        :raises NotAcceptable: if no suitable formatter can be resolved.
#        """
#        # Parse the Accept header
#        accept = parse_accept_header(
#            ctx.request.headers.get("Accept", "*/*"),
#            MIMEAccept
#        )

#        matches = []

#        for i, formatter in enumerate(instances):
#            supported = ('d/d' if m == 'default'
#                         else m
#                         for m in formatter.get_supported_mimes())
#            mime = accept.best_match(supported)

#            if mime is not None:
#                quality = accept.quality(mime)
#                priority = i * -1
#                mime = 'default' if mime == 'd/d' else mime
#                matches.append((quality, priority, mime, formatter))

#        if matches:
#            match = max(matches, key=lambda tup:tup[:2])
#            return match[2:]

#        elif '*/*' in accept.values():
#            for formatter in instances:
#                for mime in formatter.get_supported_mimes():
#                    return mime, formatter
#            else:
#                raise ValueError("No viable formatters.")
#        else:
#            raise NotAcceptable

#class AbstractParser(metaclass=ABCMeta):
#    @abstractmethod
#    def get_supported_mimes(self):
#        """
#        Return a list of content-types that this converter supports.
#        """

#    @abstractmethod
#    def parse(self, mime, options, data):
#        """
#        Return a mapping of the request data.
#        """

#    @staticmethod
#    def resolve(*instances):
#        """
#        Return the parser best suited for handling the request's content.

#        If the request doesn't specify a content-type, the first 
#        parser that supports a content-type called 'default' is returned.

#        Otherwise, the first parser that supports the content-type is
#        returned.

#        :raises UnsupportedMediaType: if no parser is resolved.
#        """

#        content_type, options = ctx.request.headers.get(
#            "content-type", type=parse_options_header
#        )

#        for parser in instances:
#            supported = parser.get_supported_mimes()

#            if not content_type and "default" in supported:
#                return "default", {}, parser

#            elif content_type in supported:
#                return content_type, options, parser

#        else:
#            raise UnsupportedMediaType


#class ContentTranslatorMixin:
#    def __init__(self):
#        self.handlers = {}

#    def __call__(self, mime):
#        def decorator(func):
#            self.register_handler(mime, func)

#        if isinstance(mime, Callable):
#            mime = "default"
#            return decorator(func)
#        else:
#            return decorator

#    def register_handler(self, mime, func):
#        """Register a handler for a specific mime type."""
#        self.handlers[mime] = func

#    def get_supported_mimes(self):
#        return list(self.handlers)


#class Formatter(ContentTranslatorMixin, AbstractFormatter):
#    """
#    A generic, concrete implementation of :class:AbstractFormatter

#    This formatter can collect functions for specific mime types.
#    :class:Formatter instances can be used as generator factories
#    to register formatter functions for specific mime-types::

#        >>> formatter = Formatter()
#        >>> @formatter("application/json")
#        ... def format_json(data):
#        ...     print(data['answer'])
#        ...
#        >>> formatter.format("application/json", {"answer": 42})
#        42

#    """
#    def format(self, mime, data):
#        """See :meth:`AbstractFormatter.format`."""
#        handler = self.handlers[mime]
#        return handler(data)


#class Parser(ContentTranslatorMixin, AbstractParser):
#    """
#    A generic, concrete implementation of :class:AbstractParser

#    This parser can collect functions for specific mime types.
#    :class:Parser instances can be used as generator factories
#    to register parser functions for specific mime-types::

#        >>> parser = Parser()
#        >>> @parser("application/json")
#        ... def parse_json(data, **options)
#        ...     import json
#        ...     return json.loads(data.decode(options.get('charset', 'utf8')))
#        ...
#        >>> parser.parse("application/json", {}, b'{"answer": 42}')
#        {'answer': 42}

#    """
#    def parse(self, mime, options, data):
#        """See :meth:`AbstractParser.parse`."""
#        handler = self.handlers[mime]
#        return handler(data, **options)

__all__ = "Formatter", "Parser", "ErrorHandler"
