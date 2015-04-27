#-*- coding: utf-8 -*-

from findig.json import App
from findig.extras.redis import RedisSet
from werkzeug.serving import run_simple

app = App(indent=2)

#TASKS = {} # Fake data store

#@app.route('/tasks/<int:id>')
#@app.resource
#def task(id):
#    return tasks.model.dataset.fetch(id=id)

#@app.route('/tasks/')
#@task.collection(key='id')
#def tasks():
#    return (task for task in TASKS)

#@tasks.model('update')
#@tasks.model('create')
#def put_task(res):
#    if not hasattr(res, 'id'):
#        res.id = id(res) #stupid hack; don't do this

#    task = dict(res)
#    TASKS[res.id] = task

#@tasks.model('delete')
#def remove_task(res):
#    del TASKS[res.id]


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