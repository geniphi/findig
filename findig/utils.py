from abc import ABCMeta, abstractmethod
from collections.abc import Callable, Iterable
from functools import reduce
import re


# stackoverflow.com/questions/elegant-python-function-to-convert-camelcase-to-camel-case/1176023#1176023
def to_snake_case(name):
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


class extremum:
    """
    A class whose instances are always ordered at one extreme.

    :param direction: If positive, always order as greater than every
                      other object. If negative, orders as less than
                      every other object.
    """
    def __init__(self, direction=1):
        self.gt = direction >= 0

    def __eq__(self, other):
        if isinstance(other, extremum) and other.gt == self.gt:
            return True
        else:
            return False

    def __gt__(self, other):
        if isinstance(other, extremum) and other.gt:
            return False
        else:
            return self.gt

    def __lt__(self, other):
        if isinstance(other, extremum) and not other.gt:
            return False
        else:
            return not self.gt


def tryeach(funcs, *args, **kwargs):
    """
    Call every item in a list a functions with the same arguments,
    until one of them does not throw an error. If all of the functions
    raise an error, then the error from the last function will be
    re-raised.

    :param funcs: An iterable of callables.

    """
    # Call every item in the list with the arguments given until
    # one of them /does not/ raise an error. If all of the items
    # raise an error, the very last error raised will re re-raised.

    funcs = list(funcs)
    last_index = len(funcs) - 1

    if not funcs:
        raise ValueError("Argument 1: must be a non-empty iterable "
                         "of functions.")

    for i, func in enumerate(funcs):
        try:
            return func(*args, **kwargs)
        except:
            if i == last_index:
                # If we are on the last function, raise the error
                raise


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
