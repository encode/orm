import typing

import sqlalchemy
import typesystem
from typesystem.schemas import SchemaMetaclass
from orm.exceptions import NoMatch, MultipleMatches


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

        return new_model


class QuerySet:
    def __init__(self, model_cls=None):
        self.model_cls = model_cls

    def __get__(self, instance, owner):
        return self.__class__(model_cls=owner)

    @property
    def database(self):
        return self.model_cls.__database__

    @property
    def table(self):
        return self.model_cls.__table__

    async def all(self):
        expr = self.table.select()
        rows = await self.database.fetch_all(expr)
        return [self.model_cls(dict(row)) for row in rows]

    async def get(self):
        expr = self.table.select()
        rows = await self.database.fetch_all(expr)

        if not rows:
            raise NoMatch()
        if len(rows) > 1:
            raise MultipleMatches()
        return self.model_cls(dict(rows[0]))

    async def create(self, **kwargs):
        # Validate the keyword arguments.
        fields = self.model_cls.fields
        required = [key for key, value in fields.items() if not value.has_default()]
        validator = typesystem.Object(
            properties=fields, required=required, additional_properties=False
        )
        kwargs = validator.validate(kwargs)

        # Build the insert expression.
        expr = self.table.insert()
        expr = expr.values(**kwargs)

        # Execute the insert, and return a new model instance.
        instance = self.model_cls(kwargs)
        instance.pk = await self.database.execute(expr)
        return instance


class Model(typesystem.Schema, metaclass=ModelMetaclass):
    __abstract__ = True

    async def update(self, **kwargs):
        # Validate the keyword arguments.
        fields = {key: field for key, field in self.fields.items() if key in kwargs}
        validator = typesystem.Object(properties=fields)
        kwargs = validator.validate(kwargs)

        # Build the update expression.
        pk_column = getattr(self.__table__.c, self.__pkname__)
        expr = self.__table__.update()
        expr = expr.values(**kwargs).where(pk_column == self.pk)

        # Perform the update.
        await self.__database__.execute(expr)

        # Update the model instance.
        for key, value in kwargs.items():
            setattr(self, key, value)

    async def delete(self):
        # Build the delete expression.
        pk_column = getattr(self.__table__.c, self.__pkname__)
        expr = self.__table__.delete().where(pk_column == self.pk)

        # Perform the delete.
        await self.__database__.execute(expr)

    objects = QuerySet()

    @property
    def pk(self):
        return getattr(self, self.__pkname__)

    @pk.setter
    def pk(self, value):
        setattr(self, self.__pkname__, value)
