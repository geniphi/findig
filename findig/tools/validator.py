"""
The :mod:`findig.tools.validator` module exposes the :class:`Validator`
which can be used to validate an application or request's input data.

Validators work by specifying a converter for each field in the 
input data to be validated::

    validator = Validator(app)
    
    @validator.enforce(id=int)
    @app.route("/test")
    def resource():
        pass

    @resource.model("write")
    def write_resource(data):
        assert isinstance(data['id'], int)

If the converter fails to convert the field's value, then a 
``400 BAD REQUEST`` error is sent back.

Converters don't have to be functions; they can be a singleton list
containing another converter, indicating that the field is expected to
be a list of items for which that converter works::

    @validator.enforce(ids=[int])
    @app.route("/test2")
    def resource2():
        pass

    @resource2.model("write")
    def write_resource(data):
        for id in data['ids']:
            assert isinstance(id, int)

Converters can also be string specifications corresponding to a 
pre-registered converter and its arguments. All of
werkzeug's :py:werkzeug:`builtin converters` and their arguments are
pre-registered and thus usable::

    @validator.enforce(foo='any(bar,baz)', cid='string(length=3)')
    @app.route("/test3")
    def resource3():
        pass

    @resource2.model("write")
    def write_resource(data):
        assert data['foo'] in ('bar', 'baz')
        assert len(data['cid']) == 3

"""

from collections import namedtuple
from collections.abc import Callable, Mapping, Sequence
from functools import partial
import re

from werkzeug.datastructures import MultiDict
from werkzeug.exceptions import BadRequest
from werkzeug.routing import parse_converter_args, BaseConverter

from findig.context import ctx
from findig.datapipe import DataPipe


_converter_re = re.compile(r'''
        (?P<name>[a-zA-Z_][a-zA-Z0-9_]*)   # converter name
        (?:\((?P<args>.*?)\))?                  # converter args
''', re.VERBOSE | re.UNICODE)

class converter_spec(namedtuple('converter_spec', 'name args')):
    def __repr__(self):
        if self.args is None:
            return repr(self.name)
        else:
            return repr("{}({})".format(self.name, self.args))

class Validator:
    def __init__(self, app):
        self.validation_specs = {}
        self.attach_to(app)

    def attach_to(self, app):
        # Hook the validator into the dispatcher's data pre processor
        # so that we can look at incoming request data and complain
        # if the request data doesn't match what we're looking for
        app.pre_processor = DataPipe(app.pre_processor, self.validate)
        app.startup_hook(partial(self.__prepare_converters, app))

    def enforce(self, *args, **validator_spec):
        def decorator(resource):
            self.__register_spec(resource.name, validator_spec)
            return resource

        if len(args) == 0:
            return decorator
        elif len(args) == 1:
            return decorator(args[0])
        else:
            raise TypeError

    def enforce_all(self, **validator_spec):
        self.__register_spec(None, validator_spec)

    def __register_spec(self, key, spec):
        def validate_item_spec(item_spec):
            if isinstance(item_spec, str):
                m = _converter_re.fullmatch(item_spec)
                if m is not None:
                    return converter_spec(m.group('name'), m.group('args'))
                else:
                    return False

            elif isinstance(item_spec, list):
                if len(item_spec) != 1:
                    return False
                else:
                    return [validate_item_spec(item_spec[0])]

            elif not isinstance(item_spec, Callable):
                return False

            else:
                return item_spec

        for field, item_spec in spec.items():
            new_item_spec = validate_item_spec(item_spec)
            if item_spec is False:
                raise InvalidSpecificationError(item_spec)
            else:
                spec[field] = new_item_spec

        else:
            self.validation_specs.setdefault(key, {})
            self.validation_specs[key].update(spec)

    def __prepare_converters(self, app):
        def fix_spec(item_spec):
            if isinstance(item_spec, converter_spec):
                cname, args = item_spec
                args, kwargs = ((), {}) if args is None \
                                        else parse_converter_args(args)
                if cname not in app.url_map.converters:
                    return None

                ccls = app.url_map.converters[cname]
                converter = ccls(app.url_map, *args, **kwargs)
                compiled_re = re.compile(converter.regex)
                return compiled_re, converter
            elif isinstance(item_spec, list):
                return [fix_spec(item_spec[0])]
            else:
                return item_spec

        for resource in self.validation_specs:
            for field, spec in self.validation_specs[resource].items():
                new_spec = fix_spec(spec)
                if new_spec is not None:
                    self.validation_specs[resource][field] = new_spec
                else:
                    raise InvalidSpecificationError(
                        "\"{}={!r}\"".format(field, spec)
                    )
                
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
            unconverted_items = _ContainerWrapper(data.getlist(key))
            converted_items = []
            child_spec = item_spec[0]
            for i, _ in enumerate(unconverted_items):
                converted_items.append(
                    self.__check_item(unconverted_items, i, child_spec)
                )
            return converted_items
        elif isinstance(item_spec, tuple):
            regexp, converter = item_spec
            val = data[key]
            if not regexp.fullmatch(val):
                raise ValueError(val)
            else:
                return converter.to_python(val)

        else:
            raise InvalidSpecificationError(item_spec)

    def validate(self, data):
        spec = {}
        spec.update(self.validation_specs.get(None, {}))
        spec.update(self.validation_specs.get(ctx.resource.name, {}))

        wrapped = _ContainerWrapper(data)

        conversion_errs = []

        # Transform the data according to the conversion spec
        for field, field_spec in spec.items():
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