from collections.abc import Callable, Mapping, Sequence
from uuid import UUID 

from werkzeug.datastructures import MultiDict
from werkzeug.exceptions import BadRequest

from findig.context import ctx
from findig.datapipe import DataPipe


class Validator:
    def __init__(self, dispatcher=None):
        self.converters = {
            'int': int, 'float': float, 'str': str, 'uuid': UUID,
        }
        self.validation_specs = {}

        if dispatcher is not None:
            self.attach_to(dispatcher)

    def attach_to(self, dispatcher):
        # Hook the validator into the dispatcher's data pre processor
        # so that we can look at incoming request data and complain
        # if the request data doesn't match what we're looking for
        dispatcher.pre_processor = DataPipe(dispatcher.pre_processor, self.validate)

    def enforce(self, *args, **validator_spec):
        def decorator(resource):
            self.validation_specs[resource.name] = validator_spec
            return resource

        if len(args) == 0:
            return decorator
        elif len(args) == 1:
            return decorator(resource)
        else:
            raise TypeError

    def enforce_all(self, **validator_spec):
        self.validation_specs[None] = validator_spec

    def __check_item(self, data, key, item_spec):
        # '89', int -> pass
        # ['58', '84', '58'], [int] -> pass
        # ['89', 'foo', '59'], [int] -> fail
        # ['89', 'foo', '59'], [str] -> pass
        if isinstance(item_spec, Callable):
            # Easiest case: call the callable on the item data
            # to get the converted answer:
            return item_spec(data[key])

        elif isinstance(item_spec, list):
            if len(item_spec) != 1:
                raise InvalidSpecificationError(item_spec)

            unconverted_items = _ContainerWrapper(data.getlist(key))
            converted_items = []
            child_spec = item_spec[0]
            for i, _ in enumerate(unconverted_items):
                converted_items.append(
                    self.__check_item(unconverted_items, i, child_spec)
                )
            return converted_items
        elif item_spec in self.converters:
            item_spec = self.converters[item_spec]
            return self.__check_item(data, key, item_spec)

        else:
            raise InvalidSpecificationError(item_spec)

    def validate(self, data):
        conversion_spec = {}
        conversion_spec.update(self.validation_specs.get(None, {}))
        conversion_spec.update(self.validation_specs.get(ctx.resource.name, {}))

        wrapped = _ContainerWrapper(data)

        conversion_errs = []

        # Transform the data according to the conversion spec
        for field, field_spec in conversion_spec.items():
            try:
                converted = self.__check_item(wrapped, field, field_spec)
            except InvalidSpecificationError:
                raise
            except:
                import traceback
                traceback.print_exc()
                conversion_errs.append(field)
            else:
                wrapped[field] = converted

        if conversion_errs:
            raise BadRequest(conversion_errs)
        else:
            return wrapped.unwrap()

class _ContainerWrapper:
    def __init__(self, container):  
        self._direct = False
        self._orig = container
        self._is_multidict = False
            
        if isinstance(container, Sequence):
            self._c = list(container)

        elif isinstance(container, MultiDict):
            self._is_multidict = True
            self._list_fields = set()
            self._c = container.copy()

        elif isinstance(container, Mapping):
            self._c = dict(container)

        else:
            self._c = container
            self._direct = True

    def __getitem__(self, key):
        if self._direct:
            return getattr(self._c, key)
        else:
            return self._c[key]

    def getlist(self, key):
        if self._is_multidict:
            l = self._c.getlist(key)
            self._list_fields.add(key)
            return l
        else:
            l = self[key]
            if not isinstance(l, Sequence):
                raise ValueError(l)
            else:
                return l

    def __setitem__(self, key, value):
        if self._direct:
            setattr(self._c, key, value)
        else:
            self._c[key] = value

    def __contains__(self, key):
        if self._direct:
            return hasattr(self._c, key)
        else:
            return key in self._c

    def unwrap(self):
        if isinstance(self._c, MultiDict):
            for field in self._list_fields:
                items = self._c.get(field, [])
                self._c.setlist(field, items)

        return self._c


class InvalidSpecificationError(ValueError):
    """Raised when an invalid specification is used."""


__all__ = ['Validator', 'InvalidSpecificationError']