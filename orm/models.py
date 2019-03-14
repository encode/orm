import typesystem
import typing
from typesystem.schemas import SchemaMetaclass
import sqlalchemy

class ModelMetaclass(SchemaMetaclass):
    def __new__(
        cls: type,
        name: str,
        bases: typing.Sequence[type],
        attrs: dict,
    ) -> type:
        new_model = super(ModelMetaclass, cls).__new__(  # type: ignore
            cls, name, bases, attrs
        )

        if attrs.get('__skip__'):
            return new_model

        tablename = attrs['__tablename__']
        metadata = attrs['__metadata__']

        columns = []
        for name, field in new_model.fields.items():
            columns.append(field.get_column(name))

        new_model.__table__ = sqlalchemy.Table(tablename, metadata, *columns)

        return new_model


class Model(typesystem.Schema, metaclass=ModelMetaclass):
    __skip__ = True
