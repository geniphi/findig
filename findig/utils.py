from collections import Mapping
import traceback

from findig.data import PreProcessor, PostProcessor
from findig.context import request

def install_preprocessor(manager, func):
    if not isinstance(manager.preprocessor, PreProcessor):
        manager.preprocessor = PreProcessor()
        manager.preprocessor(manager.preprocessor.process)

    manager.preprocessor.funcs.insert(0, func)


def install_postprocessor(manager, func, formatted=False):
    name = 'format_postprocessor' if formatted else 'postprocessor'

    if not isinstance(getattr(manager, name), PostProcessor):
        processor = PostProcessor()
        processor(getattr(manager, name).process)
        setattr(manager, name, processor)

    getattr(manager, name).funcs.insert(0, func)


class Watcher(object):
    # Watcher relies on manager.preprocess and manager.postprocess.
    # If either must be changed, then
    # it MUST be done before the Watcher is
    # instantiated in order for Watcher to work.
    def __init__(self, manager):
        install_preprocessor(manager, self.before_request)
        install_postprocessor(manager, self.after_request)

        self.handlers = {'hit': [], 'created': [], 'modified': [], 'read': [], 'deleted': []}
        self.excluded = []


    def on(self, event):
        if event not in self.handlers:
            raise ValueError("Unknown event: {}".format(event))

        def decorator(func):
            self.handlers[event].append(func)

            return func

        return decorator

    def exclude(self, res):
        self.excluded.append(res.name)
        return res

    def before_request(self, data, resource):
        if resource.name in self.excluded:
            return

        # Call the 'hit' event handlers
        self.call_handlers('hit', resource)

    def after_request(self, response, resource):
        if resource.name in self.excluded:
            return response

        # Call the 'read' event handlers
        if request.method.lower() == 'get':
            self.call_handlers('read', resource, response)

        # Or the 'modified' event handlers
        elif request.method.lower() in ('put', 'patch'):
            self.call_handlers('modified', resource, response)

        # Or the 'created' event handlers
        elif request.method.lower() == 'post':
            self.call_handlers('created', resource, response)

        # Or the 'deleted' event handlers
        elif request.method.lower() == 'delete':
            self.call_handlers('deleted', resource)

        return response

    def call_handlers(self, event, *args, **kwargs):
        self.handlers.setdefault(event, [])
        for handler in self.handlers[event]:
            try:
                handler(*args, **kwargs)
            except:
                traceback.print_exc()
                continue


class Cache(object):
    def __init__(self, manager, fixer=None, key_builder=None):
        install_preprocessor(manager, self.before_request)
        install_postprocessor(manager, self.after_request)

        self.excluded = []
        self.ffix = fixer or (lambda d: d)
        self.fkey = key_builder or (lambda r, i: r.url)
        self.data = {}

    def exclude(self, res):
        self.excluded.append(res.name)
        return res

    def fixer(self, ffix):
        self.ffix = ffix
        return ffix

    def key_builder(self, fkey):
        self.fkey = fkey
        return fkey

    def before_request(self, data, resource):
        if resource.name in self.excluded:
            return

        # If there's data in the cache for
        # this resource, return it.
        key = self.fkey(resource, data)

        if request.method.lower() == 'get' and  key in self:
            return self[key]

    def after_request(self, response, resource):
        if resource.name in self.excluded:
            return

        key = self.fkey(resource, response)

        # Only cache data after a GET request.
        if request.method.lower() == "get":
            # First call the fixer to ensure that
            # the data is cache ready.
            cachable = self.ffix(response)

            # If 'None' is returned from the fixer,
            # it means don't cache
            if cachable is not None:
                # Put the data into the cache
                self[key] = cachable

        else:
            # Any other type of request should invalidate 
            # the cache data
            if key in self:
                del self[key]

        return response

    def __contains__(self, key):
        return key in self.data

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value

    def __delitem__(self, key):
        del self.data[key]


class DelayMapping(Mapping):
    """
    A proxy that takes a function that returns a mapping, and delays
    calling it until the first time an mapping function is called
    on the proxy.
    """

    def __init__(self, fgetmap):
        self.fgetmap = fgetmap

    def __getitem__(self, item):
        m = self.__replace_methods()
        return m[item]

    def __iter__(self):
        m = self.__replace_methods()
        return iter(m)

    def __len__(self):
        m = self.__replace_methods()
        return len(m)

    def __replace_methods(self):
        m = self.fgetmap()
        self.__getitem__ = m.__getitem__
        self.__iter__ = m.__iter__
        self.__len__ = m.__len__

        # Hack for werkzeug storage classes
        if hasattr(m, 'as_dict'):
            self.as_dict = m.as_dict

        return m

    def as_dict(self):
        m = self.__replace_methods()
        if hasattr(m, 'as_dict'):
            return m.as_dict()
        else:
            return dict(self)
