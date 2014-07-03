from codecs import open
from functools import partial
from os.path import join, getmtime

from jinja2 import Environment, BaseLoader, TemplateNotFound
from werkzeug.wrappers import Response

from findig.data import TemplateFormatter
from findig.context import ctx
from findig.resource import BoundResource, Resource


class JinjaFormatter(TemplateFormatter, BaseLoader):
    def __init__(self, search_path=None, default_template=None, encoding="utf_8"):
        super(JinjaFormatter, self).__init__(
            search_path, default_template_loc=default_template)
        self.env = Environment(loader=self)
        self.encoding = encoding

    def render(self, code, headers, context, resource):
        # Store the resource so we can check against it later
        ctx.resource = resource

        # Get a template for the resource
        template = self.env.get_template(resource.name)

        # Construct a response from the resource
        return Response(
            template.render(**context),
            status=code, headers=headers
        )

    def get_source(self, environment, name):
        if name == ctx.resource.name:
            func = partial(self.get_template_location, ctx.resource)
        else:
            func = partial(self.search_for_template, name)

        try:
            path = join(*func())
        except LookupError:
            msg = "Could not find a template for resource: {0}".format(name)
            raise TemplateNotFound(msg)
        else:
            with open(path, "rb", self.encoding) as fh:
                source = fh.read()
            mtime = getmtime(path)
            return source, path, lambda: mtime == getmtime(path)

__all__ = 'JinjaFormatter',