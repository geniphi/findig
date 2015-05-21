import pytest

from findig import App
from findig.resource import AbstractResource, Collection, Resource

@pytest.fixture
def app():
    return App()

def test_subclass_abstract():
    assert issubclass(Resource, AbstractResource)
    assert issubclass(Collection, AbstractResource)

def test_unique_name_generated():
    total =  100000 # seems like a reasonable amount
    names = {r.name for r in (Resource() for i in range(total))}
    assert len(names) == total

@pytest.mark.randomize()
def test_url_build(num:int, app):
    @app.route("/index/<int:num>")
    def item(num):
        pass

    with app.test_context(path="/index/1"):
        assert item.build_url(dict(num=num)) == "/index/{}".format(num)