from functools import partial
import sys

from werkzeug.routing import Rule, RuleFactory
from werkzeug.wrappers import BaseResponse

from findig.context import *
from findig.data import GenericFormatter, GenericParser, GenericErrorHandler, PreProcessor, PostProcessor
from findig.resource import Resource, CollectionResource
from findig.utils import DelayMapping


class Manager(RuleFactory):
    def __init__(self, **args):
        self.parser = args.get('parser', GenericParser())
        self.formatter = args.get('formatter', GenericFormatter())
        self.exceptions = args.get('exceptions', GenericErrorHandler())
        self.preprocessor = args.get('preprocessor', PreProcessor())
        self.postprocessor = args.get('postprocessor', PostProcessor())
        self.format_postprocessor = args.get('format_postprocessor',
                                             PostProcessor())
        self.rules = []

    def resource(self, **args):
        collection = args.pop("collection", True)
        tp = CollectionResource if collection else Resource
        def decorator(fget):
            args['fget'] = fget
            args['manager'] = self
            return tp(**args)
        return decorator

    def route(self, rule, **args):
        def decorator(res):
            if not isinstance(res, Resource):
                res = Resource(fget=res, manager=self)
            elif res.manager is None:
                # Take over the resource if it doesn't have
                # a manager
                res.manager = self
                            
            self.rules.append((rule, args, res))

            return res
        return decorator

    def get_rules(self, map, prefix=None):
        for rule, args, res in self.rules:
            # Add the prefix if given
            if prefix is not None:
                rule = u"{prefix}{rule}".format(**locals())

            # Construct each Rule and yield it.
            args['endpoint'] = res
            args['methods'] = res.get_method_list()
            yield Rule(rule, **args)

            # If the resource requires a method hack
            # we need to add an extra url rule just for
            # the delete request.
            if res.method_hack:
                fragment = "<any(delete, put, patch):findig__method_hack>"
                joiner = "" if rule.endswith("/") else "/"
                rule = joiner.join((rule, fragment))
                args['methods'] = ["POST", "GET"]
                yield Rule(rule, **args)

    def handle(self, request, resource):
        try:
            # Set the parser function on the context so that the request
            # input property can get to it later
            ctx._parser = partial(self.parser.parse, request, resource)

            # Create a proxy to the input data; we do it this way because
            # we don't want to parse the data unless its actually needed
            # (i.e. until something actually tries to access it).
            data = DelayMapping(lambda: request.input)

            # Run the preprocessor and check whether it
            # veto's the request. 
            response = self.preprocessor.process(data, resource)

            if isinstance(response, BaseResponse):
                return response

            elif response is None:
                # Let the resource handle the request
                # First apply the method hack:
                if resource.method_hack and "findig__method_hack" in resource.bind_args:
                    method = resource.bind_args.pop("findig__method_hack")
                    request.environ["REQUEST_METHOD"] = method.upper()

                response = resource(request.method, data)

                # Only call the post-processor when the resource is called
                response = self.postprocessor.process(response, resource)

            # format the response and return it
            response = self.formatter.format(response, resource)
            return self.format_postprocessor.process(response, resource)

        except Exception as e:
            tp, m, tb = sys.exc_info()
            return self.exceptions.handle(e, tp, m, tb)

