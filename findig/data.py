import codecs
from fnmatch import fnmatch
from itertools import ifilter as filter
import json
from logging import getLogger
from os import listdir
from os.path import join, isfile
import sys

from werkzeug.datastructures import MIMEAccept
from werkzeug.exceptions import *
from werkzeug.http import parse_accept_header, parse_options_header
from werkzeug.wrappers import BaseResponse, Response

from findig.context import request, ctx
from findig.resource import BoundResource, Resource


class _GenericBase(object):
    def __init__(self):
        self.funcs = {}
        self.restricted = {}

    def __call__(self, content_type, default=False):
        def decorator(func):
            self.funcs[content_type] = func
            if default:
                self.default = func
            return func
        return decorator

    def restrict(self, content_type):
        def decorator(res):
            self.restricted.setdefault(res.name, set())
            self.restricted[res.name].add(content_type)
            return res
        return decorator

class GenericParser(_GenericBase):
    def parse(self, request, resource):
        content_type, options = request.headers.get(
            "content-type", type=parse_options_header)

        if not content_type:
            fparse = self.default

        elif content_type in self.funcs:
            fparse = self.funcs[content_type]

        else:
            raise UnsupportedMediaType
        
        restrictions = self.restricted.get(resource.name)
        if restrictions and content_type not in restrictions:
            raise UnsupportedMediaType        
            
        return fparse(request, content_type, options)

    def default(self, request, content_type, options):
        return request.parameter_storage_class({})


class GenericFormatter(_GenericBase):
    def format(self, response, resource):
        accept_header = request.headers.get("Accept") or "*/*"

        accept = parse_accept_header(accept_header, MIMEAccept)

        supported_mimes = [m for m in self.restricted.get(resource.name, self.funcs.keys())
                           if m in self.funcs]
        mime = accept.best_match(supported_mimes, None)

        code, headers = 200, {}

        if mime is None and accept_header != "*/*":
            raise NotAcceptable
        elif mime is None and resource.name in self.restricted:
            raise NotAcceptable
        elif isinstance(response, BaseResponse):
            return response
        elif isinstance(response, tuple):
            if len(response) == 2:
                response, code = response
            elif len(response) == 3:
                response, code, headers = response
            else:
                raise ValueError("Only one, two or three return values are allowed from resource functions.")

        if isinstance(response, BoundResource):
            if response == resource:
                response = resource()

            else:
                headers['Location'] = response.url

        if mime:
            headers['Content-Type'] = mime

        format_func = self.funcs.get(mime, self.default)
        return format_func(code, headers, response, resource)

    def default(self, code, headers, response, resource):
        return Response(unicode(response), status=code, headers=headers)


class GenericErrorHandler(object):
    def __init__(self):
        self.funcs = {Exception: self.default}

    def on(self, exc_type):
        def decorator(fherr):
            self.funcs[exc_type] = fherr
            return fherr
        return decorator

    def handle(self, e, exc_type, message, traceback, top_level=False):
        # Sort the exceptions that we have handlers for, so that
        # subclasses appear before their superclasses (i.e., we want
        # to pass off the exception to the most specific handler available).
        exc_types = sorted(self.funcs, key=_typewrap)

        for et in exc_types:
            if issubclass(exc_type, et):
                response = self.funcs[et](e, exc_type, message, traceback)
                return response
        else:
            # No error handler was found: raise the error
            raise

    def default(self, e, exc_type, message, traceback):
        if isinstance(e, HTTPException):
            return e
        else:
            tp, m, tb = sys.exc_info()
            raise
            #raise m, None, tb

class _typewrap(object):
    def __init__(self, T):
        self.T = T

    def __lt__(self, other):
        if issubclass(self.T, other.T):
            return True
        else:
            return False

    def __gt__(self, other):
        if issubclass(other.T, self.T):
            return True
        else:
            return False


class FormParser(GenericParser):
    def __init__(self):
        super(FormParser, self).__init__()
        self.funcs['application/x-www-form-urlencoded'] = self.default
        self.funcs['multipart/form-data'] = self.default

    def default(self, request, content_type, options):
        return request.form


class JSONParser(GenericParser):
    def __init__(self):
        super(JSONParser, self).__init__()
        self.funcs['application/json'] = self.default

    def default(self, request, content_type, options):
        byte_data = request.data or b"{}"
        try:
            data = json.loads(byte_data, encoding=options.get('charset', 'utf_8'))
        except ValueError as e:
            raise BadRequest("Could not parse JSON: {0".format(e))
        else:
            return request.parameter_storage_class(data)


