#-*- coding: utf-8 -*-
from findig.extras.redis import *
from findig.extras.redis import IndexToken
from fakeredis import FakeStrictRedis
import pytest


@pytest.fixture
def redis():
    return FakeStrictRedis()

@pytest.fixture
def rs(request):
    redis_set = RedisSet("mock-collection", client=FakeStrictRedis())
    redis_set.add(dict(id=1, name="Te-jé Rodgers", age=25))
    redis_set.add(dict(id=2, name="John Smith", age=34))
    redis_set.add(dict(id=3, name="Terrance Riverdarb", age=16))
    redis_set.add(dict(id=4, name="Anna Harris", age=74))
    redis_set.add(dict(id=5, name="Jen Brathwaithe", age=32))
    redis_set.add(dict(id=6, name="Glen Posner", age=52))
    redis_set.add(dict(id=7, name="Harriet Peters", age=21))
    redis_set.add(dict(id=8, name="Anthony Simm", age=32))
    redis_set.add(dict(id=9, name="שלום привет hello", age=49))
    redis_set.add(dict(id=10, name=b"Jabba", age=18))
    request.addfinalizer(redis_set.clear)
    return redis_set

def test_index_token_hash():
    tok1 = IndexToken(dict(id=1, name="Jen"))
    tok2 = IndexToken(dict(id=1, name="Jen"))
    assert tok1 == tok2

def test_type_preserved(rs):
    person = rs.fetch(id=4)
    assert isinstance(person['age'], int)
    assert isinstance(person['name'], str)
    assert isinstance(rs.fetch(id=10)['name'], bytes)

def test_smooth_text_coding(rs):
    person = rs.fetch(id=9)
    assert person['name'] == "שלום привет hello"

def test_patch_record(rs):
    rs.fetch(id=10).patch(dict(id=10, name="Cartman", state="CO"), ('age',))
    record = rs.fetch(id=10)
    assert 'age' not in record
    assert record['name'] == "Cartman"
    assert record['state'] == "CO"

def test_update_record(rs):
    rs.fetch(id=10).update(name="Carrie Goldman", state="MA")
    record = rs.fetch(id=10)
    assert dict(record) == dict(id=10, age=18, state="MA", name="Carrie Goldman")

def test_iter(rs):
    assert {r['id'] for r in rs} == set(range(1, 11))

def test_clear(redis, rs):
    rs.clear()
    assert list(rs) == []
    assert redis.zcard(rs.colkey) == 0
    assert redis.zcard(rs.indkey) == 0
    assert not redis.get(rs.incrkey)