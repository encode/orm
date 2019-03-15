import asyncio
import functools
import pytest

import databases
import pytest
import sqlalchemy

import orm


DATABASE_URL = "sqlite:///test.db"
database = databases.Database(DATABASE_URL, force_rollback=True)
metadata = sqlalchemy.MetaData()


class User(orm.Model):
    __tablename__ = "users"
    __metadata__ = metadata
    __database__ = database

    id = orm.Integer(primary_key=True)
    name = orm.String(max_length=100)


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


def test_model_class():
    assert list(User.fields.keys()) == ["id", "name"]
    assert isinstance(User.fields["id"], orm.Integer)
    assert User.fields["id"].primary_key is True
    assert isinstance(User.fields["name"], orm.String)
    assert User.fields["name"].max_length == 100
    assert isinstance(User.__table__, sqlalchemy.Table)


@async_adapter
async def test_model_crud():
    users = await User.objects.all()
    assert users == []

    user = await User.objects.create(name="Tom")
    users = await User.objects.all()
    assert user.name == "Tom"
    assert user.pk is not None
    assert users == [user]

    lookup = await User.objects.get()
    assert lookup == user

    await user.update(name="Jane")
    users = await User.objects.all()
    assert user.name == "Jane"
    assert user.pk is not None
    assert users == [user]

    await user.delete()
    users = await User.objects.all()
    assert users == []


@async_adapter
async def test_model_get():
    with pytest.raises(orm.NoMatch):
        await User.objects.get()

    user = await User.objects.create(name="Tom")
    lookup = await User.objects.get()
    assert lookup == user

    user = await User.objects.create(name="Jane")
    with pytest.raises(orm.MultipleMatches):
        await User.objects.get()
