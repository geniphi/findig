#-*- coding: utf-8 *-*
import pytest
from findig.tools.dataset import *


class MockDataSet(MutableDataSet):
    def __init__(self):
        self.data = []
        self.iterated = False

    def add(self, data):
        return self.data.append(data)

    def __iter__(self):
        self.iterated = True
        yield from (MockRecord(d) for d in self.data)

class MockRecord(AbstractRecord):
    def __init__(self, d):
        self.d = d

    def read(self):
        return self.d

@pytest.fixture
def people():
    mds = MockDataSet()
    mds.add(dict(id=1, name="Te-jé Rodgers", age=25))
    mds.add(dict(id=2, name="John Smith", age=34))
    mds.add(dict(id=3, name="Terrance Riverdarb", age=16))
    mds.add(dict(id=4, name="Anna Harris", age=74))
    mds.add(dict(id=5, name="Jen Brathwaithe", age=32))
    mds.add(dict(id=6, name="Glen Posner", age=52))
    mds.add(dict(id=7, name="Harriet Peters", age=21))
    mds.add(dict(id=8, name="Anthony Simm", age=32))
    return mds

def test_fetch(people):
    assert people.fetch(id=3)['name'] == "Terrance Riverdarb"
    assert people.fetch(age=lambda a: a > 30)['id'] == 2 # conflicts resolved by getting the first one
    with pytest.raises(LookupError):
        people.fetch(name="Glen").get('id')

def test_filter(people):
    are_32 = people.filtered(age=32)
    assert not people.iterated
    assert isinstance(are_32, AbstractDataSet)
    assert len(list(are_32)) == 2
    assert list(are_32)[0]['id'] == 5
    assert list(are_32)[1]['id'] == 8

    are_40 = people.filtered(age=40)
    assert isinstance(are_40, AbstractDataSet)
    assert len(list(are_40)) == 0

    t_names = people.filtered(name=lambda n: n.startswith("T"))
    assert len(list(t_names)) == 2
    assert list(t_names)[0]['id'] == 1
    assert list(t_names)[1]['id'] == 3

def test_limit(people):
    first_4 = people.limit(4)
    assert not people.iterated
    assert isinstance(first_4, AbstractDataSet)
    assert [r['id'] for r in first_4] == [1, 2, 3, 4]

def test_limit_with_offset(people):
    middle_4 = people.limit(4, offset=2)
    assert not people.iterated
    assert isinstance(middle_4, AbstractDataSet)
    assert [r['id'] for r in middle_4] == [3, 4, 5, 6]

def test_limit_beyond_items(people):
    first_100 = people.limit(100)
    assert [r['id'] for r in first_100] == [r['id'] for r in people]

@pytest.mark.parametrize('sort_param, expected', [
    ('name', [4,8,6,7,5,2,1,3]),
    ('id', [1,2,3,4,5,6,7,8]),
    ('age', [3,7,1,5,8,2,6,4]),
])
def test_sort_param(people, sort_param, expected):
    sorted_set = people.sorted(sort_param)
    assert not people.iterated
    assert isinstance(sorted_set, AbstractDataSet)
    assert [r['id'] for r in sorted_set] == expected

@pytest.mark.parametrize('sort_param, expected', [
    ('name', [3,1,2,5,7,6,8,4]),
    ('id', [8,7,6,5,4,3,2,1]),
    ('age', [4,6,2,5,8,1,7,3]),
])
def test_sort_param_descending(people, sort_param, expected):
    sorted_set = people.sorted(sort_param, descending=True)
    assert not people.iterated
    assert isinstance(sorted_set, AbstractDataSet)
    assert [r['id'] for r in sorted_set] == expected

def test_sort_func(people):
    sorted_set = people.sorted(lambda r: r['id'] * -1)    
    assert not people.iterated
    assert isinstance(sorted_set, AbstractDataSet)
    assert [r['id'] for r in sorted_set] == [8,7,6,5,4,3,2,1]

def test_sort_multi(people):
    sorted_set = people.sorted('age', 'name')
    assert not people.iterated
    assert isinstance(sorted_set, AbstractDataSet)
    assert [r['id'] for r in sorted_set] == [3,7,1,8,5,2,6,4]