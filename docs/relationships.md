## ForeignKey

ORM supports loading and filtering across foreign keys.

Let's say you have the following models defined:

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
```

You can create some `Album` and `Track` instances:

```python
malibu = await Album.objects.create(name="Malibu")
await Track.objects.create(album=malibu, title="The Bird", position=1)
await Track.objects.create(album=malibu, title="Heart don't stand a chance", position=2)
await Track.objects.create(album=malibu, title="The Waters", position=3)

fantasies = await Album.objects.create(name="Fantasies")
await Track.objects.create(album=fantasies, title="Help I'm Alive", position=1)
await Track.objects.create(album=fantasies, title="Sick Muse", position=2)
```

To fetch an instance, without loading a foreign key relationship on it:

```python
track = await Track.objects.get(title="The Bird")

# We have an album instance, but it only has the primary key populated
print(track.album)       # Album(id=1) [sparse]
print(track.album.pk)    # 1
print(track.album.name)  # Raises AttributeError
```

You can load the relationship from the database:

```python
await track.album.load()
assert track.album.name == "Malibu"
```

You can also fetch an instance, loading the foreign key relationship with it:

```python
track = await Track.objects.select_related("album").get(title="The Bird")
assert track.album.name == "Malibu"
```

To fetch an instance, filtering across a foregin key relationship:

```python
tracks = Track.objects.filter(album__name="Fantasies")
assert len(tracks) == 2

tracks = Track.objects.filter(album__name__iexact="fantasies")
assert len(tracks) == 2
```