class JSONFormatter(GenericFormatter):
    def __init__(self, indent=None):
        super(JSONFormatter, self).__init__()
        self.funcs['application/json'] = self.default
        self.indent = indent

    def default(self, code, headers, response, resource):
        if isinstance(response, (list, tuple, dict, str, 
                                 unicode, int, float, 
                                 long, bool)):
            response = json.dumps(response, indent=self.indent)
        else:
            response = None

        return Response(response, content_type="application/json", status=code, headers=headers)

class JSONErrorHandler(GenericErrorHandler):
    def __init__(self, indent=None):
        super(JSONErrorHandler, self).__init__()
        self.indent = indent

    def default(self, e, exc_type, message, traceback):
        d = None
        code = 500
        headers = {}

        if issubclass(exc_type, HTTPException):
            if e.response is not None:
                return e.response

            d = {'error': e.description}
            r = e.get_response(request)
            code = r.status
            headers = r.headers

            del headers['Content-Length']

        else:
            log = getLogger("{}.JSONErrorHandler".format(__name__))
            log.exception("Internal Application Error")
            d = {'error': "An internal application error has been logged."}

        response = None if d is None else json.dumps(d, indent=self.indent)
        return Response(response, content_type="application/json", status=code, headers=headers)


class TemplateFormatter(GenericFormatter):
    def __init__(self, search_path=None, default_template_loc=None,
                 encoding="utf_8"):
        super(TemplateFormatter, self).__init__()
        self.funcs['text/html'] = self.default
        self.templates = {}
        self.default_template_loc = default_template_loc
        self.encoding = encoding

        if search_path is None:
            self.search_path = ["."]
        elif isinstance(search_path, basestring):
            self.search_path = [search_path]
        else:
            self.search_path = search_path

    def template(self, template_name, methods=None):
        def decorator(res):
            self.templates.setdefault(res.name, {})
            if methods is None:
                self.templates[res.name][None] = template_name
            else:
                for method in methods:
                    self.templates[res.name][method.lower()] = template_name
            return res
        return decorator

    def default(self, code, headers, response, resource):
        if isinstance(response, dict):
            response["resource"] = resource
            response["request"] = request

        return self.render(code, headers, response, resource)

    def render(self, code, headers, render_args, resource):
        d, template = self.get_template_location(resource)

        with open(join(d, template), encoding=self.encoding) as fh:
            s = fh.read()

        page = s.format(**render_args)
        return Response(page, status=code, headers=headers)

    def render_template(self, template, args, code=200, headers=None):
        # Create a fake resource that points to the template
        name = "~findig.data/pointer!{0}~".format(template)
        self.templates[name] = { request.method.lower(): template }
        resource = Resource(name=name)
        try:
            return self.format((args, code, headers or {}), resource)
        finally:
            del self.templates[name] 
            

    def get_template_location(self, resource):
        # Searches for a template in the following order:
        # {resource_name}(METHOD)
        # {resource_name}(METHOD).*
        # {resource_name}
        # {resource_name}.*
        # self.default_template_loc
        search_for = [
            "{}({})".format(resource.name, request.method),
            "{}({}).*".format(resource.name, request.method),
            resource.name,
            "{}.*".format(resource.name),
        ]
        if self.default_template_loc:
            search_for.append(self.default_template_loc)

        # However, resource has a template name registered, use that
        # instead.
        if resource.name in self.templates:
            # Get the correct template name for the current request method,
            # or fallback to None
            method = request.method.lower()
            if method in self.templates[resource.name]:
                search_for = [self.templates[resource.name][method]]
            elif None in self.templates[resource.name]:
                search_for = [self.templates[resource.name][None]]

        return self.search_for_template(*search_for)

    def search_for_template(self, *search_for):
        # Scan the search path for a template with any of the provided
        # search names.
        for d in self.search_path:
            for fname in listdir(d):
                if isfile(join(d, fname)):
                    for pattern in search_for:
                        if fnmatch(fname, pattern):
                            return d, fname
        else:
            raise LookupError("No suitable template could be found")


class ProcessorBase(object):
    def __init__(self):
        self.funcs = []

    def __call__(self, func):
        self.funcs.append(func)
        return func


class PreProcessor(ProcessorBase):
    def process(self, data, resource):
        # Just a simple matter of running all
        # the registered functions.
        for func in self.funcs:
            retval = func(data, resource)

            # If any function returns a value that is
            # not None, it is considered to be
            # response data and returned immediately
            if retval is not None:
                return retval


class PostProcessor(ProcessorBase):
    def process(self, response, resource):
        # Just a simple matter of chaining the response
        # through all of the the registered functions.
        for func in self.funcs:
            response = func(response, resource)
        else:
            return response