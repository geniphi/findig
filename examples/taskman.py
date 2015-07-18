from datetime import datetime

from findig.extras.sql import SQLA, SQLASet
from findig.json import App
from findig.tools.validator import Validator
from sqlalchemy.schema import *
from sqlalchemy.types import *

app = App()
db = SQLA("sqlite:///tasks.sqlite", app=app)
validator = Validator(app)

class Task(db.Base):
    id = Column(Integer, primary_key=True)
    title = Column(String(150), nullable=False)
    desc = Column(String, nullable=True)
    due = Column(DateTime, nullable=False)

@validator.restrict("*title", "desc", "*due")
@validator.enforce(due=validator.datetime("%Y-%m-%d %H:%M:%S%z"))
@app.route("/tasks/<id>")
@app.resource(lazy=True)
def task(id):
    return tasks().fetch(id=id)

@validator.restrict("*title", "desc", "*due")
@validator.enforce(due=validator.datetime("%Y-%m-%d %H:%M:%S%z"))
@app.route("/tasks")
@task.collection(lazy=True)
def tasks():
    return SQLASet(Task)

if __name__ == '__main__':
    from werkzeug.serving import run_simple
    run_simple("localhost", 5000, app, use_reloader=True, use_debugger=False)
