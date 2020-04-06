import asyncio
import datetime
import functools

import pytest
import sqlalchemy

import databases
import orm

from tests.settings import DATABASE_URL


database = databases.Database(DATABASE_URL, force_rollback=True)
models = orm.ModelRegistry(database=database)

def time():
    return datetime.datetime.now().time()


class Example(orm.Model):
    tablename = "example"
    registry = models
    fields = {
        "id": orm.Integer(primary_key=True),
        "created": orm.DateTime(default=datetime.datetime.now),
        "created_day": orm.Date(default=datetime.date.today),
        "created_time": orm.Time(default=time),
        "description": orm.Text(allow_blank=True),
        "value": orm.Float(allow_null=True),
        "data": orm.JSON(default={})
    }


@pytest.fixture(autouse=True, scope="module")
def create_test_database():
    models.load()
    engine = sqlalchemy.create_engine(DATABASE_URL)
    models.metadata.create_all(engine)
    yield
    models.metadata.drop_all(engine)


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
    async with database:
        await Example.objects.create()

        example = await Example.objects.get()
        assert example.created.year == datetime.datetime.now().year
        assert example.created_day == datetime.date.today()
        assert example.description == ''
        assert example.value is None
        assert example.data == {}

        await example.update(data={"foo": 123}, value=123.456)
        example = await Example.objects.get()
        assert example.value == 123.456
        assert example.data == {"foo": 123}
