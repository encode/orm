import typing

import sqlalchemy
import typesystem
from typesystem.schemas import SchemaMetaclass


class ModelMetaclass(SchemaMetaclass):
    def __new__(
        cls: type, name: str, bases: typing.Sequence[type], attrs: dict
    ) -> type:
        new_model = super(ModelMetaclass, cls).__new__(  # type: ignore
            cls, name, bases, attrs
        )

        if attrs.get("__abstract__"):
            return new_model

        tablename = attrs["__tablename__"]
        metadata = attrs["__metadata__"]
        pkname = None

        columns = []
        for name, field in new_model.fields.items():
            if field.primary_key:
                pkname = name
            columns.append(field.get_column(name))

        new_model.__table__ = sqlalchemy.Table(tablename, metadata, *columns)
        new_model.__pkname__ = pkname
        new_model.objects = QuerySet(new_model)

        return new_model


class QuerySet:
    def __init__(self, model_cls):
        self.model_cls = model_cls
        self.database = model_cls.__database__
        self.query = self.model_cls.__table__.select()

    async def all(self):
        rows = await self.database.fetch_all(self.query)
        return [self.model_cls(**dict(row)) for row in rows]

    async def create(self, **kwargs):
        instance = self.model_cls.validate(kwargs)
        expr = self.model_cls.__table__.insert()
        expr = expr.values(**kwargs)
        instance.pk = await self.database.execute(expr)
        return instance


class Model(typesystem.Schema, metaclass=ModelMetaclass):
    __abstract__ = True

    async def update(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
        pk_column = getattr(self.__table__.c, self.__pkname__)
        expr = self.__table__.update()
        expr = expr.values(**kwargs).where(pk_column == self.pk)
        await self.__database__.execute(expr)
        return self

    async def delete(self):
        pk_column = getattr(self.__table__.c, self.__pkname__)
        expr = self.__table__.delete().where(pk_column == self.pk)
        await self.__database__.execute(expr)

    @property
    def pk(self):
        return getattr(self, self.__pkname__)

    @pk.setter
    def pk(self, value):
        setattr(self, self.__pkname__, value)
