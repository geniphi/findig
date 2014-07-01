from findig import App
from findig.context import request
from findig.data import FormParser
from werkzeug.wrappers import Response
from werkzeug.serving import run_simple

# A simple Findig example app
#
# Findig applications are collections of managed web resources. Apps are 
# described by declaring resources and the actions that they support 
# (get, save and delete).
#
# This example shows how a very simple application can be declared in 
# Findig.
#

# A fake data store for our app
DATA = {}

# Instantiate an application from which we can declare resources.
# In our constructor, we set the app's input parser to FormParser,
# which parses form data. Whatever parser you choose, request.input
# will always be set to the parsed data. The type of request.input for
# built-in parsers is app.request_class.parameter_storage_class.
app = App(
    parser=FormParser()
)

##########-------INTERMEZZO---------###########
# Declaring resources is a two-stage process, and the App instance 
# provides a decorator for each stage.
#
# In the first stage the resource itself is instantiated with a function 
# that fetches its data and returns it. @app.resource(**args) is a handy 
# decorator that uses the wrapped function as the getter function, and 
# passes any arguments it receives on to the resource.
#
# In the second stage, a url route to the resource must be declared
# (or else it would just be sitting there, never used and stuff).
# @app.route(rule) is the decorator to do this. The argument is a werkzeug 
# compatible rule string, which is documented at 
# http://werkzeug.pocoo.org/docs/routing/.
#
# The app provides two url resources:
#
# /hello - Greet the user with a friendly message (GET)
# /name - Display and change the user's name (GET PUT PATCH DELETE)
#

# Declare a resource and assign a route to it
# Resource names should be unique throughout the entire application.
# If the name argument is omitted, then __module__.__name__ of the
# getter function is used.
@app.route("/hello")
@app.resource(name="greeter")
def greeter():
    # This function is the data getter for the resource. Its job is
    # to fetch the resource data from the data store. In general, it
    # should avoid any side effects (such as modifying data) as Findig
    # may use it to get resource data under some circumstances.
    return {"message": "Hello {0}".format(DATA.get("name", "Findig"))}

# method_hack=True causes Findig to internally restructure GET or POST
# requests sent to /name/put /name/patch or name/delete to appear like 
# they were PUT PATCH or DELETE requests sent to /name.
@app.route("/name")
@app.resource(method_hack=True, name="name")
def name():
    return {"name": DATA.get("name")}

# Define a saver function that will save input data to the resource.
# This function is called during both PUT and PATCH requests. Findig's
# default behavior for PATCH requests is to update the request input
# with missing keys from the resource data. This allows the saver 
# function to always treat the input data as though it were a PUT
# request, but calls the resource getter, potentially hitting the
# database.
@name.saver
def name():
    # findig.context.request always proxies to the current request.
    # request.input contains parsed input data for the request, depending
    # on how app.parser is configured.
    DATA['name'] = request.input['name']

# Additionally, a deleter function can teach Findig how to handle
# DELETE requests.
@name.deleter
def name():
    del DATA['name']


# This is where we tell Findig how to format all of our responses.
# We want to output HTML and JSON. For this example we will use the decorator
# syntax to declare formatters for output.
@app.formatter("text/html", default=True)
def format_html(status_code, headers, resource_data, resource):
    # This example app only has two resources, so we can define
    # our templates here without it getting *too* messy. For larger
    # apps, you may want to consider using something like a 
    # TemplateFormatter instead of defining our templates in code
    # branches.

    if resource.name == "greeter":
        template = """
<h1>{message}!</h1>
<p>I'm not sure if I got that right. If I didn't,
   you can always <a href="/name">change it here</a>.</p>"""
        
    elif resource.name == "name":
        # If the data function didn't return anything,
        # we can redirect them to /hello
        if resource_data is None:
            return Response(None, status=303, 
                            headers={"Location": greeter.bind().url})

        template = """
<h1>What's your name?</h1>
<p>Sorry about the mixup, but I'm a computer, not a
   psychic, you see.</p>
<form method=post action={url}/put>
    <label for=name>Name: </label>
    <input id=name name=name value="{name}" type=text>
    <input type=submit value=Submit>
</form>
<p>Alternatively, I can <a href={url}/delete>forget your name</a>.</p>"""
        # If the name is not set yet or deleted, the value will be None;
        # We need to change it to an empty value in this case to
        # avoid printing None on the webpage.
        resource_data['name'] = resource_data.get('name') or ""
        resource_data['url'] = resource.url
    else:
        raise LookupError("Resource not recognized")
    
    page = template.format(**resource_data)

    # All formatters must return a werkzeug response object
    return Response(page, status=status_code, headers=headers, 
                    content_type="text/html")

# See also findig.data.JSONFormatter
@app.formatter("application/json")
def format_json(status_code, headers, resource_data, resource):
    import json
    return Response(json.dumps(resource_data), status=status_code, 
                    headers=headers, content_type="application/json")


if __name__ == '__main__':
    run_simple('localhost', 5001, app, use_reloader=True, use_debugger=True)