import datetime
import decimal
import uuid
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
        "uuid": orm.UUID(primary_key=True, default=uuid.uuid4),
        "created": orm.DateTime(default=datetime.datetime.now),
        "created_day": orm.Date(default=datetime.date.today),
        "created_time": orm.Time(default=time),
        "data": orm.JSON(default={}),
        "description": orm.Text(allow_blank=True),
        "huge_number": orm.BigInteger(default=0),
        "number": orm.Integer(allow_null=True),
        "price": orm.Decimal(max_digits=5, decimal_places=2, allow_null=True),
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


async def test_model_crud():
    await Example.objects.create()

    example = await Example.objects.get()
    assert example.created.year == datetime.datetime.now().year
    assert example.created_day == datetime.date.today()
    assert example.data == {}
    assert example.description == ""
    assert example.huge_number == 0
    assert example.number is None
    assert example.price is None
    assert example.status == StatusEnum.DRAFT
    assert example.value is None
    assert isinstance(example.uuid, uuid.UUID)

    await example.update(
        data={"foo": 123},
        value=123.456,
        number=10,
        status=StatusEnum.RELEASED,
        price=decimal.Decimal("999.99"),
    )

    example = await Example.objects.get()
    assert example.value == 123.456
    assert example.number == 10
    assert example.data == {"foo": 123}
    assert example.status == StatusEnum.RELEASED
    assert example.price == decimal.Decimal("999.99")
