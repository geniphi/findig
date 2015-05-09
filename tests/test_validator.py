import uuid

import pytest
from werkzeug.exceptions import *
from werkzeug.datastructures import MultiDict
from werkzeug.test import Client, EnvironBuilder

from findig.validator import InvalidSpecificationError, Validator
from findig.json import App
from findig.wrappers import Request


@pytest.fixture
def app():
    app = App()
    return app

@pytest.fixture
def client(app):
    return Client(app)

@pytest.fixture
def request_context(app):
    app.route(lambda:None, "/")
    builder = EnvironBuilder("/")

    return app.build_context(builder.get_environ())

parametrize = pytest.mark.parametrize('spec,data,expected', [
    (   # General test
        {'foo':int, 'bar':[int], 'baz':[str]},
        {'foo': '9', 'bar': ['49', '49', 2, '76'], 'baz': ['384', 'dju']},
        {'foo':9, 'bar': [49, 49, 2, 76], 'baz': ['384', 'dju']},
    ),
    (   # Test with extra fields not in spec
        {'foo':int},
        {'foo': '98', 'bar': 'open the door', 'baz': ['85', '58']},
        {'foo': 98, 'bar': 'open the door', 'baz': ['85', '58']},
    ),
    (
        # Test with missings fields
        {'foo': int, 'baz': [int]},
        {'bar': 'open the door', 'baz': ['85', '58']},
        BadRequest,
    ),
    (
        # Test with multi-dict
        {'foo': [int]},
        MultiDict([('foo', '5'), ('foo', '6'), ('foo', '7')]),
        MultiDict([('foo', 5), ('foo', 6), ('foo', 7)])
    ),
    (
        # Test with multi-dict with values in bad form
        {'foo': [int]},
        MultiDict([('foo', '5'), ('foo', '6fg'), ('foo', 'wf7')]),
        BadRequest
    ),
    (
        # Badly formed specification
        {'foo': 'dskjfhskdjfsdj'},
        {'foo': '98', 'bar': 'open the door', 'baz': ['85', '58']},
        InvalidSpecificationError,
    ),
    (
        # A specification with a named converter
        {'foo': 'uuid'},
        {'foo': '029b2439-b561-4ec8-bdf0-710b6148a70d', 'bar': 'door'},
        {'foo': uuid.UUID('029b2439-b561-4ec8-bdf0-710b6148a70d'), 'bar': 'door'}
    ),
])

@parametrize
def test_validate_method(request_context, spec, data, expected):
    validator = Validator()
    validator.enforce_all(**spec)

    # Validators only work inside a request
    with request_context:
        if isinstance(expected, type) and issubclass(expected, Exception):
            with pytest.raises(expected):
                assert validator.validate(data) == expected
        elif isinstance(expected, MultiDict):
            assert validator.validate(data).to_dict(flat=False) == expected.to_dict(flat=False)
        else:
            assert validator.validate(data) == expected

@parametrize
def test_validation_process(app, request_context, spec, data, expected):
    validator = Validator(app)
    validator.enforce_all(**spec)   

    with request_context:
        if isinstance(expected, type) and issubclass(expected, Exception):
            with pytest.raises(expected):
                assert app.pre_processor(data) == expected
        else:
            assert app.pre_processor(data) == expected