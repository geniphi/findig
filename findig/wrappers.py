from werkzeug.utils import cached_property
from werkzeug.wrappers import Request as Request_

from findig.content import Parser
from findig.context import ctx
from findig.utils import DataPipe, tryeach


class Request(Request_):
    """A default request class for wrapping WSGI environs."""
    
    #: The maximum allowed content-length for the requests is set to
    #: 10MB by default.
    max_content_length = 1024 * 1024 * 10

    @cached_property
    def input(self):
        """
        Request content that has been parsed into a python object.
        This is a read-only property.
        """
        parsed = tryeach(
            [
                getattr(ctx.resource, 'parser', Parser()),
                ctx.dispatcher.parser
            ],
            self.data
        )[1]

        process = DataPipe(
            getattr(ctx.resource, 'pre_processor', None),
            ctx.dispatcher.pre_processor
        )

        return process(parsed)


__all__ = ['Request']
