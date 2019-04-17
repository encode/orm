# ORM

<p>
<a href="https://travis-ci.org/encode/orm">
    <img src="https://travis-ci.org/encode/orm.svg?branch=master" alt="Build Status">
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

# Create the database
engine = sqlalchemy.create_engine(str(database.url))
metadata.create_all(engine)

# .create()
await Note.objects.create(text="Buy the groceries.", completed=False)
await Note.objects.create(text="Call Mum.", completed=True)
await Note.objects.create(text="Send invoices.", completed=True)

# .all()
notes = await Note.objects.all()

# .filter()
notes = await Note.objects.filter(completed=True).all()

# exact, iexact, contains, icontains, lt, lte, gt, gte, in
notes = await Note.objects.filter(text__icontains="mum").all()

# .get()
note = await Note.objects.get(id=1)

# .update()
await note.update(completed=True)

# .delete()
await note.delete()

# 'pk' always refers to the primary key
note = await Note.objects.get(pk=2)
note.pk  # 2
```

ORM supports loading and filtering across foreign keys...

```python
import databases
import orm
import sqlalchemy

database = databases.Database("sqlite:///db.sqlite")
metadata = sqlalchemy.MetaData()


class Album(orm.Model):
    __tablename__ = "album"
    __metadata__ = metadata
    __database__ = database

    id = orm.Integer(primary_key=True)
    name = orm.String(max_length=100)


class Track(orm.Model):
    __tablename__ = "track"
    __metadata__ = metadata
    __database__ = database

    id = orm.Integer(primary_key=True)
    album = orm.ForeignKey(Album)
    title = orm.String(max_length=100)
    position = orm.Integer()


# Create some records to work with.
malibu = await Album.objects.create(name="Malibu")
await Track.objects.create(album=malibu, title="The Bird", position=1)
await Track.objects.create(album=malibu, title="Heart don't stand a chance", position=2)
await Track.objects.create(album=malibu, title="The Waters", position=3)

fantasies = await Album.objects.create(name="Fantasies")
await Track.objects.create(album=fantasies, title="Help I'm Alive", position=1)
await Track.objects.create(album=fantasies, title="Sick Muse", position=2)


# Fetch an instance, without loading a foreign key relationship on it.
track = await Track.objects.get(title="The Bird")

# We have an album instance, but it only has the primary key populated
print(track.album)       # Album(id=1) [sparse]
print(track.album.pk)    # 1
print(track.album.name)  # Raises AttributeError

# Load the relationship from the database
await track.album.load()
assert track.album.name == "Malibu"

# This time, fetch an instance, loading the foreign key relationship.
track = await Track.objects.select_related("album").get(title="The Bird")
assert track.album.name == "Malibu"

# Fetch instances, with a filter across an FK relationship.
tracks = Track.objects.filter(album__name="Fantasies")
assert len(tracks) == 2

# Fetch instances, with a filter and operator across an FK relationship.
tracks = Track.objects.filter(album__name__iexact="fantasies")
assert len(tracks) == 2

# Limit a query
tracks = await Track.objects.limit(1).all()
assert len(tracks) == 1
```

## Data types

The following keyword arguments are supported on all field types.

* `primary_key`
* `allow_null`
* `default`
* `index`
* `unique`

All fields are required unless one of the following is set:

* `allow_null` - Creates a nullable column. Sets the default to `None`.
* `allow_blank` - Allow empty strings to validate. Sets the default to `""`.
* `default` - Set a default value for the field.

The following column types are supported.
See TypeSystem for [type-specific validation keyword arguments][typesystem-fields].

* `orm.String(max_length)`
* `orm.Text()`
* `orm.Boolean()`
* `orm.Integer()`
* `orm.Float()`
* `orm.Date()`
* `orm.Time()`
* `orm.DateTime()`
* `orm.JSON()`

[sqlalchemy-core]: https://docs.sqlalchemy.org/en/latest/core/
[databases]: https://github.com/encode/databases
[typesystem]: https://github.com/encode/typesystem
[typesystem-fields]: https://www.encode.io/typesystem/fields/
