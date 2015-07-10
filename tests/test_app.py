from tempfile import NamedTemporaryFile
from os.path import isfile

import pytest
from findig import App
from findig.context import ctx
from findig.resource import AbstractResource
from werkzeug.test import Client, EnvironBuilder
from werkzeug.wrappers import BaseResponse


@pytest.fixture
def app():
    # Create a fake app with one working route.
    class TestResource(AbstractResource):
        def get_supported_methods(self):
            return {'GET'}
        def handle_request(self, request, url_values):
            assert request.method == 'GET'
            assert url_values == {}
            return BaseResponse("test data")

    res = TestResource()
    res.name = "test"

    app = App()
    app.route(res, "/test")
    return app

@pytest.fixture
def environ():
    builder = EnvironBuilder(path="/test")
    return builder.get_environ()


def test_context_error(app, environ):
    @app.context
    def error_func():
        raise ValueError
        yield

    with pytest.raises(ValueError):
        with app.build_context(environ):
            print()

def test_context_error_propagates(app, environ):
    # The Protector relies on any errors being raised by a request 
    # context manager being propagated all the way to the application
    # error handler. Should these test cases fail, then the Protector
    # will fail to do its job.
    class CustomErrorClass(Exception):
        pass

    err = CustomErrorClass()
    tracked = []

    @app.context
    def error_func():
        raise err
        yield

    @app.error_handler.register(CustomErrorClass)
    def track_error(e):
        tracked.append(e)
        return BaseResponse("Foo")

    client = Client(app)
    client.open(environ)

    assert tracked == [err]

def test_app_context_management(app, environ):
    @app.context
    def temp_file():
        fobj = NamedTemporaryFile()
        yield fobj
        fobj.close()

    with app.build_context(environ):
        # The first part of the context manager should have been run
        # by here
        temp_fobj = ctx.temp_file
        assert not temp_fobj.file.closed

    # Now that we leave the application context, expect
    # temp_fobj to be closed and for the context information to be
    # deleted.
    assert temp_fobj.file.closed
    assert not hasattr(ctx, 'temp_file')

def test_cleanup_hook(app, environ):
    items = [49, 48, 43, 42]

    @app.cleanup_hook
    def clear_items():
        items.clear()

    c = Client(app)

    assert len(items) == 4
    
    c.get('/test')
    assert items == []

    # Check that even after a request that throws an error during processing,
    # cleanup hooks still get called
    with app.build_context(environ):
        items.extend([93, 3, 4, 5])
        with pytest.raises(ValueError):
            raise ValueError

    assert items == []

def test_late_cleanup_hook(app, environ):
    # Test that cleanup hooks registered during a request
    # are run
    items = [48, 45, 34, 65]

    with app.build_context(environ):
        app.cleanup_hook(items.clear)

    assert items == []