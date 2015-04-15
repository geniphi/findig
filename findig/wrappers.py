from werkzeug.utils import cached_property
from werkzeug.wrappers import Request as Request_

from findig.content import AbstractParser, Parser
from findig.context import ctx


class Request(Request_):
    # 10MB max content length
    max_content_length = 1024 * 1024 * 10

    @cached_property
    def input(self):
        mime, options, parser = AbstractParser.resolve(
            getattr(ctx.resource, 'parser', Parser()),
            ctx.dispatcher.parser # Fall back to the current dispatcher's parser
        )
        return parser.parse(mime, options, self.data)


__all__ = ['Request']
