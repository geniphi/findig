from abc import ABCMeta, abstractmethod
from collections.abc import Callable, Iterable
from functools import reduce


class DataPipe:
    def __init__(self, *funcs):
        self.funcs = []

        for func in funcs:
            if isinstance(func, DataPipe):
                self.funcs.extend(func)
            elif isinstance(func, Iterable):
                self.funcs.extend(func)
            elif isinstance(func, Callable):
                self.funcs.append(func)

    def stage(self, func):
        self.funcs.append(func)
        return func

    def __call__(self, data):
        return reduce(lambda x, f: f(x), self.funcs, data)