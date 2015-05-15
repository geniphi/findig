"""
The :mod:`findig.tools.counter` module defines the :class:`Counter` tool,
which can be used as a hit counter for your application. Counters can
count hits to a particular resource, or globally within the application.

"""

from abc import ABCMeta, abstractmethod
from collections import Counter as PyCounter, namedtuple
from datetime import datetime, timedelta
from itertools import chain, combinations
from functools import partial, reduce, total_ordering
from numbers import Integral
from threading import Lock
import heapq

from werkzeug.utils import validate_arguments

from findig.context import ctx

class Counter:
    """
    A :class:`Counter` counter keeps track of hits (requests) made on an
    application and its resources.

    :param app: The findig application whose requests the counter will track.
    :type app: :class:`findig.App`, or a subclass like :class:`findig.json.App`.
    :param duration: If given, the counter will only track hits that 
        occurred less than this duration before the current time. 
        Otherwise, all hits are tracked.
    :type duration: :class:`datetime.timedelta` or int representing seconds.
    :param storage: A subclass of :class:`AbstractLog` that should be used
        to store hits. By default, the counter will use a thread-safe,
        in-memory storage class.

    """

    any = [] # just needed an unhashable object here

    def __init__(self, app=None, duration=-1, storage=None):
        self.logs = {}
        self.callbacks = {
            'before': {None:[]},
            'after': {None:[]},
        }
        self.duration = duration
        self.partitioners = {}
        self.log_cls = _HitLog if storage is None else storage

        if app is not None:
            self.attach_to(app)

    def attach_to(self, app):
        """
        Attach the counter to a findig application.

        .. note:: This is called automatically for any app that is passed
            to the counter's constructor.

        By attaching the counter to a findig application, the counter is
        enabled to wrap count hits to the application and fire callbacks.

        :param app: The findig application whose requests the counter will 
            track.
        :type app: :class:`findig.App`, or a subclass like 
            :class:`findig.json.App`.

        """
        app.context(self)

    def partition(self, name, fgroup=None):
        """
        Create a partition that is tracked by the counter.

        A partition can be thought of as a set of mutually exclusive 
        groups that hits fall into, such that each hit can only belong to
        one group in any single partition. For example, if we
        partition a counter by the IP address of the requesting clients,
        each possible client address can be thought of as one group, since
        it's only possible for any given hit to come from just one of those
        addresses.

        For every partition, a *grouping function* must be supplied to help
        the counter determine which group a hit belongs to. The
        grouping function takes a request as its parameter, and returns
        a hashable result that identifies the group. For example, if we
        partition by IP address, our grouping function can either return
        the IP address's string representation or 32-bit (for IPv4) 
        integer value.

        By setting up partitions, we can query a counter for the number of
        hits belonging to a particular group in any of our partitions. For 
        example, if we wanted to count the number GET requests, we could 
        partition the counter on the request method (here our groups would
        be GET, PUT, POST, etc) and query the counter for the number of
        hits in the GET group in our request method partition::

            counter = Counter(app)
           
            # Create a partition named 'method', which partitions our
            # hits by the request method (in uppercase).
            counter.partition('method', lambda request: request.method.upper())

            # Now we can query the counter for hits belonging to the 'GET' 
            # group in our 'method' partition
            hits = counter.hits()
            number_of_gets = hits.count(method='GET')

        :param name: The name for our partition.
        :param fgroup: The grouping function for the partition. It must]
            be a callable that takes a request and returns a hashable
            value that identifies the group that the request falls into.

        This method can be used as a decorator factory::

            @counter.partition('ip')
            def getip(request):
                return request.remote_addr

        A counter may define more than one partition.

        """
        def add_partitioner(keyfunc):
            self.partitioners[name] = keyfunc
            return keyfunc

        if fgroup is not None:
            return add_partitioner(fgroup)
        else:
            return add_partitioner

    def _register_cb(self, when, n, callback, args):
        allowed_args = ['until', 'after', 'resource']
        allowed_args.extend(self.partitioners)
        for a in args:
            if a not in allowed_args:
                raise TypeError("Unknown argument: {}".format(a))

        key = args.pop('resource').name if 'resource' in args else None
        self.callbacks[when].setdefault(key, [])
        self.callbacks[when][key].append((callback, n, args))

    def every(self, n, callback=None, **args):
        """
        Call a callback every *n* hits.

        :param resource: If given, the callback will be called on every
            *n* hits to the resource.
        :param after: If given, the callback won't be called until *after*
            this number of hits; it will be called on the (after+1)th hit
            and every nth hit thereafter.
        :param until: If given, the callback won't be called after this
            number of hits; it will be called up to and including this
            number of hits.
        
        If partitions have been set up (see :meth:`partition`), additional
        keyword arguments can be given as ``{partition_name}={group}``. In
        this case, the hits are filtered down to those that match the
        partition before issuing callbacks. For example, we can run some
        code on every 100th GET request after the first 1000 like this::

            counter.partition('method', lambda r: r.method.upper())

            @counter.every(100, after=1000, method='GET')
            def on_one_hundred_gets(method):
                pass

        Furthermore, if we wanted to issue a callback on every 100th
        request of any specific method, we can do this::

            @counter.every(100, method=counter.any)
            def on_one_hundred(method):
                pass

        The above code is different from simply ``every(100, callback)`` 
        in that ``every(100, callback)`` will call the callback on every
        100th request received, while the example will call the callback
        of every 100th request of a particular method (every 100th GET,
        every 100th PUT, every 100th POST etc). 
        
        Whenever partition specs are used to register callbacks,
        then the callback must take a named argument matching the
        partition name, which will contain the partition group for the
        request that triggered the callback.

        """
        def decorator(callback):
            self._register_cb('before', n, callback, args)
            return callback

        if callback is not None:
            return decorator(callback)
        else:
            return decorator

    def after_every(self, n, callback=None, **args):
        """
        Call a callback after every *n* hits.

        This method works exactly like :meth:`every` except that 
        callbacks registered with :meth:`every` are called before the
        request is handled (and therefore can throw errors that interupt
        the request) while callbacks registered with this function are
        run after a request has been handled.
        """
        def decorator(callback):
            self._register_cb('after', n, callback, args)
            return callback

        if callback is not None:
            return decorator(callback)
        else:
            return decorator

    def at(self, n, callback=None, **args):
        """
        Call a callback on the *nth* hit.

        :param resource: If given, the callback will be called on every
            *n* hits to the resource.

        Like :meth:`every`, this function can be called with partition
        specifications.

        This function is equivalent to ``every(1, after=n-1, until=n)``
        """
        return self.every(1, callback=callback, after=n-1, until=n, **args)

    def after(self, n, callback=None, **args):
        """
        Call a callback after the *nth* hit.

        This method works exactly like :meth:`at` except that 
        callbacks registered with :meth:`at` are called before the
        request is handled (and therefore can throw errors that interupt
        the request) while callbacks registered with this function are
        run after a request has been handled.
        """
        return self.after_every(1, callback=callback, after=n-1, until=n, **args)

    def hits(self, resource=None):
        """
        Get the hits that have been recorded by the counter.

        The result can be used to query the number of
        total hits to the application or resource, as well as the number
        of hits belonging to specific partition groups::

            # Get the total number of hits
            counter.hits().count()

            # Get the number of hits belonging to a partition group
            counter.hits().count(method='GET')

        The result is also an iterable of (:class:`datetime.datetime`, 
        *partition_mapping*) objects.

        :param resource: If given, only hits for this resource will be
            retrieved.
        """
        if resource is None:
            return reduce(
                lambda x,y: x + y, 
                self.logs.values(), 
                self.log_cls(self.duration, None)
            )
        else:
            self.logs.setdefault(resource.name, self.log_cls(self.duration, resource))
            return self.logs[resource.name]

    def __call__(self):
        # Calling the counter registers a 'hit'.
        request = ctx.request
        resource = ctx.resource

        self.logs.setdefault(resource.name, self.log_cls(self.duration, resource))
        hit_log = self.logs[resource.name]
        partitions = {name: func(request) for name, func in self.partitioners.items()}
        hit_log.track(partitions)

        fire_callbacks = partial(self._fire_cb_funcs, hit_log, resource,
                                 partitions)

        fire_callbacks('before')

        yield

        fire_callbacks('after')

    def _fire_cb_funcs(self, hit_log, resource, partitions, group):
        callbacks = self.callbacks[group]
        callbacks.setdefault(resource.name, [])
        callbacks = chain(callbacks[resource.name], callbacks[None])

        #@counter.every(1, after=1000, method=any)

        for cb_func, n, args in callbacks:
            # {'ip': counter.any, 'method': 'PUT'}
            partby = {a:args[a] for a in args if a in self.partitioners}
            # {'ip': '255.215.213.32', 'method': 'GET'}
            request_vals = {k:partitions[k] for k in partby}
            count = hit_log.count(**request_vals)

            if partby:
                # Actually verify that the callback restrictions apply to
                # this request
                unmatched = [p for p,v in partby.items() 
                             if not (v == self.any or v == partitions[p])]
                if unmatched:
                    continue

            if 'until' in args and args['until'] < count:
                continue

            if 'after' in args and count <= args['after']:
                continue

            if (count - args.get('after', 0) - 1) % n == 0:
                cb_func(**request_vals)


