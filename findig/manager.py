import sys

from werkzeug.routing import Rule, RuleFactory

from findig.context import *
from findig.data import GenericFormatter, GenericParser, GenericErrorHandler, PreProcessor, PostProcessor
from findig.resource import Resource, CollectionResource


class Manager(RuleFactory):
    def __init__(self, **args):
        self.parser = args.get('parser', GenericParser())
        self.formatter = args.get('formatter', GenericFormatter())
        self.exceptions = args.get('exceptions', GenericErrorHandler())
        self.prepocessor = args.get('preprocessor', PreProcessor())
        self.postprocessor = args.get('postprocessor', PostProcessor())
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

    def handle(self, request, resource):
        try:
            # Get the request data
            data = self.parser.parse(request, resource)

            # Run the preprocessor and check whether it
            # veto's the request. 
            response = self.prepocessor.process(data, resource)

            if response is None:
                # Only call the resource if the pre-processor
                # doesn't return a response
                request.input = data

                # Let the resource handle the request
                response = resource(request.method)

                # Only call the post-processor when the resource is called
                response = self.postprocessor.process(response, resource)

            # format the response and return it
            return self.formatter.format(response, resource)

        except Exception as e:
            tp, m, tb = sys.exc_info()
            return self.exceptions.handle(e, tp, m, tb)

