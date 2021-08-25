import datetime
from enum import Enum

import databases
import pytest

import orm
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = databases.Database(DATABASE_URL)
models = orm.ModelRegistry(database=database)


def time():
    return datetime.datetime.now().time()


class StatusEnum(Enum):
    DRAFT = "Draft"
    RELEASED = "Released"


class Example(orm.Model):
    registry = models
    fields = {
        "id": orm.Integer(primary_key=True),
        "created": orm.DateTime(default=datetime.datetime.now),
        "created_day": orm.Date(default=datetime.date.today),
        "created_time": orm.Time(default=time),
        "data": orm.JSON(default={}),
        "description": orm.Text(allow_blank=True),
        "huge_number": orm.BigInteger(default=0),
        "status": orm.Enum(StatusEnum, default=StatusEnum.DRAFT),
        "value": orm.Float(allow_null=True),
    }


@pytest.fixture(autouse=True, scope="module")
def create_test_database():
    models.create_all()
    yield
    models.drop_all()


@pytest.fixture(autouse=True)
async def rollback_transactions():
    with database.force_rollback():
        async with database:
            yield


@pytest.mark.asyncio
async def test_model_crud():
    await Example.objects.create()

    example = await Example.objects.get()
    assert example.created.year == datetime.datetime.now().year
    assert example.created_day == datetime.date.today()
    assert example.data == {}
    assert example.description == ""
    assert example.huge_number == 0
    assert example.status == StatusEnum.DRAFT
    assert example.value is None

    await example.update(
        data={"foo": 123}, value=123.456, huge_number=9223372036854775807
    )
    example = await Example.objects.get()
    assert example.value == 123.456
    assert example.data == {"foo": 123}