class AbstractLog(metaclass=ABCMeta):
    """
    Abstract base for a storage class for hit records.

    This module provides a thread-safe, in-memory concrete implementation 
    that is used by default. 
    """

    @abstractmethod
    def __init__(self, duration, resource):
        """
        Initialize the abstract log

        All implementations must support this signature for their
        constructor.

        :param duration: The length of time for which the log should
            store records. Or if -1 is given, the log should store all
            records indefinitely.
        :type duration: :class:`datetime.timedelta` or int representing seconds.
        :param resource: The resource for which the log will store records.
        """

    @abstractmethod
    def __iter__(self):
        """
        Iter the stored hits.

        Each item iterated must be a 2-tuple in the form 
        (:class:`datetime.datetime`, partitions).

        """

    @abstractmethod
    def track(self, partitions):
        """
        Store a hit record

        :param partitions: A mapping from partition names to the group
            that the hit matches for the partition. See
            :meth:`Counter.partition`.

        """

    @abstractmethod
    def count(self, **partition_spec):
        """
        Return the number of hits stored.

        If no keyword arguments are given, then the total number of hits
        stored should be returned. Otherwise, keyword arguments must be
        in the form ``{partition_name}={group}``. See
        :meth:`Counter.partition`.
        """

    def __add__(self, other):
        if isinstance(other, AbstractLog):
            return _CompositeLog(self, other)
        else:
            return NotImplemented


