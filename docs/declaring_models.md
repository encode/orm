## Declaring models

You can define models by inheriting from `orm.Model` and
defining model fields as attributes in the class.
For each defined model you need to set two special variables:

* `__database__` for database connection.
* `__metadata__` for `SQLAlchemy` functions and migrations.

You can also specify the table name in database by setting `__tablename__` attribute.

```python
import databases
import orm
import sqlalchemy

database = databases.Database("sqlite:///db.sqlite")
metadata = sqlalchemy.MetaData()


class Note(orm.Model):
    __tablename__ = "notes"
    __database__ = database
    __metadata__ = metadata

    id = orm.Integer(primary_key=True)
    text = orm.String(max_length=100)
    completed = orm.Boolean(default=False)
```

ORM can create or drop database and tables from models using SQLAlchemy.
For using these functions or `Alembic` migrations, you still have to
install a synchronous DB driver: [psycopg2][psycopg2] for PostgreSQL and [pymysql][pymysql] for MySQL.

Afer installing a synchronous DB driver, you can create tables for the models using:

```python
engine = sqlalchemy.create_engine(str(database.url))
metadata.create_all(engine)
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
* `orm.Enum()`
* `orm.Float()`
* `orm.Integer()`
* `orm.String(max_length)`
* `orm.Text()`
* `orm.Time()`
* `orm.JSON()`

[psycopg2]: https://www.psycopg.org/
[pymysql]: https://github.com/PyMySQL/PyMySQL
[typesystem-fields]: https://www.encode.io/typesystem/fields/
