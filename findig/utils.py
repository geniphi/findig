

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
