import uuid

import pytest
from werkzeug.exceptions import *
from werkzeug.datastructures import MultiDict
from werkzeug.test import Client, EnvironBuilder

from findig.tools.validator import *
from findig.json import App
from findig.wrappers import Request


@pytest.fixture
def app():
    app = App()
    return app

@pytest.fixture
def client(app):
    return Client(app)

parametrize = pytest.mark.parametrize('spec,data,restrict,skip,expected', [
    (   # General test
        {'foo':int, 'bar':[int], 'baz':[str], 'ext':int},
        {'foo': '9', 'bar': ['49', '49', 2, '76'], 'baz': ['384', 'dju'], 'ext': 'newp'},
        ['*foo', 'bar', 'baz'], True,
        {'foo':9, 'bar': [49, 49, 2, 76], 'baz': ['384', 'dju']},
    ),
    (   # Test with extra fields not in spec
        {'foo':int},
        {'foo': '98', 'bar': 'open the door', 'baz': ['85', '58']},
        ['foo', 'bar', 'baz'], False,
        {'foo': 98, 'bar': 'open the door', 'baz': ['85', '58']},
    ),
    (
        # Test with extra fields in spec
        {'foo': int, 'baz': [int]},
        {'bar': 'open the door', 'baz': ['85', '58']},
        None, False,
        {'bar': 'open the door', 'baz': [85, 58]},
    ),
    (
        # Missing required fields
        {},
        {'bar': 'open sesame'},
        ['*foo', 'bar'], False,
        MissingFields
    ),
    (
        # Test with multi-dict
        {'foo': [int]},
        MultiDict([('foo', '5'), ('foo', '6'), ('foo', '7')]),
        ['foo', 'bar', 'baz'], False,
        MultiDict([('foo', 5), ('foo', 6), ('foo', 7)])
    ),
    (
        # Test with multi-dict with values in bad form
        {'foo': [int]},
        MultiDict([('foo', '5'), ('foo', '6fg'), ('foo', 'wf7')]),
        ['foo', 'bar', 'baz'], False,
        BadRequest
    ),
    (
        # Badly formed specification
        {'foo': 'dskjfhskdjfsdj'},
        {'foo': '98', 'bar': 'open the door', 'baz': ['85', '58']},
        ['foo', 'bar', 'baz'], False,
        InvalidSpecificationError,
    ),
    (
        # A specification with a named converter
        {'foo': 'uuid'},
        {'foo': '029b2439-b561-4ec8-bdf0-710b6148a70d', 'bar': 'door'},
        ['foo', 'bar', 'baz'], False,
        {'foo': uuid.UUID('029b2439-b561-4ec8-bdf0-710b6148a70d'), 'bar': 'door'}
    ),
    (
        # Another converter, but a failed match
        {'foo': 'any(john,jane)'},
        {'foo': 'harry', 'bar': 'john'},
        ['foo', 'bar', 'baz'], False,
        BadRequest
    ),
    (
        # Using a list containing a werkzeug converter
        {'foo': ['any(john,jane)']},
        MultiDict([('foo', 'john'), ('foo', 'jane'), ('foo', 'john')]),
        ['foo', 'bar', 'baz'], False,
        MultiDict([('foo', 'john'), ('foo', 'jane'), ('foo', 'john')]),
    ),
    #(
    #    # FIXME: This test currently fails.
    #    # Match string items with slashes in them
    #    {'foo': 'any(application/xml,application/json)', 'bar':'string(minlength=3)'},
    #    {'foo': 'application/xml', 'bar': 'text/html'},
    #    {'foo' : 'application/xml', 'bar': 'text/html'},
    #),
])

@parametrize
def test_validate_method(app, spec, data, restrict, skip, expected):
    validator = Validator(app)
    validator.enforce_all(**spec)

    @app.route("/")
    def resource():
        pass

    validator.enforce(resource, **spec)
    if restrict is not None:
        validator.restrict(resource, *restrict, strip_extra=skip)

    def runtest():
        with app.test_context(path="/"):
            if isinstance(expected, MultiDict):
                assert validator.validate(data).to_dict(flat=False) == expected.to_dict(flat=False)
            else:
                assert validator.validate(data) == expected

    # Validators only work inside a request
    if isinstance(expected, type) and issubclass(expected, Exception):
        with pytest.raises(expected):
            runtest()
    else:
        runtest()

@parametrize
def test_validation_process(app, spec, data, restrict, skip, expected):
    validator = Validator(app)
    validator.enforce_all(**spec)

    @app.route("/")
    def resource():
        pass

    if restrict is not None:
        validator.restrict(resource, *restrict, strip_extra=skip)

    def runtest():
        with app.test_context(path="/"):
            assert app.pre_processor(data) == expected

    if isinstance(expected, type) and issubclass(expected, Exception):
        with pytest.raises(expected):
            runtest()
    else:
        runtest()

def test_collection_inheritance(app):
    validator = Validator(app)

    @validator.enforce(foo=int)
    @validator.restrict('foo', strip_extra=True)
    @app.route("/<id>")
    def item(id):
        pass

    @app.route("/")
    @item.collection
    def items():
        pass

    with app.test_context(path="/"):
        assert validator.validate({"foo": "87", "bar": "strip me baby"}) == {"foo": 87}

def test_collection_inheritance_overide(app):
    validator = Validator(app)

    @validator.enforce(foo=int)
    @validator.restrict('foo', strip_extra=True)
    @app.route("/<id>")
    def item(id):
        pass

    @app.route("/")
    @validator.enforce(foo='uuid')
    @validator.restrict('foo', strip_extra=False)
    @item.collection
    def items():
        pass

    test_uuid = uuid.uuid4()

    with app.test_context(path="/"):
        with pytest.raises(UnexpectedFields):
            assert validator.validate({"foo": "87", "bar": "strip me baby"}) == {"foo": 87}

        assert validator.validate({"foo": str(test_uuid)}) == {"foo": test_uuid}
