Findig
======

Findig is a micro-framework for building HTTP applications. It is based
on the excellent Werkzeug_ WSGI utility library, and is meant as an
alternative to Flask_ when implementing RESTful APIs.

.. _werkzeug: http://werkzeug.pocoo.org
.. _flask: http://flask.pocoo.org


Declaring Resources and attaching routes
----------------------------------------

.. code:: python

	from klebstoff import App

	app = App()

	@app.route("/u/<int:user>")
	@app.resource(autoroute=False)
	# Note: @app.route("/u/<int:user>") can be used as shorthand for
	# this construct.
	def user(self, user):
		# Query the database for the user id
		# Return the contents of the user resource
		# Access to app.ctx.request is available
		return { id: ... }

	# By default, /u/<user> will only support GET. PATCH and PUT
	# can be added by adding a persistence function
	@user.persist
	def user(self, user, data, method)
		# Save the data to the database
		# Access to app.ctx.request is available;
		# method is equivalent to app.ctx.request.method
		return user

	# And DELETE support can be added by adding a deletion
	# function
	@user.delete
	def user(self, user):
		# Delete the user from the database
		# Access to app.ctx.request is available


Adding a cache
--------------

.. code:: python

	from klebstoff.abc import Cache

	class AppCache(Cache):
		def get(self, resource_name, args):
			# Return the resource data if in cache, otherwise
			# just return None.

		def set(self, resource_name, args, data):
			# Store the resource data in the cache, associated
			# with the given resource name and arguments

	app.set_cache(AppCache())
