from abc import ABCMeta, abstractmethod
from collections.abc import Callable, Iterable
from functools import reduce


class DataPipe:
    """
    An object that folds data over a set of functions.

    :param funcs: A variable list of functions. Each function must take
        one parameter and return a single value.

    Calling this object with data will pass the data through each one of
    the functions that is has collected, using the result of one function
    as the argument for the next function. For example, if the data pipe
    ``dpipe`` contains the functions ``[f1, f2, ..., fn]``, then 
    ``dpipe(data)`` is equivalent to ``fn(...(f2(f1(data))))``.

    """
    def __init__(self, *funcs):
        self.funcs = []

        for func in funcs:
            if isinstance(func, DataPipe):
                self.funcs.extend(func.funcs)
            elif isinstance(func, Iterable):
                self.funcs.extend(func)
            elif isinstance(func, Callable):
                self.funcs.append(func)

    def stage(self, func):
        """
        Append a function to the data pipes internal list.

        This returns the function that it is called with, so it can be
        used as a decorator.

        """
        self.funcs.append(func)
        return func

    def __call__(self, data):
        return reduce(lambda x, f: f(x), self.funcs, data)