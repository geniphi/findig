import pytest

from findig import App
from findig.content import *
from findig.context import ctx
from findig.wrappers import Request
from werkzeug.exceptions import NotAcceptable, UnsupportedMediaType
from werkzeug.test import EnvironBuilder


@pytest.mark.parametrize('accept,formatter_args,expected,idx', [
    (
        # Check that best match is returned even other matches appear
        # before the best match
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        [
            ["application/json", "application/xml"], # contains match
            ["text/html"], # best match
            ["text/json"]
        ],
        "text/html",
        1
    ),
    (
        # Check that the default match is used when accept header will
        # accept anything, and no other formatter can match.
        "application/json,*/*",
        [
            ["default"],
            ["application/xml", "text/json"],
            ["text/xml"],
        ],
        "default",
        0
    ),
    (
        # Check that the default match not used when the client
        # does not specify that it will accept anything
        "application/json",
        [
            ["default"],
            ["application/xml", "text/json"],
        ],
        NotAcceptable,
        0
    ),
    (
        # Check that the default match is used when there is no accept
        # header
        None,
        [
            ["default"],
            ["application/json", "text/json"],
        ],
        "default",
        0
    ),
    (
        # Check that a value error is raised when no viable formatters are
        # present for a request that will accept any content type.
        None,
        [
        ],
        ValueError,
        0
    ),
])
def test_formatter_resolution(accept, formatter_args, expected, idx):
    builder = EnvironBuilder(headers=[("Accept", accept)] if accept else None)
    ctx.request = builder.get_request(Request)

    formatters = []
    for fa in formatter_args:
        f = Formatter()
        for handler in fa:
            f.register_handler(handler, lambda: None)
        formatters.append(f)

    if isinstance(expected, type) and issubclass(expected, Exception):
        with pytest.raises(expected):
            print(AbstractFormatter.resolve(*formatters))

    else:
        mime, formatter = AbstractFormatter.resolve(*formatters)
        assert mime == expected
        assert formatter is formatters[idx]

@pytest.mark.parametrize('content_type,parser_args,expected,idx,opts', [
    (
        # Returns the first formatter with the content type, if given
        "application/json;charset=utf-8",
        [
            ["text/json", "text/xml"],
            ["application/json"],
            ["application/json", "text/html"]
        ],
        "application/json",
        1,
        {'charset': 'utf-8'}
    ),
    (
        # If no content type is given, and no 'default' formatter is
        # available, raise UnsupportedMediaType
        None,
        [
            ["text/json", "application/json"],
        ],
        UnsupportedMediaType,
        0,
        {},
    ),
    (
        # If no content type is given, return the first default formatter
        # present.
        None,
        [
            ["application/json", "default"],
            ["default"],
            ["application/json"]
        ],
        "default",
        0,
        {},
    ),
    (
        # If a content-type is given, but no formatter is present,
        # raise unsupported media type (even when default formatter)
        'text/xml;charset=iso-8859-1;foo=bar',
        [
            ['application/json', 'default'],
            ['application/xml'],
        ],
        UnsupportedMediaType,
        0,
        {'charset': 'iso-8859-1', 'foo': 'bar'},
    ),
])
def test_parser_resolution(content_type, parser_args, expected, idx, opts):
    builder = EnvironBuilder(content_type=content_type)
    ctx.request = builder.get_request(Request)

    parsers = []
    for pa in parser_args:
        p = Parser()
        for mime in pa:
            p.register_handler(mime, lambda:None)
        parsers.append(p)

    if isinstance(expected, type) and issubclass(expected, Exception):
        with pytest.raises(expected):
            print(AbstractParser.resolve(*parsers))

    else:
        mime, opts, parser = AbstractParser.resolve(*parsers)
        assert mime == expected
        assert parsers[idx] is parser
        assert opts == opts

def test_interfaces():
    assert isinstance(Parser(), AbstractParser)
    assert isinstance(Formatter(), AbstractFormatter)

def test_formatter_decorator_factory():
    formatter = Formatter()

    assert 'text/json' not in formatter.get_supported_mimes()
    assert 'application/json' not in formatter.get_supported_mimes()

    @formatter("text/json")
    @formatter("application/json")
    def format_to_json(data):
        import json
        return json.dumps(data)

    assert 'text/json' in formatter.get_supported_mimes()
    assert 'application/json' in formatter.get_supported_mimes()
    assert formatter.format('application/json', {'answer':42}) == '{"answer": 42}'

def test_parser_decorator_factory():
    parser = Parser()

    assert 'application/json' not in parser.get_supported_mimes()

    @parser('application/json')
    def parse_json(data, **options):
        import json
        text = data.decode(options.get('charset', 'utf-8'))
        return json.loads(text)

    assert 'application/json' in parser.get_supported_mimes()
    assert parser.parse(
        'application/json',
        {'charset': 'cp424'},
        b'\xc0\x7f\x81\x95\xa2\xa6\x85\x99\x7fz@\xf4\xf2\xd0'
    )['answer'] == 42

@pytest.mark.parametrize("obj,funcname,handler,args,expected", [
    (
        Formatter(),
        "format",
        str,
        ("text/plain", {'foo': 'bar'}),
        str({'foo': 'bar'}),
    ),
    (
        Parser(),
        "parse",
        lambda d, **opts: d.decode("utf8").upper(),
        ("text/plain", {}, b"hello world"),
        "HELLO WORLD",
    ),
])
def test_register_handler(obj, funcname, handler, args, expected):
    assert args[0] not in obj.get_supported_mimes()
    with pytest.raises(KeyError):
        func = getattr(obj, funcname)
        assert func(*args) == expected

    obj.register_handler(args[0], handler)

    assert args[0] in obj.get_supported_mimes()
    func = getattr(obj, funcname)
    assert func(*args) == expected

def test_formatter_default_handler_not_fallback():
    formatter = Formatter()

    assert 'default' not in formatter.get_supported_mimes()    
    with pytest.raises(KeyError):
        assert formatter.format('text/plain', {'answer': 42}) == str({'answer': 42})

    formatter.register_handler('default', str)

    assert 'default' in formatter.get_supported_mimes()
    with pytest.raises(KeyError):
        assert formatter.format('text/plain', {'answer': 42}) == str({'answer': 42})


