from os.path import dirname

from findig import App
from findig.extras import JinjaFormatter
from werkzeug.exceptions import HTTPException
from werkzeug.serving import run_simple


# This example uses Jinja2 for templating, which needs jinja2 installed
# to work. Other file-based templating engines can be supported by 
# subclassing the general purpose findig.data.TemplateFormatter.
app = App(
    formatter=JinjaFormatter(dirname(__file__))
)

# By default, TemplateFormatter will search its search path for a 
# template a filename that matches the resource name (ignoring the
# file extension). In this case, it will find 'index.html' in 
# examples/templates.
@app.route("/")
@app.resource(name="index")
def index():
    return {}

# TemplateFormatter also provides a decorator for naming a template
# for a particular resource.
@app.formatter.template("info.html")
@app.route("/about")
def info():
    import jinja2
    import werkzeug
    import sys
    return {
        "jinja_version": jinja2.__version__,
        "werkzeug_version": werkzeug.__version__,
        "python_version": ".".join(map(str, sys.version_info[:3])),
        "template_path": app.formatter.search_path[0],
    }

# We can also set up the application to render error pages from
# a template.
@app.exceptions.on(Exception)
def format_exception(e, exc_type, message, traceback):
    import traceback
    traceback.print_exc()
    args = {"title": "Internal Server Error", 
            "message": "The server cannot process your request because of "
                       "an internal error."}
    return app.formatter.render_template(
        "error.html", args, 500, {"Content-Type": "text/html"})

@app.exceptions.on(HTTPException)
def format_http_exception(e, exc_type, message, traceback):
    args = {"title": e.name, "message": e.description}
    return app.formatter.render_template(
        "error.html", args, e.code, dict(e.get_headers()))

if __name__ == '__main__':
     run_simple('localhost', 5002, app, use_reloader=True, use_debugger=True)