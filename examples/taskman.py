from findig.json import App
from sqlalchemy.schema import *
from sqlalchemy.types import *
from findig.extras.sql import SQLA, SQLASet

app = App()
db = SQLA("sqlite:///tasks.sqlite", app=app)

class Task(db.Base):
    id = Column(Integer, primary_key=True)
    title = Column(String(150), nullable=False)
    desc = Column(String, nullable=True)
    due = Column(DateTime, nullable=False)

def check_

@app.route("/tasks/<id>")
@app.resource
def task(id):
    return tasks().fetch(id=id)

@app.route("/tasks")
@task.collection(lazy=True)
def tasks():
    return SQLASet(Task)

if __name__ == '__main__':
    from werkzeug.serving import run_simple
    run_simple("localhost", 5000, app, use_reloader=True, use_debugger=False)
