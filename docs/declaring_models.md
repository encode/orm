## Declaring models

You can define models by inheriting from `orm.Model` and
defining model fields in the `fields` attribute.
For each defined model you need to set two special variables:

* `registry` an instance of `orm.ModelRegistry`
* `fields` a `dict` of `orm` fields

You can also specify the table name in database by setting `tablename` attribute.

```python
import databases
import orm

database = databases.Database("sqlite:///db.sqlite")
models = orm.ModelRegistry(database=database)


class Note(orm.Model):
    tablename = "notes"
    registry = models
    fields = {
        "id": orm.Integer(primary_key=True),
        "text": orm.String(max_length=100),
        "completed": orm.Boolean(default=False),
    }
```

ORM can create or drop database and tables from models using SQLAlchemy.
You can use the following methods:

```python
models.create_all()

models.drop_all()
```

## Data types

The following keyword arguments are supported on all field types.

* `primary_key` - A boolean. Determine if column is primary key.
* `allow_null` - A boolean. Determine if column is nullable.
* `default` - A value or a callable (function).
* `index` - A boolean. Determine if database indexes should be created.
* `unique` - A boolean. Determine if unique constraint should be created.

All fields are required unless one of the following is set:

* `allow_null` - A boolean. Determine if column is nullable. Sets the default to `None`.
* `allow_blank` - A boolean. Determine if empty strings are allowed. Sets the default to `""`.
* `default` - A value or a callable (function).

The following column types are supported.
See `TypeSystem` for [type-specific validation keyword arguments][typesystem-fields].

* `orm.BigInteger()`
* `orm.Boolean()`
* `orm.Date()`
* `orm.DateTime()`
* `orm.Decimal()`
* `orm.Email(max_length)`
* `orm.Enum()`
* `orm.Float()`
* `orm.Integer()`
* `orm.String(max_length)`
* `orm.Text()`
* `orm.Time()`
* `orm.UUID()`
* `orm.JSON()`

[typesystem-fields]: https://www.encode.io/typesystem/fields/
