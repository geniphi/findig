import pytest

from findig.context import ctx
from findig.json import App
from findig.tools.counter import Counter
from werkzeug.test import Client


@pytest.fixture
def app():
    app = App()
    app.route(lambda: {},  "/")
    return app

@pytest.fixture
def client(app):
    return Client(app)

@pytest.fixture
def counter(app):
    return Counter(app)

def test_totals(client, counter):
    @counter.partition('method')
    def get_ip(request):
        # this gets called before the current request is counted
        return request.method.lower()

    for i in range(100):
        client.get("/")

    assert counter.hits().count() == 100
    assert counter.hits().count(method='get') == 100
    assert counter.hits().count(method='put') == 0
    assert counter.hits().count(foo='bar') == 0

def test_hit_iteration(client, counter):
    for i in range(100):
        client.get("/")

    hits = list(counter.hits())
    assert len(hits) == 100

def test_callbacks(client, counter):
    args = []
    @counter.every(2, after=2, until=6)
    def collect_args():
        args.append(ctx.request.args.to_dict())

    client.get("/")
    client.get("/?id=84")
    client.get("/?name=TJ") # yep
    client.get("/?id=46")
    client.get("/?name=TJD") # yep
    client.get("/?id=29")
    client.get("/?id=94")
    client.get("/?name=Rodgers")
    client.get("/?name=TJ")

    assert counter.hits().count() == 9
    assert len(args) == 2
    assert args == [{'name': 'TJ'}, {'name': 'TJD'}]

def test_callbacks_with_partitions(client, counter):
    results = {'any_team': [], 'specific_name': []}

    @counter.partition("name")
    def name(request):
        return request.args.get('name', '')

    @counter.partition("team")
    def team(request):
        return request.args.get('team', None)

    @counter.at(3, team=counter.any)
    def on_any_name_reaches_4(team):
        results['any_team'].append((team, ctx.request.args.get('name', '')))

    queries = [
        "?name=TJ",
        "?name=James&team=code",
        "?name=John&team=qa",
        "?name=Cindy&team=code",
        "?name=Jane&team=qa",
        "?name=Jane",
        "?name=John&team=code",
        "?name=Smithy&team=qa",
        "?name=Jennifer&team=code",
    ]

    for query in queries:
        client.get("/{}".format(query))

    assert len(results['any_team']) == 2
    assert results['any_team'] == [('code', 'John'), ('qa', 'Smithy')]
