"""
This module stores request context variables. That is, variables whose
values are assigned during the handling of a request and then cleared
immediately after the request is done.

.. important:: With exception of *ctx*, all of the variables documented
   here are proxies to attributes of *ctx*. For example, *app* is a
   proxy to *ctx.app*.
"""

from werkzeug.local import Local


#: A global request context local that can be used by anyone to store
#: data about the current request. Data stored on this object will be
#: cleared automatically at the end of each request and call only be
#: seen on the same thread that set the data. This means that data
#: accessed through this object will only ever be relevant to the current
#: request that is being processed.
ctx = Local()

# A bunch of context local proxies

#: The :py:class:`findig.App` instance that responded to the request.
app = ctx('app')

#: An object representing the current request and a subclass of 
#: :py:data:`findig.App.request_class`.
request = ctx('request')

#: An object representing a :py:class:`werkzeug.routing.MapAdapter` for
#: the current reques that can be used to build URLs.
url_adapter = ctx('url_adapter')

#: The :py:class:`~findig.dispatcher.Dispatcher` that registered the
#: resource that the current request is directed to.
dispatcher = ctx('dispatcher')

#: The :py:class:`~findig.resource.AbstractResource` that the current
#: request is directed to.
resource = ctx('resource')

#: A dictionary of values that have been extracted from the request path 
#: by matching it against a URL rule.
url_values = ctx('url_values')


__all__ = ['ctx', 'app', 'request', 'url_adapter', 
           'dispatcher', 'resource', 'url_values']
