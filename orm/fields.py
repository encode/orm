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
        **kwargs: typing.Any,
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
        constraints = self.get_constraints()
        return sqlalchemy.Column(
            name,
            column_type,
            *constraints,
            primary_key=self.primary_key,
            nullable=allow_null and not self.primary_key,
            index=self.index,
            unique=self.unique,
        )

    def get_column_type(self) -> sqlalchemy.types.TypeEngine:
        raise NotImplementedError()  # pragma: no cover

    def get_constraints(self):
        return []

    def expand_relationship(self, value):
        return value


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
        return value.pk

    def get_constraints(self):
        fk_string = self.to.__tablename__ + "." + self.to.__pkname__
        return [sqlalchemy.schema.ForeignKey(fk_string)]

    def get_column_type(self):
        to_column = self.to.fields[self.to.__pkname__]
        return to_column.get_column_type()

    def expand_relationship(self, value):
        if isinstance(value, self.to):
            return value
        return self.to({self.to.__pkname__: value})
