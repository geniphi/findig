from tempfile import NamedTemporaryFile
from os.path import isfile

import pytest
from findig import App
from findig.context import ctx
from findig.resource import AbstractResource
from werkzeug.test import Client
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



def test_app_context_management(app):
    @app.context
    def temp_file():
        fobj = NamedTemporaryFile()
        yield fobj
        fobj.close()

    with app.build_context():
        # The first part of the context manager should have been run
        # by here
        temp_fobj = ctx.temp_file
        assert not temp_fobj.file.closed

    # Now that we leave the application context, expect
    # temp_fobj to be closed and for the context information to be
    # deleted.
    assert temp_fobj.file.closed
    assert not hasattr(ctx, 'temp_file')

def test_cleanup_hook(app):
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
    with app.build_context():
        items.extend([93, 3, 4, 5])
        with pytest.raises(ValueError):
            raise ValueError

    assert items == []

def test_late_cleanup_hook(app):
    # Test that cleanup hooks registered during a request
    # are run
    items = [48, 45, 34, 65]

    with app.build_context():
        app.cleanup_hook(items.clear)

    assert items == []