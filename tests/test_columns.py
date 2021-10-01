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


class Product(orm.Model):
    registry = models
    fields = {
        "id": orm.Integer(primary_key=True),
        "uuid": orm.UUID(allow_null=True),
        "created": orm.DateTime(default=datetime.datetime.now),
        "created_day": orm.Date(default=datetime.date.today),
        "created_time": orm.Time(default=time),
        "data": orm.JSON(default={}),
        "description": orm.Text(allow_blank=True),
        "huge_number": orm.BigInteger(default=0),
        "price": orm.Decimal(max_digits=5, decimal_places=2, allow_null=True),
        "status": orm.Enum(StatusEnum, default=StatusEnum.DRAFT),
        "value": orm.Float(allow_null=True),
    }


class User(orm.Model):
    registry = models
    fields = {
        "id": orm.UUID(primary_key=True, default=uuid.uuid4),
        "name": orm.String(allow_null=True, max_length=16),
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
    product = await Product.objects.create()

    product = await Product.objects.get(pk=product.pk)
    assert product.created.year == datetime.datetime.now().year
    assert product.created_day == datetime.date.today()
    assert product.data == {}
    assert product.description == ""
    assert product.huge_number == 0
    assert product.price is None
    assert product.status == StatusEnum.DRAFT
    assert product.value is None
    assert product.uuid is None

    await product.update(
        data={"foo": 123},
        value=123.456,
        status=StatusEnum.RELEASED,
        price=decimal.Decimal("999.99"),
        uuid=uuid.UUID("01175cde-c18f-4a13-a492-21bd9e1cb01b"),
    )

    product = await Product.objects.get()
    assert product.value == 123.456
    assert product.data == {"foo": 123}
    assert product.status == StatusEnum.RELEASED
    assert product.price == decimal.Decimal("999.99")
    assert product.uuid == uuid.UUID("01175cde-c18f-4a13-a492-21bd9e1cb01b")


@pytest.mark.skipif(database.url.dialect == "sqlite", reason="Not supported on SQLite")
async def test_model_crud_with_non_integer_pk():
    user = await User.objects.create(name="Chris")

    assert isinstance(user.pk, uuid.UUID)
    assert await User.objects.get(pk=user.pk) == user
