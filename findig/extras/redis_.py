from cPickle import dumps, loads

import redis

from findig.utils import Cache


class RedisCache(Cache):
    def __init__(self, manager, **args):
        super(RedisCache, self).__init__(
            manager, fixer=args.pop('fixer', None), 
            key_builder=args.pop('key_builder', None)
        )

        self.fixkey = lambda k: "{0}{1}".format(args.pop('prefix', ''), k)
        self.r = redis.StrictRedis(**args)

    def __contains__(self, key):
        return self.r.exists(self.fixkey(key))

    def __getitem__(self, key):
        data = self.r.get(self.fixkey(key))
        if data is None:
            return
        else:
            return loads(data)

    def __setitem__(self, key, value):
        data = dumps(value)
        self.r.set(self.fixkey(key), data)

    def __delitem__(self, key):
        self.r.delete(self.fixkey(key))


__all__ = ["RedisCache"]