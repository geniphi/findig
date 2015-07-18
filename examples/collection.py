#-*- coding: utf-8 -*-

from findig.json import App
from findig.extras.redis import RedisSet
from werkzeug.serving import run_simple

app = App(indent=2)

ITEMS = {} # Fake data store

@app.route("/items/<int:id>")
def item(id):
    return ITEMS[id]

@item.model("write")
def put_item(data, id):
    ITEMS[id] = data

@item.model("delete")
def delete_item(data, id):
    del ITEM[id]

################################
# Alternative using a data set #
################################

# See documentation for an explanation of data set collections,
# and why you should use them whenever possible.

@app.route('/tasks/<int:id>')
@app.resource(lazy=True)
def task(id):
    return tasks().fetch(id=id)

@app.route('/tasks/')
@task.collection(lazy=True, include_urls=True)
def tasks():
    # RedisSet is a DataSet instance, and so has an implicit
    # model that we do not need to specify; Findig already
    # knows how to use it to create, update and delete items.
    # You can return any DataSet instance here.
    return RedisSet('my-data-set')

if __name__ == '__main__':
    run_simple('localhost', 5002, app, use_reloader=True, use_debugger=True)