Introduction
============

This section gives a brief introduction to what Findig is, its
design philosophy, and what to expect when using it.


What Findig is
--------------

Findig is a micro-framework for building HTTP applications. It's perhaps
comparable to Flask_ and Bottle_ in terms of size and easy of use.
Continuing in their tradition, it makes it incredibly easy to set up
a WSGI application, and avoids forcing specific choices on you
(such as a database layer or templating engine). However, Findig is
geared specifically toward building RESTful web applications, so much so
that serving HTML for web browsers with Findig would be incredibly 
counter-intuitive.

Where traditional frameworks typically describe web applications in
terms of views (or pages) and routes, Findig applications are described 
in terms of resources and CRUD actions, and the actual generation of
views is done behind the scenes. Here's an example of what an application
that serves a simple JSON API looks like in Findig::

    from findig.json import App
    from dbstack.users import get, save, delete
    
    app = JSONApp()

    @app.route("/users/<int:id>")
    def user(id):
        user = get(id)
        return user.as_dict()

    @user.model("write")
    def user(data, id):
        save(id, data)
        return get(id).as_dict()

    @user.model("delete")
    def user(id):
        delete(id)

    # app is a WSGI callable that can be run by your
    # WSGI server of choice

This code will accept and respond to application/json
``GET|PUT|DELETE`` requests sent to ``/users/:id`` on the server, 
as long as ``id`` looks like an integer. Notice how rather than 
describing the resource in terms of how it looks (i.e., a view), the 
resource is described in terms of how to read, write and delete its data.
It's implied that Findig will use this data to organize the
views and construct the responses. Behind the scenes the 
:class:`findig.json.App` converts the resource data into a JSON formatted
response.

A word on customization
-----------------------

As seen above, Findig lets you describe how to manipulate resource data
and then runs along and does everything else to handle requests 
(including parsing input and formatting output). If that sounds a little
heavy on the fascism, don't despair; it's actually really customizable. 

Input parsing, output formatting and error handling can be globally or 
selectively overridden in all Findig applications. For example, if we 
wanted to also output to XML based on an accept header, 
we could add the following code::

	@user.formatter.register("application/xml")
	def format_xml_response(user_dict):
		# This registers an xml formatter for the user resource
		xml = generate_user_xml_by_some_means(user_dict)
		return xml

.. todo:: Provide links to parts of documentation explaining extending
          parsing, formatting and error handling.

In addition, a lot of Findig's internals are based on abstract classes,
allowing you to plug in custom components that do things just the way you
want them done (let's hope it never comes to that, though).

When to use (and not to use) Findig
-----------------------------------

.. note:: Findig is plain and simple pre-release software. This section
          right now is largely irrelevant for production applications:
          *you simply don't*.

Findig is an API framework that's intended for building APIs, and it aims
to be great at doing only that. As a result, support for applications that
talk to traditional web browsers is virtually non-existent. Instead, use
Findig if you want to build a backend API that powers your web apps and/or
mobile applications.

.. note:: Findig can be used to back angularjs_ apps.

.. _flask: http://flask.pocoo.org/
.. _bottle: http://bottlepy.org/
.. _angularjs: http://https://angularjs.org/