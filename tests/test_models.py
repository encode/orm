import asyncio
import functools
import os

import pytest
import sqlalchemy

import orm
from databases import Database, DatabaseURL

assert "TEST_DATABASE_URLS" in os.environ, "TEST_DATABASE_URLS is not set."

DATABASE_URLS = [url.strip() for url in os.environ["TEST_DATABASE_URLS"].split(",")]

metadata = sqlalchemy.MetaData()


class User(orm.Model):
    __tablename__ = "users"
    __metadata__ = metadata

    id = orm.Integer(primary_key=True)
    name = orm.String(max_length=100)


class Product(orm.Model):
    __tablename__ = "product"
    __metadata__ = metadata

    id = orm.Integer(primary_key=True)
    name = orm.String(max_length=100)
    rating = orm.Integer(minimum=1, maximum=5)
    in_stock = orm.Boolean(default=False)


models = [User, product]


@pytest.fixture(autouse=True, scope="module")
def create_test_database():
    # Create test databases
    for url in DATABASE_URLS:
        database_url = DatabaseURL(url)
        if database_url.dialect == "mysql":
            url = str(database_url.replace(driver="pymysql"))
        engine = sqlalchemy.create_engine(url)
        metadata.create_all(engine)

    # Run the test suite
    yield

    # Drop test databases
    for url in DATABASE_URLS:
        database_url = DatabaseURL(url)
        if database_url.dialect == "mysql":
            url = str(database_url.replace(driver="pymysql"))
        engine = sqlalchemy.create_engine(url)
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


def test_model_pk():
    user = User(pk=1)
    assert user.pk == 1
    assert user.id == 1


@pytest.mark.parametrize("database_url", DATABASE_URLS)
@async_adapter
async def test_model_crud(database_url):
    async with Database(database_url, force_rollback=True) as database:
        for model in models:
            model.__database__ = database
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


@pytest.mark.parametrize("database_url", DATABASE_URLS)
@async_adapter
async def test_model_get(database_url):
    async with Database(database_url, force_rollback=True) as database:
        for model in models:
            model.__database__ = database
        with pytest.raises(orm.NoMatch):
            await User.objects.get()

        user = await User.objects.create(name="Tom")
        lookup = await User.objects.get()
        assert lookup == user

        user = await User.objects.create(name="Jane")
        with pytest.raises(orm.MultipleMatches):
            await User.objects.get()


@pytest.mark.parametrize("database_url", DATABASE_URLS)
@async_adapter
async def test_model_filter(database_url):
    async with Database(database_url, force_rollback=True) as database:
        for model in models:
            model.__database__ = database
        await User.objects.create(name="Tom")
        await User.objects.create(name="Jane")
        await User.objects.create(name="Lucy")

        user = await User.objects.get(name="Lucy")
        assert user.name == "Lucy"

        with pytest.raises(orm.NoMatch):
            await User.objects.get(name="Jim")

        await Product.objects.create(name="T-Shirt", rating=5, in_stock=True)
        await Product.objects.create(name="Dress", rating=4)
        await Product.objects.create(name="Coat", rating=3, in_stock=True)

        product = await Product.objects.get(name__iexact="t-shirt", rating=5)
        assert product.pk is not None
        assert product.name == "T-Shirt"
        assert product.rating == 5

        products = await Product.objects.all(rating__gte=2, in_stock=True)
        assert len(products) == 2

        products = await Product.objects.all(name__icontains="T")
        assert len(products) == 2

        # Test escaping % character from icontains, contains, and iexact
        await Product.objects.create(name="100%-Cotton", rating=3)
        await Product.objects.create(name="Cotton-100%-Egyptian", rating=3)
        await Product.objects.create(name="Cotton-100%", rating=3)
        products = Product.objects.filter(name__iexact="100%-cotton")
        assert await products.count() == 1

        products = Product.objects.filter(name__contains="%")
        assert await products.count() == 3

        products = Product.objects.filter(name__icontains="%")
        assert await products.count() == 3


@pytest.mark.parametrize("database_url", DATABASE_URLS)
@async_adapter
async def test_model_exists(database_url):
    async with Database(database_url, force_rollback=True) as database:
        for model in models:
            model.__database__ = database
        await User.objects.create(name="Tom")
        assert await User.objects.filter(name="Tom").exists() is True
        assert await User.objects.filter(name="Jane").exists() is False


@pytest.mark.parametrize("database_url", DATABASE_URLS)
@async_adapter
async def test_model_count(database_url):
    async with Database(database_url, force_rollback=True) as database:
        for model in models:
            model.__database__ = database
        await User.objects.create(name="Tom")
        await User.objects.create(name="Jane")
        await User.objects.create(name="Lucy")

        assert await User.objects.count() == 3
        assert await User.objects.filter(name__icontains="T").count() == 1


@pytest.mark.parametrize("database_url", DATABASE_URLS)
@async_adapter
async def test_model_limit(database_url):
    async with Database(database_url, force_rollback=True) as database:
        for model in models:
            model.__database__ = database
        await User.objects.create(name="Tom")
        await User.objects.create(name="Jane")
        await User.objects.create(name="Lucy")

        assert len(await User.objects.limit(2).all()) == 2


@pytest.mark.parametrize("database_url", DATABASE_URLS)
@async_adapter
async def test_model_limit_with_filter(database_url):
    async with Database(database_url, force_rollback=True) as database:
        for model in models:
            model.__database__ = database
        await User.objects.create(name="Tom")
        await User.objects.create(name="Tom")
        await User.objects.create(name="Tom")

        assert len(await User.objects.limit(2).filter(name__iexact='Tom').all()) == 2
