# ORM

**IN PROGRESS**

*Seriously, it's in progress. But it's a nice start.*

The `orm` package is an async ORM for Python, with support for Postgres,
MySQL, and SQLite.

It uses [SQLAlchemy core][sqlalchemy-core] for query building,
and [the `databases` package][databases] for cross-database async support.

Because ORM is built on SQLAlchemy core, you can use Alembic to provide
database migrations.

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
```

[sqlalchemy-core]: https://docs.sqlalchemy.org/en/latest/core/
[databases]: https://github.com/encode/databases
