## ForeignKey

### Defining and querying relationships

ORM supports loading and filtering across foreign keys.

Let's say you have the following models defined:

```python
import databases
import orm

database = databases.Database("sqlite:///db.sqlite")
models = orm.ModelRegistry(database=database)


class Album(orm.Model):
    tablename = "albums"
    registry = models
    fields = {
        "id": orm.Integer(primary_key=True),
        "name": orm.String(max_length=100),
    }


class Track(orm.Model):
    tablename = "tracks"
    registry = models
    fields = {
        "id": orm.Integer(primary_key=True),
        "album": orm.ForeignKey(Album),
        "title": orm.String(max_length=100),
        "position": orm.Integer(),
    }
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

To fetch an instance, filtering across a foreign key relationship:

```python
tracks = Track.objects.filter(album__name="Fantasies")
assert len(tracks) == 2

tracks = Track.objects.filter(album__name__iexact="fantasies")
assert len(tracks) == 2
```

### ForeignKey constraints

`ForeigknKey` supports specifying a constraint through `on_delete` argument.

This will result in a SQL `ON DELETE` query being generated when the referenced object is removed.

With the following definition:

```python
class Album(orm.Model):
    tablename = "albums"
    registry = models
    fields = {
        "id": orm.Integer(primary_key=True),
        "name": orm.String(max_length=100),
    }


class Track(orm.Model):
    tablename = "tracks"
    registry = models
    fields = {
        "id": orm.Integer(primary_key=True),
        "album": orm.ForeignKey(Album, on_delete=orm.CASCADE),
        "title": orm.String(max_length=100),
    }
```

`Track` model defines `orm.ForeignKey(Album, on_delete=orm.CASCADE)` so whenever an `Album` object is removed,
all `Track` objects referencing that `Album`  will also be removed.

Available options for `on_delete` are:

* `CASCADE`

This will remove all referencing objects.

* `RESTRICT`

This will restrict removing referenced object, if there are objects referencing it.
A database driver exception will be raised.

* `SET NULL`

This will set referencing objects `ForeignKey` column to `NULL`.
The `ForeignKey` defined here should also have `allow_null=True`.


## OneToOne

Creating a  `OneToOne` relationship between models, this is basically
the same as `ForeignKey` but it uses `unique=True` on the ForeignKey column:

```python
class Profile(orm.Model):
    registry = models
    fields = {
        "id": orm.Integer(primary_key=True),
        "website": orm.String(max_length=100),
    }


class Person(orm.Model):
    registry = models
    fields = {
        "id": orm.Integer(primary_key=True),
        "email": orm.String(max_length=100),
        "profile": orm.OneToOne(Profile),
    }
```

You can create a `Profile` and `Person` instance:

```python
profile = await Profile.objects.create(website="https://encode.io")
await Person.objects.create(email="info@encode.io", profile=profile)
```

Now creating another `Person` using the same `profile` will fail
and will raise an exception:

```python
await Person.objects.create(email="info@encode.io", profile=profile)
```

`OneToOne` accepts the same `on_delete` parameters as `ForeignKey` which is
described [here](#foreignkey-constraints).
