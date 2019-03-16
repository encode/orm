import asyncio
import functools

import databases
import pytest
import sqlalchemy

import orm

DATABASE_URL = "sqlite:///test.db"
database = databases.Database(DATABASE_URL, force_rollback=True)
metadata = sqlalchemy.MetaData()


class Album(orm.Model):
    __tablename__ = "users"
    __metadata__ = metadata
    __database__ = database

    id = orm.Integer(primary_key=True)
    name = orm.String(max_length=100)


class Track(orm.Model):
    __tablename__ = "product"
    __metadata__ = metadata
    __database__ = database

    id = orm.Integer(primary_key=True)
    album = orm.ForeignKey(Album)
    title = orm.String(max_length=100)
    position = orm.Integer()


@pytest.fixture(autouse=True, scope="module")
def create_test_database():
    engine = sqlalchemy.create_engine(DATABASE_URL)
    metadata.create_all(engine)
    yield
    metadata.drop_all(engine)


def async_adapter(wrapped_func):
    """
    Decorator used to run async test cases.
    """

    @functools.wraps(wrapped_func)
    def run_sync(*args, **kwargs):
        loop = asyncio.get_event_loop()
        task = wrapped_func(*args, **kwargs)
        return loop.run_until_complete(task)

    return run_sync


@async_adapter
async def test_model_crud():
    album = await Album.objects.create(name="The coders")
    await Track.objects.create(album=album, title="Foo", position=1)
    await Track.objects.create(album=album, title="Bar", position=2)
    await Track.objects.create(album=album, title="Baz", position=3)

    track = await Track.objects.get(title="Foo")
    assert track.album.pk == album.pk
    assert not hasattr(track.album, 'name')
    await track.album.load()
    assert track.album.name == "The coders"
