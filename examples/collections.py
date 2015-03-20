# coding: utf8

from findig import App

app = App()

@app.route('/tasks/<int:id>')
@app.resource
def task(id):
    return db.gettaskbyid(id)

@app.route('/tasks/')
@task.collection
def task(id):
    for task in db.getnexttask():
        yield task

@tasks.model('update')
@tasks.model('create')
def put_task(task):
    db.puttask(task)

@tasks.model('delete')
def remove_task(**criteria):
    db.removetasks(criteria)


##################################

#tasks = Collection(adapter=SQLAAdapter(table))
task = Resource()
tasks = task.collection(adapter=SQLAAdapter(table))
app.route('/tasks/<int:id>', task)
app.route('/tasks', tasks)