import typing

import sqlalchemy
import typesystem


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
        self.primary_key = primary_key
        self.index = index
        self.unique = unique
        self.validator = self.get_validator(**kwargs)

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
        return typesystem.Any()

    def get_column_type(self):
        return sqlalchemy.JSON()


class ForeignKey(ModelField):
    def __init__(self, to, allow_null: bool = False):
        super().__init__(allow_null=allow_null)
        self.to = to

    def validate(self, value):
        return value.pk

    def get_validator(self, **kwargs) -> typesystem.Field:
        return typesystem.Any()

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
