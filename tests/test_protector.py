import pytest

from findig.context import ctx
from findig.json import App
from findig.resource import Resource
from findig.tools.protector import *
from werkzeug.test import Client
from werkzeug.wrappers import BaseResponse

@pytest.fixture
def app():
    return App()

@pytest.fixture
def protector(app):
    return Protector(app)

scope_guards = [
    [[]],
    [["scope1"]],
    [["scope2", "scope3"], ["scope1"]]
]

@pytest.mark.parametrize("scope_guards", scope_guards)
def test_guard_function(scope_guards, app, protector):
    res = Resource()

    for scopes in scope_guards:
        protector.guard(res, *scopes)

    assert protector._guard_specs[res.name] == scope_guards

    with app.test_context(create_route=True):
        ctx.resource = res
        with pytest.raises(Unauthorized):
            next(protector.auth())

@pytest.mark.parametrize("scope_guards", scope_guards)
def test_guard_decorator_factory(scope_guards, app, protector):
    if len(scope_guards) == 2:
        @protector.guard(*scope_guards[1])
        @protector.guard(*scope_guards[0])
        @app.route("/test")
        def res():
            pass

    else:
        @protector.guard(*scope_guards[0])
        @app.route("/test")
        def res():
            pass

    assert protector._guard_specs[res.name] == scope_guards

    with app.test_context(create_route=True):
        ctx.resource = res
        with pytest.raises(Unauthorized):
            next(protector.auth())

def test_guard_decorator(app, protector):
    @protector.guard
    @app.route("/")
    def res():
        pass

    assert protector._guard_specs[res.name] == [[]]

    with pytest.raises(Unauthorized):
        with app.test_context():
            pass

@pytest.mark.parametrize("username,password,auth_header,passes", [
    (
        'Aladdin', 'open sesame',
        'Basic QWxhZGRpbjpvcGVuIHNlc2FtZQ==',
        True
    ),
    (
        'username', 'password',
        'Basic QWxhZGRpbjpvcGVuIHNlc2FtZQ==',
        False
    ),
    (
        'Aladdin', 'open sesame',
        None,
        False
    ),
    (
        'Aladdin', 'open sesame',
        "",
        False
    )
])
def test_basic_protector(username, password, auth_header, passes, app):
    protector = BasicProtector(app)
    
    @protector.guard
    @app.route("/")
    def res():
        return {}

    @protector.auth_func
    def auth(usn, pwd):
        print(usn, username, password, pwd)
        return username==usn and password==pwd

    errors = []

    @app.error_handler.register(Unauthorized)
    def handle_unauthorized(err):
        errors.append(err)
        response = err.get_response()
        assert "WWW-Authenticate" in response.headers
        return response

    client = Client(app)
    if auth_header is None:
        client.get("/")
    else:
        client.get("/", headers=[("Authorization", auth_header)])

    assert passes == (not errors)
