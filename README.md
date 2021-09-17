# ORM

<p>
<a href="https://github.com/encode/orm/actions">
    <img src="https://github.com/encode/orm/workflows/Test%20Suite/badge.svg" alt="Build Status">
</a>
<a href="https://codecov.io/gh/encode/orm">
    <img src="https://codecov.io/gh/encode/orm/branch/master/graph/badge.svg" alt="Coverage">
</a>
<a href="https://pypi.org/project/orm/">
    <img src="https://badge.fury.io/py/orm.svg" alt="Package version">
</a>
</p>

The `orm` package is an async ORM for Python, with support for Postgres,
MySQL, and SQLite. ORM is built with:

* [SQLAlchemy core][sqlalchemy-core] for query building.
* [`databases`][databases] for cross-database async support.
* [`typesystem`][typesystem] for data validation.

Because ORM is built on SQLAlchemy core, you can use Alembic to provide
database migrations.

**ORM is still under development: We recommend pinning any dependencies with `orm~=0.2`**

---

## Installation

```shell
$ pip install orm
```

You can install the required database drivers with:

```shell
$ pip install orm[postgresql]
$ pip install orm[mysql]
$ pip install orm[sqlite]
```

Driver support is provided using one of [asyncpg][asyncpg], [aiomysql][aiomysql], or [aiosqlite][aiosqlite].

---

## Quickstart

**Note**: Use `ipython` to try this from the console, since it supports `await`.

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

# Create the tables
models.create_all()

await Note.objects.create(text="Buy the groceries.", completed=False)

note = await Note.objects.get(id=1)
print(note)
# Note(id=1, text="Buy the groceries.", completed=False)
```

[sqlalchemy-core]: https://docs.sqlalchemy.org/en/latest/core/
[asyncpg]: https://github.com/MagicStack/asyncpg
[aiomysql]: https://github.com/aio-libs/aiomysql
[aiosqlite]: https://github.com/jreese/aiosqlite

[databases]: https://github.com/encode/databases
[typesystem]: https://github.com/encode/typesystem
[typesystem-fields]: https://www.encode.io/typesystem/fields/
