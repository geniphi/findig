from ast import literal_eval
from collections.abc import Callable, Mapping
from contextlib import contextmanager
from time import time

import redis

from findig.context import ctx
from findig.resource import AbstractResource
from findig.tools.dataset import MutableDataSet, MutableRecord, FilteredDataSet


class IndexToken(Mapping):
    __slots__ = 'sz', 'fields'

    def __init__(self, fields, bytesize=4):
        self.fields = fields
        self.sz = bytesize

    def __str__(self):
        return ",".join("{}={!r}".format(k, self.fields[k])
                        for k in sorted(self.fields))

    def __hash__(self):
        return hash(str(self)) & (2**(8*self.sz - 1) - 1)

    def __iter__(self):
        yield from self.fields

    def __len__(self):
        return len(self.fields)

    def __getitem__(self, key):
        return self.fields[key]

    @property
    def value(self):
        return hash(self).to_bytes(self.sz, 'big')


class RedisObj(MutableRecord):
    def __init__(self, key, collection=None, include_id=True):
        self.itemkey = key
        self.collection = collection
        self.include_id = include_id
        self.r = (collection.r 
                  if collection is not None
                  else redis.StrictRedis())
        self.inblock = False

    def __repr__(self):
        return "<{name}({key!r}){suffix}>".format(
            name="redis-object" if self.collection is None else "item",
            key=self.itemkey,
            suffix="" if self.collection is None
                      else " of {!r}".format(self.collection)
        )

    def start_edit_block(self):
        client = self.r
        self.r = self.r.pipeline()
        self.inblock = True
        return (client, dict(self))

    def close_edit_block(self, token):
        client, old_data = token

        ret = self.r.execute()
        self.r = client
        
        data = dict(self)

        if self.collection is not None:
            self.collection.reindex(
                self.id,
                data,
                old_data
            )

        self.invalidate(new_data=data)
        self.inblock = False
        

    def patch(self, add_data, remove_fields, replace=False):
        p = self.r.pipeline()

        if not self.inblock:
            old_data = dict(self)

        if replace:
            p.delete(self.itemkey)

        elif remove_fields:
            p.hdel(self.itemkey, *remove_fields)

        self.store(add_data, self.itemkey, p)
        p.execute()

        if self.inblock:
            data = {k: old_data[k] for k in old_data 
                    if k not in remove_fields}
            data.update(add_data)

            self.invalidate(new_data=data)

            if self.collection is not None:
                self.collection.reindex(self.id, data, old_data)

        else:
            self.invalidate()

    def read(self):
        data = self.r.hgetall(self.itemkey)
        if self.include_id:
            data[b'id'] = self.id.encode("utf8")
        return {k.decode('utf8'):literal_eval(v.decode('utf8')) 
                for k,v in data.items()}

    def delete(self):
        if self.collection is not None:
            self.collection.remove_from_index(self.id, self)
            self.collection.untrack_id(self.id)

        self.r.delete(self.itemkey)

    @staticmethod
    def store(data, key, client):
        data = {k: repr(v).encode('utf8')
                for k,v in data.items()}

        return client.hmset(key, data)

    @property
    def id(self):
        return self.itemkey.rpartition(":")[-1]

            
