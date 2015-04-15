import pytest

from findig.resource import AbstractResource, Collection, Resource


def test_subclass_abstract():
    assert issubclass(Resource, AbstractResource)
    assert issubclass(Collection, AbstractResource)

def test_unique_name_generated():
    total =  100000 # seems like a reasonable amount
    names = {r.name for r in (Resource() for i in range(total))}
    assert len(names) == total