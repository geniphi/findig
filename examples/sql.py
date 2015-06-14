from sqlalchemy.schema import *
from sqlalchemy.types import *
from werkzeug.serving import run_simple

from findig.json import App
from findig.extras.sql import SQLA, SQLASet

app = App()
db = SQLA("sqlite:///temp.db", app=app)


# Let's create a model for our API
class User(db.Base):
    id = Column(Integer, primary_key=True)
    name = Column(String(150), nullable=False)
    age = Column(Integer)

class Item(db.Base):
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)


@app.route("/users/<int:id>")
@app.resource(lazy=True)
def user(id):
    return users().fetch(id=id)

@app.route("/users/")
@user.collection(lazy=True)
def users():
    return SQLASet(User)


if __name__ == '__main__':
    run_simple('localhost', 5003, app, use_reloader=True, use_debugger=True)