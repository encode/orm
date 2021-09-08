import typing

import sqlalchemy
import typesystem

from orm.sqlalchemy_fields import GUID


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
    def __init__(self, **kwargs):
        assert "max_length" in kwargs, "max_length is required"
        super().__init__(**kwargs)

    def get_column_type(self):
        return sqlalchemy.String(length=self.max_length)


class Text(ModelField, typesystem.Text):
    def get_column_type(self):
        return sqlalchemy.Text()


class Integer(ModelField, typesystem.Integer):
    def get_column_type(self):
        return sqlalchemy.Integer()


class BigInteger(ModelField, typesystem.Integer):
    def get_column_type(self):
        return sqlalchemy.BigInteger()


class Float(ModelField, typesystem.Float):
    def get_column_type(self):
        return sqlalchemy.Float()


class Boolean(ModelField, typesystem.Boolean):
    def get_column_type(self):
        return sqlalchemy.Boolean()


class DateTime(ModelField, typesystem.DateTime):
    def get_column_type(self):
        return sqlalchemy.DateTime()


class Date(ModelField, typesystem.Date):
    def get_column_type(self):
        return sqlalchemy.Date()


class Time(ModelField, typesystem.Time):
    def get_column_type(self):
        return sqlalchemy.Time()


class JSON(ModelField, typesystem.Any):
    def get_column_type(self):
        return sqlalchemy.JSON()


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


class Enum(ModelField, typesystem.Any):
    def __init__(self, enum, **kwargs):
        super().__init__(**kwargs)
        self.enum = enum

    def get_column_type(self):
        return sqlalchemy.Enum(self.enum)


class Decimal(ModelField, typesystem.Decimal):
    def __init__(self, max_digits: int, decimal_places: int, **kwargs):
        assert max_digits, "max_digits is required"
        assert decimal_places, "decimal_places is required"
        self.max_digits = max_digits
        self.decimal_places = decimal_places
        super().__init__(**kwargs)

    def get_column_type(self):
        return sqlalchemy.Numeric(precision=self.max_digits, scale=self.decimal_places)


class UUID(ModelField, typesystem.UUID):
    def get_column_type(self):
        return GUID()
