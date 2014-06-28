Findig
======

Findig is a micro-framework for developing RESTful Python web applications
that's built on Werkzeug_.

.. _werkzeug: http://werkzeug.pocoo.org/


Why not just use Flask?
-----------------------

Flask_ is great; we love it! What we noticed, however, is that it's best
suited for HTML-based web apps. Findig is an alternative that's tuned for
building RESTful applications, or APIs.

.. _flask: http://flask.pocoo.org/


How does it work?
-----------------

A RESTful application can be seen as a set of web resources that can be read
and modified using different HTTP verbs. With Findig, you create your
application by declaring your resources. The gist is that you provide a
function that knows how to read the resource data from storage, and optionally
update it when it changes; Findig handles the REST (yeah, we like puns).
Of course, most of Findig's guts are easily customizable for when your API
needs an added layer of complexity.


Useful features
---------------

- Easy caching support. Srsly iz so ez.

- Built-in support for multiple response types.

- Protect resources with OAuth (oauthlib2 support via extra).