class RedisSet(MutableDataSet):
    """
    A RedisSet is an :class:AbstractDataSet that stores its items in
    a Redis database (using a Sorted Set to represent the collection,
    and a sorted set to represent items).
    """

    def __init__(self, key=None, client=None, **args):
        if key is None:
            key = ctx.resource

        if isinstance(key, AbstractResource):
            key = "findig:resource:{}".format(key.name)

        self.colkey = key
        self.itemkey = self.colkey + ':item:{id}'
        self.indkey = self.colkey + ':index'
        self.incrkey =  self.colkey + ':next-id'
        self.genid = args.pop(
            'generate_id', 
            lambda d: self.r.incr(self.incrkey)
        )
        self.indsize = args.pop('index_size', 4)
        self.filterby = args.pop('filterby', {})
        self.indexby = args.pop('candidate_keys', [('id',)])
        self.include_ids = args.pop('include_ids', True)
        self.r = redis.StrictRedis() if client is None else client

    def __repr__(self):
        if self.filterby:
            name = "filtered-redis-view"
            suffix = "|{}".format(
                ",".join("{}={!r}".format(k,v) 
                         for k,v in self.filterby.items())
            )
        else:
            name = "redis-set"
            suffix = ""

        return "<{name}({key!r}){suffix}>".format(
            name=name, suffix=suffix, key=self.colkey
        )

    def __iter__(self):
        """Query the set and iterate through the elements."""
        # If there is a filter, and it is completely encapsulated by
        # our index, we can use that to iter through the items
        
        tokens = self.__buildindextokens(self.filterby, raise_err=False)
        if tokens:
            # Pick an index to scan
            token = random.choice(tokens)
            id_blobs = self.r.zrangebylex(self.indkey, token.value, token.value)
            ids = [bs[self.indsize:] for bs in id_blobs]

        else:
            ids = self.r.zrange(self.colkey, 0, -1)

        for id in map(lambda bs: bs.decode('ascii'), ids):
            itemkey = self.itemkey.format(id=id)
            if self.filterby:
                # Check the items against the filter if it was
                # specified
                data = RedisObj(itemkey, self, self.include_ids)
                if FilteredDataSet.check_match(data, self.filterby):
                    yield data
            else:
                yield RedisObj(itemkey, self, self.include_ids)

    def add(self, data):
        """Add the record to the set."""
        id = str(data['id'] if 'id' in data else self.genid(data))
        itemkey = self.itemkey.format(id=id)

        with self.group_redis_commands():
            tokens = self.add_to_index(id, data)
            self.track_id(id)
            RedisObj.store(data, itemkey, self.r)

        return tokens[0]

    def fetch_now(self, **spec):
        """Get an item matching the search spec."""
        if list(spec) == ['id']:
            # Fetching by ID only; just lookup the item according to its
            # key
            itemkey = self.itemkey.format(id=spec['id'])
            if not self.r.exists(itemkey):
                raise LookupError("No matching item found.")
            else:
                return RedisObj(itemkey, self)

        else:
            return super(RedisSet, self).fetch_now(**spec)

    def track_id(self, id):
        self.r.zadd(self.colkey, time(), id)

    def untrack_id(self, id):
        self.r.zrem(self.colkey, id)

    def remove_from_index(self, id, data):
        tokens = self.__buildindextokens(data, id, False)
        for token in tokens:
            self.r.zrem(
                self.indkey, 
                token.value + id.encode('ascii')
            )

    def add_to_index(self, id, data):
        tokens = self.__buildindextokens(data, id)
        for token in tokens:
            self.r.zadd(
                self.indkey,
                0,
                token.value + id.encode('ascii')
            )
        return tokens

    def reindex(self, id, data, old_data):
        with self.group_redis_commands():
            self.remove_from_index(id, data)
            self.add_to_index(id, data)

    def clear(self):
        # Remove all the child objects
        for_removal = list(self)

        with self.group_redis_commands():
            for obj in for_removal:
                obj.delete()

            self.r.delete(self.incrkey)

        # Delete all the redis structures
        # Technically this step shouldn't be necessary;
        # Redis should clean up the other data structures

    def filtered(self, **spec):
        filter = dict(self.filterby)
        filter.update(spec)
        args = {
            'key': self.colkey,
            'candidate_keys': self.indexby,
            'index_size': self.indsize,
            'filterby': filter,
            'client': self.r,
        }
        return RedisSet(**args)

    @contextmanager
    def group_redis_commands(self):
        client = self.r
        self.r = client.pipeline()

        yield

        self.r.execute()
        self.r = client

    def __buildindextokens(self, data, generated_id=None, raise_err=True):
        index = []
       
        for ind in self.indexby:
            mapping = {}
            for field in ind:
                if field in data:
                    mapping[field] = data[field]
                elif field == 'id' and generated_id is not None: # special case
                    mapping[field] = generated_id
                else:
                    # Can't use this index
                    break
            else:
                index.append(IndexToken(mapping, self.indsize))

        if not index:
            if raise_err:
                raise ValueError("Could not index this data. "
                                 "This may be due to insuffient index keys "
                                 "or incomplete data."
                                )
            else:
                return []
        else:
            return index

__all__ = ["RedisSet"]