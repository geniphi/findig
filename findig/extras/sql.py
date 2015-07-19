"""
"""

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql.expression import desc
from werkzeug.datastructures import MultiDict
from werkzeug.exceptions import BadRequest

from findig.context import ctx
from findig.tools.dataset import MutableDataSet, MutableRecord, FilteredDataSet
from findig.utils import to_snake_case


class _MappedObjMixin:
    @declared_attr
    def __tablename__(cls):
        return to_snake_case(cls.__name__)

    def __repr__(self):
        clsname = self.__class__.__name__
        parts = [
            "{}={!r}".format(c.name, getattr(self, c.name))
            for c in self.__table__.columns
        ]
        if parts:
            return "<{} {}>".format(clsname, ", ".join(parts))
        else:
            return "<{}>".join(clsname)


class SQLA:
    # NOTE ABOUT AUTO-CREATE: it does *not* update a table schema that
    # changes in code to the database side; those changes will have to be
    # manually applied on the database server.
    def __init__(self, engine, autocommit=False, autoflush=True,
                 auto_create=True, app=None):
        # Create an SQLAlchemy engine for the database
        if isinstance(engine, str):
            engine = create_engine(engine)

        self.engine = engine
        self._session_cls = sessionmaker(bind=engine,
                                         autocommit=autocommit,
                                         autoflush=autoflush)
        self._auto_create = auto_create
        self.Base = declarative_base(bind=engine, cls=_MappedObjMixin)

        if app is not None:
            self.attach_to(app)

    def attach_to(self, app):
        # This request context manager creates a session at the start
        # of the request, and closes it at the end.
        @app.context
        def sqla_session():
            session = self._session_cls()
            yield session
            session.close()

        if self._auto_create:
            app.startup_hook(self.create_all)

    def create_all(self, checkfirst=True):
        self.Base.metadata.create_all(checkfirst=checkfirst)

    def configure_session_factory(self, **kwargs):
        self._session_cls.configure(**kwargs)

    @contextmanager
    def transaction(self, new_session=False, auto_rollback=True):
        session = self._session_cls() if new_session else self.session

        try:
            yield session
            session.commit()
        except:
            if auto_rollback:
                session.rollback()
            raise
        finally:
            session.close()

    @property
    def session(self):
        """Return the SQL Alchemy session for the current request."""
        return ctx.sqla_session


class SQLASet(MutableDataSet):
    class InvalidField(BadRequest):
        pass

    class CommitError(BadRequest):
        def __init__(self, e):
            self.inner = e
            super().__init__()

    def __init__(self, orm_cls):
        self._cls = orm_cls
        self._modifiers = []

    def __iter__(self):
        query = ctx.sqla_session.query(self._cls)
        for modifier in self._modifiers:
            mod_name, *args = modifier
            if mod_name == "filter":
                filters, filter_by = args
                query = self._filter_query(query, filters, filter_by)
            if mod_name == "sort":
                for field in args:
                    query = query.order_by(field)
            if mod_name == "limit":
                count, offset = args
                if offset:
                    query = query.offset(offset)
                query = query.limit(count)

        yield from map(_SQLRecord, query.all())

    def add(self, data):
        data = data.to_dict() if isinstance(data, MultiDict) else data
        try:
            obj = self._cls(**data)
        except TypeError:
            raise self.InvalidField

        ctx.sqla_session.add(obj)

        try:
            ctx.sqla_session.commit()
        except Exception as e:
            raise self.CommitError(e)

        key = obj.__table__.primary_key
        return {c.name: getattr(obj, c.name) for c in key}

    def copy(self):
        copy = SQLSet(self._cls)
        copy._modifiers = self._modifiers[:]
        return copy

    def filtered(self, *filters, **filter_by):
        copy = self.copy()
        copy._modifiers.append(("filter", filters, filter_by))
        return copy

    def sorted(self, *fields, descending=False):
        copy = self.copy()
        fields = [desc(f) if descending else f for f in fields]
        copy._modifiers.append(("sort", fields))
        return copy

    def limit(self, count, offset=0):
        copy = self.copy()
        copy._modifiers.append(("limit", count, offset))
        return copy

    def fetch_now(self, *args, **kwargs):
        query = ctx.sqla_session.query(self._cls)
        query = self._filter_query(query, *args, **kwargs)
        obj = query.first()
        if obj is None:
            raise LookupError("No matching records.")
        else:
            return _SQLRecord(obj)

    def _filter_query(self, query, *filter_args, **filter_by):
        query = query.filter_by(**filter_by)
        for arg in filter_args:
            query = query.filter(arg)
        return query


class _SQLRecord(MutableRecord):
    def __init__(self, obj):
        self._obj = obj

    def read(self):
        d = {}
        for c in self._obj.__class__.__table__.columns:
            d[c.name] = getattr(self._obj, c.name)
        return d

    def patch(self, add_data, remove_fields):
        try:
            for field in remove_fields:
                setattr(self._obj, field, None)

            for k, v in add_data.items():
                setattr(self._obj, k, v)

            ctx.sqla_session.commit()
        except AttributeError:
            raise SQLASet.InvalidField

    def delete(self):
        ctx.sqla_session.delete(self._obj)
        ctx.sqla_session.commit()


__all__ = ["SQLA", "SQLASet"]