class _CompositeLog(AbstractLog):
    # This isn't really a storage class so much as it's a convenience
    # class for stitching logs together
    def __init__(self, first, second, *others):
        self._logs = [first, second]
        self._logs.extend(others)

    def __iter__(self):
        yield from chain.from_iterable(self._logs)

    def track(self, partitions):
        raise NotImplementedError("Composite log is read only.")

    def count(self, **partitions):
        return sum(map(lambda l: l.count(**partitions), self._logs))

                
class _HitLog(AbstractLog):
    # This is a storage class that keep track of the hits that have
    # occurred over a given duration.
    # This particular implementation keeps track of hits in-memory.
    def __init__(self, duration, _): # last argument is resource (or None), but it is unused.
        self._hits = []
        self._delta = duration if isinstance(duration, timedelta) \
                               else timedelta(seconds=duration)
        self._thread_lock = Lock()
        self._counter = PyCounter()

    def _prune(self):
        if self._delta.total_seconds() < 0:
            # negative seconds means keep everything.
            return 

        now = datetime.now()
        with self._thread_lock:
            while self._hits and (now - self._hits[0][0]) > self._delta:
                time, partitions = heapq.heappop(self._hits)
                self._counter.subtract(self._generate_counter_keys(partitions))

    def _generate_counter_keys(self, partitions):
        sub_keys = chain.from_iterable(
            combinations(partitions, r) for r in range(1, len(partitions)+1)
        )

        for key_list in sub_keys:
            counter_key = tuple(sorted(map(lambda k: (k, partitions[k]), key_list)))
            yield counter_key

    def track(self, partitions):
        now = datetime.now()

        with self._thread_lock:
            heapq.heappush(self._hits, (now, partitions))
            self._counter.update(self._generate_counter_keys(partitions))

    def count(self, **partitions):
        self._prune()

        if not partitions:
            return len(self._hits)

        else:
            counter_key = tuple(sorted(partitions.items()))
            return self._counter[counter_key]

    def __add__(self, other):
        if isinstance(other, _HitLog):
            if self._delta != other._delta:
                return NotImplemented
            else:
                new_log = _HitLog(self._delta, None)

                new_log._hits.extend(self._hits)
                new_log._hits.extend(other._hits)
                heapq.heapify(new_log._hits)

                new_log._counter.update(self._counter)
                new_log._counter.update(other._counter)
                
                return new_log

        else:
            return NotImplemented

    def __iter__(self):
        ascending = heapq.nsmallest(self.count(), self._hits)
        for time, partitions in ascending:
            yield Hit(time, partitions)

    def __len__(self):
        return self.count()

    def __repr__(self):
        return "HitLog({})".format(self.count())

Hit = namedtuple("Hit", "time parts")

