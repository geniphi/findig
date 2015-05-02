from werkzeug.utils import cached_property
from werkzeug.wrappers import Request as Request_

from findig.content import Parser
from findig.context import ctx
from findig.datapipe import DataPipe
from findig.utils import tryeach


class Request(Request_):
    # 10MB max content length
    max_content_length = 1024 * 1024 * 10

    @cached_property
    def input(self):
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
