import typesystem
import typing
from typesystem.schemas import SchemaMetaclass


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
        columns = []
        for name, field in new_model.fields.items():
            columns.append(field.get_column(name))
        return new_model


class Model(typesystem.Schema, metaclass=ModelMetaclass):
    pass
