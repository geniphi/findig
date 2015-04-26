import random
import string
import sys

from findig.utils import *


def test_extremum():
    assert not extremum() > extremum()
    assert not extremum(-1) < extremum(-1)
    assert extremum() == extremum()
    assert extremum(-1) == extremum(-1)
    assert extremum() > extremum(-1)
    assert extremum(-1) < extremum()
    
    items = [sys.maxsize, sys.maxsize * -1, None, 
             random.randint(sys.maxsize * -1, sys.maxsize),
             "".join(random.sample(string.printable, random.randint(5, 25)))]

    for item in items:
        assert extremum() > item
        assert item < extremum()
        assert item > extremum(-1)
        assert extremum(-1) < item