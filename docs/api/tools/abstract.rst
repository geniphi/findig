Abstract classes for higher-level tools
=======================================

Some higher-level tools aren't explicitly implemented by Findig;
rather abstract classes for how they are expected to behave are defined
so that support libraries and applications can provide their own
implementations.

.. _data-sets:

Data sets
---------

Data sets are one example of higher level tools without an explicit
implementation. Abstractly, they're collections of resource data that also
encapsulate an implicit data model (i.e., instructions on data access).
This makes them a powerful replacement for explicitly defining a 
data-model for each resource, since a resource function can instead return
a data set and have Findig construct a resource from it::

    @app.route("/items/<int:id>")
    @app.resource(lazy=True)
    def item(id):
        return items().fetch(id=id)

    @app.route("/items")
    @item.collection(lazy=True)
    def items():
        return SomeDataSet()

Findig currently includes one concrete implementation:
:class:`findig.extras.redis.RedisSet`.

.. autoclass:: findig.tools.dataset.AbstractDataSet
    :members:

.. autoclass:: findig.tools.dataset.MutableDataSet
    :members:

.. autoclass:: findig.tools.dataset.AbstractRecord
    :members:

.. autoclass:: findig.tools.dataset.MutableRecord
    :members: