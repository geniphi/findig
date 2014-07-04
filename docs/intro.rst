Introduction
============

This section gives a brief introduction to what Findig is, its
design philosophy, and what to expect when using it.


What Findig is
--------------

Findig is a micro-framework for building web applications. It's perhaps
comparable to Flask_ and Bottle_ in terms of size and easy of use.
Continuing in their tradition, it makes it incredibly easy to set up
a WSGI application, and avoids forcing specific choices on you
(such as database layer or templating engine). However, Findig is
geared specifically toward building RESTful web applications.

Where traditional frameworks typically describes web applications in
terms of views (or pages) and routes, Findig applications are described 
in terms of resources and CRUD actions, and the actual generation of
views is done behind the scenes. Here's an example of what a
JSON api application looks like in Findig::

    from findig import JSONApp
    from findig.context import request
    from dbstack.users import get, save, delete
    
    app = JSONApp()

    @app.route("/users/<int:id>")
    def user(id):
        user = get(id)
        return user.as_dict()

    @user.saver
    def user(data, id):
        save(id, data)
        return get(id).as_dict()

    @user.deleter
    def user(id):
        delete(id)

    # app is a WSGI callable that can be run by your
    # WSGI server of choice

This code will accept and respond to application/json
``GET|PUT|PATCH|DELETE`` requests sent to ``/users/<id>`` on the server, 
as long as ``<id>`` looks like an integer, with an application/json.
Notice how rather than describing views that respond to specific requests, 
the application describes a resource in tems of how to get, save and delete 
its data. It's implied that Findig will use this data to organize the
views and construct the responses.

While this abstraction can be superficial and even undesirable for some 
classes of web applications (which we'll get to soon), it's also 
incredibly handy for others.

A word on customization
-----------------------

As seen above, Findig lets you describe how to manipulate resource data
and then runs along and does everything else to handle requests (
including parsing input and formatting output). If that sounds scary, 
don't despair; it's actually really customizable. 

For starters, input parsing, output formatting and error handling can
be completely or selectively overridden in all Findig applications. For
example, if we wanted to also output to XML based on an accept header, 
we could add the following code::

    from werkzeug.wrappers import Response

    @app.formatter("application/xml")
    def format_xml_response(code, headers, response_data, resource):
        assert resource == user
        assert headers["Content-Type"] == "application/xml"
        xml = generate_user_xml_by_some_means(response_data)

        return Response(xml, status=code, headers=headers)

.. todo:: Provide links to parts of documentation explaining extending
          parsing, formatting and error handling.

Further, Findig provides hooks that lets you insert code between each
stage. From your hooks you can affect how the rest of the process works.


When to use (and not to use) Findig
-----------------------------------

.. note:: Findig is plain and simple pre-release software. This section
          right now is largely irrelevant for production applications:
          *you simply don't*.

If all your web application does and will ever do is serve HTML, then
you have very little to gain from using Findig. Not only are frameworks
like Flask_ more stable, they don't waste your time with an extra level
of abstraction that you'll probably never use.

For applications that need to serve RESTful applications however, 
Findig is an excellent option to consider. It's native support of REST
actions and decoupling of view/response generation from resource data
functions provide a clean way automate things around entire groups of
resources (or your entire application!).

If it does its job, the rest of the documentation will not only guide you
on how to use Findig, but shed light on the use cases that it excels at.

.. _flask: http://flask.pocoo.org/
.. _bottle: http://bottlepy.org/