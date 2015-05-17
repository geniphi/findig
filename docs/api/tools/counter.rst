:mod:`findig.tools.counter` --- Hit counters for apps and resources
===================================================================

.. automodule:: findig.tools.counter
    
    .. autoclass:: Counter
        
        .. automethod:: attach_to

        .. automethod:: partition(name, fgroup)

        .. automethod:: every(n, callback, after=None, until=None, resource=None)
        
        .. automethod:: at(n, callback, resource=None)

        .. automethod:: after_every(n, callback, after=None, until=None, resource=None)

        .. automethod:: after(n, callback, resource=None)

        .. automethod:: hits
        
    .. autoclass:: AbstractLog
        :members:
        :special-members:
        :exclude-members: __weakref__


    Counter example
    ---------------

    Counters can be used to implement more complex tools. For example,
    a simple rate-limiter can be implemented using the counter API::

        from findig.json import App
        from findig.tools.counter import Counter
        from werkzeug.exceptions import TooManyRequests

        app = App()

        # Using the counter's duration argument, we can set up a
        # rate-limiter to only consider requests in the last hour.
        counter = counter(app, duration=3600)

        LIMIT = 1000

        @counter.partition('ip')
        def get_ip(request):
            return request.remote_addr

        @counter.every(1, after=1000, ip=counter.any)
        def after_thousandth(ip):
            raise TooManyRequests("Limit exceeded for: {}".format(ip))