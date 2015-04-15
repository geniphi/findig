import pytest

from werkzeug.routing import Rule

from findig.data_model import DictDataModel
from findig.dispatcher import Dispatcher
from findig.resource import Resource, AbstractResource

@pytest.fixture
def dispatcher():
    return Dispatcher()

@pytest.fixture
def resource():
    return Resource()

def test_resource_decorator(dispatcher):
    """Test the use of @resource as a decorator."""
    
    @dispatcher.resource
    def resource():
        return 10

    assert isinstance(resource, Resource)
    assert resource.name == "{}.{}.<locals>.resource".format(
        __name__,
        test_resource_decorator.__qualname__
        )

def test_resource_decorator_factory(dispatcher):
    """Test the use of @resource as a decorator factory."""

    @dispatcher.resource(name="resource")
    def resource():
        return 10

    assert isinstance(resource, Resource)
    assert resource.name == "resource"

def test_resource_builder(dispatcher):
    """Test the use of .resource() to create new resources from wrapped functions."""

    def func():
        return 42

    resource = dispatcher.resource(func, name="res")
    
    assert func is not resource
    assert isinstance(resource, Resource)
    assert resource.__wrapped__ is func
    assert resource.name == "res"

def test_route_decorator_factory(dispatcher):
    """Test the use of @route to register new routes."""

    @dispatcher.route("/first")
    @dispatcher.resource
    def first_resource():
        return True

    @dispatcher.route("/extra")
    @dispatcher.route("/second")
    def shortcut():
        return False

    url_map = {
        '/first': first_resource.name,
        '/second': shortcut.name,
        '/extra': shortcut.name,
        }

    rules = list(dispatcher.build_rules())

    assert len(rules) == len(url_map)

    for rule in rules:
        assert isinstance(rule, Rule)
        assert rule.rule in url_map
        assert rule.endpoint == url_map[rule.rule]


def test_route_builder(dispatcher, resource):
    """Test that .route() builds a URL rule correctly."""
    r = dispatcher.route(resource, '/route')

    assert r is resource
    rule = next(dispatcher.build_rules())
    assert isinstance(rule, Rule)
    assert rule.rule == "/route"
    assert rule.endpoint == resource.name

def test_method_warning(dispatcher, recwarn):
    """Test that passing a list of methods to .route() raises a 
    warning if the model does not support of the methods."""
    
    model = DictDataModel({
        'read': lambda: (),
        'delete': lambda: ()
        })
    dispatcher.route(dispatcher.resource(lambda: (), model=model), 
                     '/test', 
                     methods=['get', 'post', 'delete'])

    for rule in dispatcher.build_rules():
        if rule.rule == '/test':
            warning = recwarn.pop()
            assert set(map(str.lower, rule.methods)) == {'head', 'get', 'delete'}


#def test_dispatch(dispatcher):
#    request_objs = []

#    class TestResource(AbstractResource):
#        def __init__(self, name):
#            self.name = name
#            AbstractResource.__init__(self)
#        def get_supported_methods(self):
#            return {'GET'}
#        def handle_request(self, request, url_values):
#            assert url_values == {}

#    class TestResource2(AbstractResource):
#        def __init__(self, name):
#            self.name = name
#            AbstractResource.__init__(self)
#        def get_supported_methods(self):
#            return {'GET'}
#        def handle_request(self, request, url_values):
#            assert len(url_values) == 2
#            assert 'id' in url_values
#            assert 't' in url_values


#    test_resource = TestResource('test')
#    test_resource2 = TestResource2('test2')
#    dispatcher.route(test_resource, '/my_route')
#    dispatcher.route(test_resource2, '/items/<id>/<t>')