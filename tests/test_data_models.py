import pytest

from findig.data_model import *


def test_data_model_compose():
    """Test that a data model can correctly compose another."""
    model1 = DictDataModel({
        'read': lambda:(),
        'write': lambda:(),
        })

    model2 = DictDataModel({
        'read': lambda:(),
        'write': lambda:(),
        'delete': lambda: (),
        })

    model3 = model1.compose(model2)
    assert isinstance(model3, AbstractDataModel)
    assert sorted(model3) == ['delete', 'read', 'write']
    assert model3['read'] is model1['read']
    assert model3['write'] is model1['write']
    assert model3['delete'] is model2['delete']

def test_subclass_with_op_methods():
    """Test that an AbstractDataModel can be subclassed with method names
    that correspond to data operations.
    """
    class TestModel(AbstractDataModel):
        def test():
            """This test method should not be included."""
        def read():
            """This method should be included, because 'read' is a valid
            operation."""
        def write():
            """This should be included too, even though the signature is
            incorrect."""

    test_model = TestModel()
    assert isinstance(test_model, AbstractDataModel)
    assert 'test' not in test_model
    assert 'read' in test_model
    assert 'write' in test_model
    assert test_model['read'] == test_model.read
    assert test_model['write'] == test_model.write
    assert len(test_model) == 2

    with pytest.raises(KeyError):
        _ = test_model['test']

    with pytest.raises(TypeError):
        test_model['test'] = test_model['read']


def test_data_model_decorator():
    """Test that DataModel instances can be used as decorators to register 
    new model functions."""
    model = DataModel()

    @model("read")
    def reader():
        pass

    with pytest.raises(ValueError):
        @model("test") # Test is not a valid data operation
        def tester():
            pass

    assert "read" in model
    assert model["read"] is reader

def test_data_model_mut_map():
    """
    Test that DataModel can be used as a mutable mapping of operations
    to functions implementing them.
    """
    model = DataModel()

    with pytest.raises(KeyError):
        maker =  model['make']

    with pytest.raises(ValueError):
        model['foo'] = lambda: () # 'foo' isn't a valid data operation

    reader = lambda: ()
    model['read'] = reader
    model['make'] = reader
    model['make'] = lambda: ()

    assert 'read' in model
    assert 'make' in model
    assert model['read'] is reader
    assert model['make'] is not reader

    del model['read']

    with pytest.raises(KeyError):
        maker = model['read']