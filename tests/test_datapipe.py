import pytest
from findig.utils import DataPipe


@pytest.mark.parametrize("val", [10, "Foo$&4fhs", None, 74.37473764])
def test_empty_noop(val):
    pipe = DataPipe()

    assert pipe(val) == val

def test_stage():
    pipe = DataPipe()

    @pipe.stage
    def mult_3(x):
        return x * 3

    assert pipe(3) == 9
    assert pipe(3) == 9 # this second check is to ensure no buildup

    pipe.stage(lambda x: x*3)

    assert pipe(3) == 27
    assert pipe(3) == 27