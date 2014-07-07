from werkzeug.utils import cached_property
from werkzeug.wrappers import Request as Request_

from findig.context import ctx


class Request(Request_):
    # 10MB max content length
    max_content_length = 1024 * 1024 * 10

    @cached_property
    def input(self):
        return ctx._parser()


__all__ = ['Request']
