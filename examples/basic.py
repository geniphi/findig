#-*- coding: utf-8 -*-

import json

from findig import App
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

app = App()
DATA = {}

@app.route("/greeting")
@app.resource
def greeter():
    return {"message": "Hello {0}!".format(DATA.get("name", "Findig"))}

@app.route("/data")
@app.resource
def data():
    return dict(DATA)

@data.model("write")
def update_data(res_data):
    DATA.clear()
    DATA.update(res_data)

@data.model("delete")
def delete_data(res_data):
    DATA.clear()

@app.formatter.register("application/json", default=True)
def format_data_json(d):
    return json.dumps(d)

@data.parser.register("application/json")
def parse_json_bytes(bs, **opts):
    return json.loads(bs.decode(opts.get("charset", "utf8")))

if __name__ == '__main__':
    run_simple('localhost', 5001, app, use_reloader=True, use_debugger=True)