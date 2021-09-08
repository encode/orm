import datetime
import decimal
import uuid
from enum import Enum

import databases
import pytest
import sqlalchemy

import orm
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = databases.Database(DATABASE_URL, force_rollback=True)
metadata = sqlalchemy.MetaData()


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
    uuid = orm.UUID(allow_null=True)
    huge_number = orm.BigInteger(default=9223372036854775807)
    created = orm.DateTime(default=datetime.datetime.now)
    created_day = orm.Date(default=datetime.date.today)
    created_time = orm.Time(default=time)
    description = orm.Text(allow_blank=True)
    value = orm.Float(allow_null=True)
    price = orm.Decimal(max_digits=5, decimal_places=2, allow_null=True)
    data = orm.JSON(default={})
    status = orm.Enum(StatusEnum, default=StatusEnum.DRAFT)


@pytest.fixture(autouse=True, scope="module")
def create_test_database():
    database_url = databases.DatabaseURL(DATABASE_URL)
    if database_url.scheme == "mysql":
        url = str(database_url.replace(driver="pymysql"))
    else:
        url = str(database_url)

    engine = sqlalchemy.create_engine(url)
    metadata.create_all(engine)
    yield
    metadata.drop_all(engine)


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
        assert example.uuid is None

        await example.update(
            data={"foo": 123},
            value=123.456,
            status=StatusEnum.RELEASED,
            price=decimal.Decimal("999.99"),
            uuid=uuid.UUID("01175cde-c18f-4a13-a492-21bd9e1cb01b"),
        )

        example = await Example.objects.get()
        assert example.value == 123.456
        assert example.data == {"foo": 123}
        assert example.status == StatusEnum.RELEASED
        assert example.price == decimal.Decimal("999.99")
        assert example.uuid == uuid.UUID("01175cde-c18f-4a13-a492-21bd9e1cb01b")
