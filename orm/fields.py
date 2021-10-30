import typing

import sqlalchemy
import typesystem

from orm.sqlalchemy_fields import GUID, GenericIP


class ModelField:
    def __init__(
        self,
        primary_key: bool = False,
        index: bool = False,
        unique: bool = False,
        **kwargs: typing.Any,
    ) -> None:
        if primary_key:
            kwargs["read_only"] = True
        self.allow_null = kwargs.get("allow_null", False)
        self.primary_key = primary_key
        self.index = index
        self.unique = unique
        self.validator = self.get_validator(**kwargs)

    def get_column(self, name: str) -> sqlalchemy.Column:
        column_type = self.get_column_type()
        constraints = self.get_constraints()
        return sqlalchemy.Column(
            name,
            column_type,
            *constraints,
            primary_key=self.primary_key,
            nullable=self.allow_null and not self.primary_key,
            index=self.index,
            unique=self.unique,
        )

    def get_validator(self, **kwargs) -> typesystem.Field:
        raise NotImplementedError()  # pragma: no cover

    def get_column_type(self) -> sqlalchemy.types.TypeEngine:
        raise NotImplementedError()  # pragma: no cover

    def get_constraints(self):
        return []

    def expand_relationship(self, value):
        return value


class String(ModelField):
    def __init__(self, **kwargs):
        assert "max_length" in kwargs, "max_length is required"
        super().__init__(**kwargs)

    def get_validator(self, **kwargs) -> typesystem.Field:
        return typesystem.String(**kwargs)

    def get_column_type(self):
        return sqlalchemy.String(length=self.validator.max_length)


class Text(ModelField):
    def get_validator(self, **kwargs) -> typesystem.Field:
        return typesystem.Text(**kwargs)

    def get_column_type(self):
        return sqlalchemy.Text()


class Integer(ModelField):
    def get_validator(self, **kwargs) -> typesystem.Field:
        return typesystem.Integer(**kwargs)

    def get_column_type(self):
        return sqlalchemy.Integer()


class Float(ModelField):
    def get_validator(self, **kwargs) -> typesystem.Field:
        return typesystem.Float(**kwargs)

    def get_column_type(self):
        return sqlalchemy.Float()


class BigInteger(ModelField):
    def get_validator(self, **kwargs) -> typesystem.Field:
        return typesystem.Integer(**kwargs)

    def get_column_type(self):
        return sqlalchemy.BigInteger()


class Boolean(ModelField):
    def get_validator(self, **kwargs) -> typesystem.Field:
        return typesystem.Boolean(**kwargs)

    def get_column_type(self):
        return sqlalchemy.Boolean()


class DateTime(ModelField):
    def get_validator(self, **kwargs) -> typesystem.Field:
        return typesystem.DateTime(**kwargs)

    def get_column_type(self):
        return sqlalchemy.DateTime()


class Date(ModelField):
    def get_validator(self, **kwargs) -> typesystem.Field:
        return typesystem.Date(**kwargs)

    def get_column_type(self):
        return sqlalchemy.Date()


class Time(ModelField):
    def get_validator(self, **kwargs) -> typesystem.Field:
        return typesystem.Time(**kwargs)

    def get_column_type(self):
        return sqlalchemy.Time()


class JSON(ModelField):
    def get_validator(self, **kwargs) -> typesystem.Field:
        return typesystem.Any(**kwargs)

    def get_column_type(self):
        return sqlalchemy.JSON()


class ForeignKey(ModelField):
    class ForeignKeyValidator(typesystem.Field):
        def validate(self, value):
            return value.pk

    def __init__(
        self, to, allow_null: bool = False, on_delete: typing.Optional[str] = None
    ):
        super().__init__(allow_null=allow_null)
        self.to = to
        self.on_delete = on_delete

    @property
    def target(self):
        if not hasattr(self, "_target"):
            if isinstance(self.to, str):
                self._target = self.registry.models[self.to]
            else:
                self._target = self.to
        return self._target

    def get_validator(self, **kwargs) -> typesystem.Field:
        return self.ForeignKeyValidator()

    def get_column(self, name: str) -> sqlalchemy.Column:
        target = self.target
        to_field = target.fields[target.pkname]

        column_type = to_field.get_column_type()
        constraints = [
            sqlalchemy.schema.ForeignKey(
                f"{target.tablename}.{target.pkname}", ondelete=self.on_delete
            )
        ]
        return sqlalchemy.Column(
            name,
            column_type,
            *constraints,
            nullable=self.allow_null,
        )

    def expand_relationship(self, value):
        target = self.target
        if isinstance(value, target):
            return value
        return target(pk=value)


class OneToOne(ForeignKey):
    def get_column(self, name: str) -> sqlalchemy.Column:
        target = self.target
        to_field = target.fields[target.pkname]

        column_type = to_field.get_column_type()
        constraints = [
            sqlalchemy.schema.ForeignKey(
                f"{target.tablename}.{target.pkname}", ondelete=self.on_delete
            ),
        ]

        return sqlalchemy.Column(
            name,
            column_type,
            *constraints,
            nullable=self.allow_null,
            unique=True,
        )


class Enum(ModelField):
    def __init__(self, enum, **kwargs):
        super().__init__(**kwargs)
        self.enum = enum

    def get_validator(self, **kwargs) -> typesystem.Field:
        return typesystem.Any(**kwargs)

    def get_column_type(self):
        return sqlalchemy.Enum(self.enum)


class Decimal(ModelField):
    def __init__(self, max_digits: int, decimal_places: int, **kwargs):
        assert max_digits, "max_digits is required"
        assert decimal_places, "decimal_places is required"
        self.max_digits = max_digits
        self.decimal_places = decimal_places
        super().__init__(**kwargs)

    def get_validator(self, **kwargs) -> typesystem.Field:
        return typesystem.Decimal(**kwargs)

    def get_column_type(self):
        return sqlalchemy.Numeric(precision=self.max_digits, scale=self.decimal_places)


class UUID(ModelField):
    def get_validator(self, **kwargs) -> typesystem.Field:
        return typesystem.UUID(**kwargs)

    def get_column_type(self):
        return GUID()


class Email(String):
    def get_validator(self, **kwargs) -> typesystem.Field:
        return typesystem.Email(**kwargs)

    def get_column_type(self):
        return sqlalchemy.String(length=self.validator.max_length)


class IPAddress(ModelField):
    def get_validator(self, **kwargs) -> typesystem.Field:
        return typesystem.IPAddress(**kwargs)

    def get_column_type(self):
        return GenericIP()


class URL(String):
    def get_validator(self, **kwargs) -> typesystem.Field:
        return typesystem.URL(**kwargs)

    def get_column_type(self):
        return sqlalchemy.String(length=self.validator.max_length)
