import typing

import sqlalchemy
import typesystem
from attr import attrs


class ModelField:
    def __init__(
        self,
        primary_key: bool = False,
        index: bool = False,
        unique: bool = False,
        **kwargs: typing.Any
    ) -> None:
        if primary_key:
            kwargs["allow_null"] = True
        super().__init__(**kwargs)  # type: ignore
        self.primary_key = primary_key
        self.index = index
        self.unique = unique

    def get_column(self, name: str) -> sqlalchemy.Column:
        column_type = self.get_column_type()
        allow_null = getattr(self, "allow_null", False)
        return sqlalchemy.Column(
            name,
            column_type,
            primary_key=self.primary_key,
            nullable=allow_null and not self.primary_key,
            index=self.index,
            unique=self.unique,
        )

    def get_column_type(self) -> sqlalchemy.types.TypeEngine:
        raise NotImplementedError()  # pragma: no cover


class String(ModelField, typesystem.String):
    def get_column_type(self):
        return sqlalchemy.String(length=self.max_length)


class Integer(ModelField, typesystem.Integer):
    def get_column_type(self):
        return sqlalchemy.Integer()


class Boolean(ModelField, typesystem.Boolean):
    def get_column_type(self):
        return sqlalchemy.Boolean()


class ForeignKey(ModelField, typesystem.Field):
    def __init__(self, to, allow_null: bool = False):
        super().__init__(allow_null=allow_null)
        self.to = to

    def validate(self, value, strict=False):
        if isinstance(value, self.to):
            return value
        to_column = self.to.fields[self.to.__pkname__]
        pk = to_column.validate(value, strict=strict)
        return self.to(pk=pk)

    def get_column_type(self):
        to_column = self.to.fields[self.to.__pkname__]
        return to_column.get_column_type()
