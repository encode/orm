import asyncio
import datetime
import functools
from orm.fields import UUIDField

import pytest
import sqlalchemy
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql.psycopg2 import _PGUUID

import databases
import orm

import uuid

from tests.settings import DATABASE_URL


database = databases.Database(DATABASE_URL, force_rollback=True)
metadata = sqlalchemy.MetaData()


def time():
    return datetime.datetime.now().time()


class Example(orm.Model):
    __tablename__ = "example"
    __metadata__ = metadata
    __database__ = database

    id = orm.Integer(primary_key=True)
    created = orm.DateTime(default=datetime.datetime.now)
    created_day = orm.Date(default=datetime.date.today)
    created_time = orm.Time(default=time)
    description = orm.Text(allow_blank=True)
    value = orm.Float(allow_null=True)
    data = orm.JSON(default={})
    uuid = orm.UUID(default=uuid.uuid4())


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
    async with database:
        _uuid = uuid.uuid4()

        await Example.objects.create(uuid=_uuid)

        example = await Example.objects.get()
        assert example.created.year == datetime.datetime.now().year
        assert example.created_day == datetime.date.today()
        assert example.description == ''
        assert example.value is None
        assert example.data == {}
        assert isinstance(example.uuid, uuid.UUID)
        assert example.uuid == _uuid

        await example.update(data={"foo": 123}, value=123.456, uuid=uuid.uuid4())
        example = await Example.objects.get()
        assert example.value == 123.456
        assert example.data == {"foo": 123}
        assert example.uuid != _uuid


def test_uuid_field():
    type = UUIDField()
    assert isinstance(type.load_dialect_impl(postgresql.dialect()), _PGUUID)
    data = uuid.uuid4()

    assert type.process_bind_param(data, postgresql.dialect()) == str(data)
    assert type.process_bind_param(str(data), postgresql.dialect()) == str(data)
    assert type.process_bind_param(int(data), postgresql.dialect()) == str(data)
    assert type.process_bind_param(data.bytes, postgresql.dialect()) == str(data)
    assert type.process_bind_param(None, postgresql.dialect()) == None

    assert type.process_result_value(str(data), postgresql.dialect()) == data
    assert type.process_result_value(None, postgresql.dialect()) == None
