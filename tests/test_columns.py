import asyncio
import datetime
import decimal
import functools
from enum import Enum

import databases
import pytest
import sqlalchemy

import orm
from tests.settings import DATABASE_URL

database = databases.Database(DATABASE_URL, force_rollback=True)
metadata = sqlalchemy.MetaData()
decimal.getcontext().prec = 8


def time():
    return datetime.datetime.now().time()


class StatusEnum(Enum):
    DRAFT = "Draft"
    RELEASED = "Released"


class Example(orm.Model):
    __tablename__ = "example"
    __metadata__ = metadata
    __database__ = database

    id = orm.Integer(primary_key=True)
    huge_number = orm.BigInteger(default=9223372036854775807)
    created = orm.DateTime(default=datetime.datetime.now)
    created_day = orm.Date(default=datetime.date.today)
    created_time = orm.Time(default=time)
    description = orm.Text(allow_blank=True)
    value = orm.Float(allow_null=True)
    price = orm.Decimal(allow_null=True, scale=8, precision=18)
    data = orm.JSON(default={})
    status = orm.Enum(StatusEnum, default=StatusEnum.DRAFT)


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
        loop = asyncio.new_event_loop()
        task = wrapped_func(*args, **kwargs)
        return loop.run_until_complete(task)

    return run_sync


@async_adapter
async def test_model_crud():
    async with database:
        await Example.objects.create()

        example = await Example.objects.get()
        assert example.huge_number == 9223372036854775807
        assert example.created.year == datetime.datetime.now().year
        assert example.created_day == datetime.date.today()
        assert example.description == ""
        assert example.value is None
        assert example.price is None
        assert example.data == {}
        assert example.status == StatusEnum.DRAFT
        await example.update(
            data={"foo": 123},
            value=123.456,
            status=StatusEnum.RELEASED,
            price=decimal.getcontext().create_decimal(0.12345678),
        )
        example = await Example.objects.get()
        assert example.value == 123.456
        assert example.price == decimal.getcontext().create_decimal(0.12345678)
        assert example.data == {"foo": 123}
        assert example.status == StatusEnum.RELEASED
