from collections import deque, Mapping
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


# Borrowed from contextlib2
# Inspired by discussions on http://bugs.python.org/issue13585
class ExitStack(object):
    """Context manager for dynamic management of a stack of exit callbacks
    
    For example:
    
        with ExitStack() as stack:
            files = [stack.enter_context(open(fname)) for fname in filenames]
            # All opened files will automatically be closed at the end of
            # the with statement, even if attempts to open files later
            # in the list throw an exception
    
    """
    def __init__(self):
        self._exit_callbacks = deque()
        
    def pop_all(self):
        """Preserve the context stack by transferring it to a new instance"""
        new_stack = type(self)()
        new_stack._exit_callbacks = self._exit_callbacks
        self._exit_callbacks = deque()
        return new_stack

    def _push_cm_exit(self, cm, cm_exit):
        """Helper to correctly register callbacks to __exit__ methods"""
        def _exit_wrapper(*exc_details):
            return cm_exit(cm, *exc_details)
        _exit_wrapper.__self__ = cm
        self.push(_exit_wrapper)
        
    def push(self, exit):
        """Registers a callback with the standard __exit__ method signature

        Can suppress exceptions the same way __exit__ methods can.

        Also accepts any object with an __exit__ method (registering the
        method instead of the object itself)
        """
        # We use an unbound method rather than a bound method to follow
        # the standard lookup behaviour for special methods
        _cb_type = type(exit)
        try:
            exit_method = _cb_type.__exit__
        except AttributeError:
            # Not a context manager, so assume its a callable
            self._exit_callbacks.append(exit)
        else:
            self._push_cm_exit(exit, exit_method)
        return exit # Allow use as a decorator

    def callback(self, callback, *args, **kwds):
        """Registers an arbitrary callback and arguments.
        
        Cannot suppress exceptions.
        """
        def _exit_wrapper(exc_type, exc, tb):
            callback(*args, **kwds)
        # We changed the signature, so using @wraps is not appropriate, but
        # setting __wrapped__ may still help with introspection
        _exit_wrapper.__wrapped__ = callback
        self.push(_exit_wrapper)
        return callback # Allow use as a decorator

    def enter_context(self, cm):
        """Enters the supplied context manager
        
        If successful, also pushes its __exit__ method as a callback and
        returns the result of the __enter__ method.
        """
        # We look up the special methods on the type to match the with statement
        _cm_type = type(cm)
        _exit = _cm_type.__exit__
        result = _cm_type.__enter__(cm)
        self._push_cm_exit(cm, _exit)
        return result

    def close(self):
        """Immediately unwind the context stack"""
        self.__exit__(None, None, None)

    def __enter__(self):
        return self

    def __exit__(self, *exc_details):
        if not self._exit_callbacks:
            return
        # This looks complicated, but it is really just
        # setting up a chain of try-expect statements to ensure
        # that outer callbacks still get invoked even if an
        # inner one throws an exception
        def _invoke_next_callback(exc_details):
            # Callbacks are removed from the list in FIFO order
            # but the recursion means they're invoked in LIFO order
            cb = self._exit_callbacks.popleft()
            if not self._exit_callbacks:
                # Innermost callback is invoked directly
                return cb(*exc_details)
            # More callbacks left, so descend another level in the stack
            try:
                suppress_exc = _invoke_next_callback(exc_details)
            except:
                suppress_exc = cb(*sys.exc_info())
                # Check if this cb suppressed the inner exception
                if not suppress_exc:
                    raise
            else:
                # Check if inner cb suppressed the original exception
                if suppress_exc:
                    exc_details = (None, None, None)
                suppress_exc = cb(*exc_details) or suppress_exc
            return suppress_exc
        # Kick off the recursive chain
        return _invoke_next_callback(exc_details)
