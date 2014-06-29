import collections

from werkzeug.exceptions import *

from findig.context import url_adapter, request


class Resource(object):

    __slots__ = ('_fget', 'fsave', 'fdel', '_name', 'handlers',
                 'manager',)

    def __init__(self, **args):
        self.fget = args.get('fget')
        self.fsave = args.get('fsave')
        self.fdel = args.get('fdel')
        self.handlers = args.get('handler', {})
        self.name = args.get('name')
        self.manager = args.get('manager')

    def getter(self, fget):
        self.fget = fget
        return self

    def saver(self, fsave):
        self.fsave = fsave
        return self

    def deleter(self, fdel):
        self.fdel = fdel
        return self

    def get_method_list(self):
        methods = set(self.handlers)

        if self.fget is not None:
            methods.add('get')

        if self.fsave is not None:
            methods.add('put')

        if self.fget is not None and self.fsave is not None:
            methods.add('patch')

        if self.fdel is not None:
            methods.add('delete')

        return methods

    def run_func(self, method, **args):
        method = method.lower()

        if method in self.handlers:
            func = self.handlers[method]

        elif method == 'patch' and self.fsave and self.fget:
            # Get the resource data, update it with the keys
            # from the input, and PUT it to the resource.
            data = dict(self.fget(**args))
            data.update(request.input.to_dict())
            request.input = request.parameter_storage_class(data)
            func = self.fsave

        elif method == 'get' and self.fget:
            func = self.fget

        elif method == 'put' and self.fsave:
            func = self.fsave

        elif method == 'delete' and self.fdel:
            func = self.fdel

        else:
            raise MethodNotAllowed(self.get_method_list())            

        return func(**args)

    @property
    def fget(self):
        return getattr(self, '_fget')

    @fget.setter
    def fget(self, fget):
        self._fget = fget

    @property
    def name(self):
        name = getattr(self, '_name', None)

        if name is None:
            return u"{0.__module__}.{0.__name__}".format(self.fget)

    @name.setter
    def name(self, name):
        self._name = name


    def bind(self, **args):
        return BoundResource(self, **args)

    def __repr__(self):
        return u"<Resource '{0.name}'>".format(self)

    def __call__(self, **args):
        return self.fget(**args)


class CollectionResource(Resource):
    __slots__ = ("fcreate",)

    def __init__(self, **args):
        super(CollectionResource, self).__init__(**args)
        self.fcreate = args.get("fcreate")

    def creator(self, fcreate):
        self.fcreate = fcreate
        return self

    def get_method_list(self):
        methods = []
        
        if self.fcreate is not None:
            methods.append('post')

        methods.extend(super(CollectionResource, self).get_method_list())

        return methods

    def run_func(self, method, **args):
        if method.lower() == 'post' and self.fcreate is not None:
            res = self.fcreate(**args)
            if isinstance(res, BoundResource):
                # If a BoundResource is returned from a creator,
                # it points to a new resource, meaning that the
                # resource has been created. Status 201
                return res, 201
            else:
                return res

        else:
            return super(CollectionResource, self).run_func(method, **args)


class BoundResource(object):
    __slots__ = "res", "bind_args"

    def __init__(self, resource, **args):
        self.res = resource
        self.bind_args = args

    def __repr__(self):
        args_str = u",".join(u"{}={!r}".format(a,v) for a,v in self.bind_args.items())
        return u"<BoundResource '{}' ({})>".format(self.res.name, args_str)

    def __getattribute__(self, name):
        if name.startswith('_') or name in self.__slots__ + ('url',):
            return super(BoundResource, self).__getattribute__(name)
        else:
            return getattr(self.res, name)

    def __call__(self, method='get'):
        return self.res.run_func(method, **self.bind_args)

    @property
    def url(self):
        return url_adapter.build(self.res, self.bind_args)