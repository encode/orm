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

**ORM is still under development: We recommend pinning any dependencies with `orm~=0.1`**

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
Note that if you are using any synchronous SQLAlchemy functions such as `engine.create_all()` or [alembic][alembic] migrations then you still have to install a synchronous DB driver: [psycopg2][psycopg2] for PostgreSQL and [pymysql][pymysql] for MySQL.

---

## Quickstart

**Note**: Use `ipython` to try this from the console, since it supports `await`.

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

# Create the database and tables
engine = sqlalchemy.create_engine(str(database.url))
metadata.create_all(engine)

await Note.objects.create(text="Buy the groceries.", completed=False)

note = await Note.objects.get(id=1)
print(note)
# Note(id=1, text="Buy the groceries.", completed=False)
```

[sqlalchemy-core]: https://docs.sqlalchemy.org/en/latest/core/
[alembic]: https://alembic.sqlalchemy.org/en/latest/
[psycopg2]: https://www.psycopg.org/
[pymysql]: https://github.com/PyMySQL/PyMySQL
[asyncpg]: https://github.com/MagicStack/asyncpg
[aiomysql]: https://github.com/aio-libs/aiomysql
[aiosqlite]: https://github.com/jreese/aiosqlite

[databases]: https://github.com/encode/databases
[typesystem]: https://github.com/encode/typesystem
[typesystem-fields]: https://www.encode.io/typesystem/fields/
