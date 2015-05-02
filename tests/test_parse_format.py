import pytest

from findig import App
from findig.content import *
from findig.context import ctx
from findig.wrappers import Request
from findig.utils import tryeach
from werkzeug.exceptions import NotAcceptable, UnsupportedMediaType
from werkzeug.test import Client, EnvironBuilder

@pytest.fixture
def app():
    app = App()
    app.route(lambda: {}, '/')
    return app

@pytest.mark.parametrize('accept,formatter_args,expected', [
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
    ),
    (
        # Check that the default match is used when accept header will
        # accept anything, and no other formatter can match.
        "application/json,*/*",
        [
            ["application/xml"],
        ],
        "application/xml",
    ),
    (
        # Check that the default match not used when the client
        # does not specify that it will accept anything
        "application/json",
        [
            ["application/xml", "text/json"],
        ],
        NotAcceptable,
    ),
    (
        # Check that the default match is used when there is no accept
        # header
        None,
        [
            ["application/json", "text/json"],
        ],
        "text/json",
    ),
])
def test_correct_formatter_is_selected(app, accept, formatter_args, expected):
    builder = EnvironBuilder(
        headers=[("Accept", accept)] if accept else None
    )

    formatters = []
    for fa in formatter_args:
        f = Formatter()
        for mime in fa:
            f.register(mime, lambda d: None, default=True)
        formatters.append(f)

    format = Formatter.compose(*formatters) \
             if len(formatters) > 1 else formatters[0]
    print (format.handlers)

    with app.build_context(builder.get_environ()):
        if isinstance(expected, type) and issubclass(expected, Exception):
            with pytest.raises(expected):
                print(format({}))
        else:
            mime, formatted = format({})
            assert mime == expected

@pytest.mark.parametrize('content_type,parser_args,expected,opts', [
    (
        # Returns the first formatter with the content type, if given
        "application/json;charset=utf-8",
        [
            ["text/json", "text/xml"],
            ["application/json"],
            ["application/json", "text/html"]
        ],
        "application/json",
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
        {},
    ),
    (
        # If a content-type is given, but no formatter is present,
        # raise unsupported media type (even when default formatter)
        'text/xml;charset=iso-8859-1;foo=bar',
        [
            ['application/json'],
            ['application/xml'],
        ],
        UnsupportedMediaType,
        {'charset': 'iso-8859-1', 'foo': 'bar'},
    ),
])
def test_correct_parser_chosen(app, content_type, parser_args, expected, opts):
    builder = EnvironBuilder(content_type=content_type)
    results = []

    parsers = []
    for pa in parser_args:
        p = Parser()
        for mime in pa:
            @p.register(mime)
            def do_parse(data, **opts):
                results.append(opts)
        parsers.append(p)

    parse = lambda s: tryeach(parsers, s)

    with app.build_context(builder.get_environ()):
        if isinstance(expected, type) and issubclass(expected, Exception):
            with pytest.raises(expected):
                print(parse(""))

        else:
            mime, parser = parse("")
            assert mime == expected
            assert opts == results.pop()

def test_formatter_decorator_factory(app):
    formatter = Formatter()

    @formatter.register("text/json")
    @formatter.register("application/json")
    def format_to_json(data):
        import json
        return json.dumps(data, indent=2)
    
    builder = EnvironBuilder(headers=[("Accept", "application/json")])
    with app.build_context(builder.get_environ()):
        assert formatter({'answer':42})[1] == '{\n  "answer": 42\n}'

def test_parser_decorator_factory(app):
    parser = Parser()

    @parser.register('application/json')
    def parse_json(data, **options):
        import json
        text = data.decode(options.get('charset', 'utf-8'))
        return json.loads(text)

    builder = EnvironBuilder(content_type="application/json;charset=cp424")
    with app.build_context(builder.get_environ()):
        mime, parsed = parser(b'\xc0\x7f\x81\x95\xa2\xa6\x85\x99\x7fz@\xf4\xf2\xd0')
        assert parsed['answer'] == 42


@pytest.mark.parametrize("obj,handler,mime,arg,expected", [
    (
        Formatter(),
        str,
        "text/plain", 
        {'foo': 'bar'},
        str({'foo': 'bar'}),
    ),
    (
        Parser(),
        lambda d, **opts: d.decode("utf8").upper(),
        "text/plain", 
        b"hello world",
        "HELLO WORLD",
    ),
])
def test_register_handler(obj, handler, mime, arg, expected, app):
    builder = EnvironBuilder(
        content_type=mime,
        headers=[("Accept", mime)],
    )

    def runtest():
        with app.build_context(builder.get_environ()):
            assert obj(arg) == (mime, expected)

    with pytest.raises((UnsupportedMediaType, NotAcceptable)):
        runtest()

    obj.register(mime, handler)

    runtest()

