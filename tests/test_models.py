import databases
import pytest
import sqlalchemy

import orm
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = databases.Database(DATABASE_URL, force_rollback=True)
metadata = sqlalchemy.MetaData()


class User(orm.Model):
    __tablename__ = "users"
    __metadata__ = metadata
    __database__ = database

    id = orm.Integer(primary_key=True)
    name = orm.String(max_length=100)


class Product(orm.Model):
    __tablename__ = "product"
    __metadata__ = metadata
    __database__ = database

    id = orm.Integer(primary_key=True)
    name = orm.String(max_length=100)
    rating = orm.Integer(minimum=1, maximum=5)
    in_stock = orm.Boolean(default=False)


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


async def test_model_crud():
    async with database:
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


async def test_model_get():
    async with database:
        with pytest.raises(orm.NoMatch):
            await User.objects.get()

        user = await User.objects.create(name="Tom")
        lookup = await User.objects.get()
        assert lookup == user

        user = await User.objects.create(name="Jane")
        with pytest.raises(orm.MultipleMatches):
            await User.objects.get()

        same_user = await User.objects.get(pk=user.id)
        assert same_user.id == user.id
        assert same_user.pk == user.pk


async def test_model_filter():
    async with database:
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

        products = await Product.objects.exclude(rating__gte=4, in_stock=True).all()
        assert len(products) == 2

        products = await Product.objects.exclude(in_stock=True).all()
        assert len(products) == 1

        products = await Product.objects.all(name__icontains="T")
        assert len(products) == 2

        products = await Product.objects.exclude(name__icontains="T").all()
        assert len(products) == 1

        # Test escaping % character from icontains, contains, and iexact
        await Product.objects.create(name="100%-Cotton", rating=3)
        await Product.objects.create(name="Cotton-100%-Egyptian", rating=3)
        await Product.objects.create(name="Cotton-100%", rating=3)
        products = Product.objects.filter(name__iexact="100%-cotton")
        assert await products.count() == 1

        products = Product.objects.exclude(name__iexact="100%-cotton")
        assert await products.count() == 5

        products = Product.objects.filter(name__contains="%")
        assert await products.count() == 3

        products = Product.objects.exclude(name__contains="%")
        assert await products.count() == 3

        products = Product.objects.filter(name__icontains="%")
        assert await products.count() == 3

        products = Product.objects.exclude(name__icontains="%")
        assert await products.count() == 3


async def test_model_order_by():
    async with database:
        await User.objects.create(name="Bob")
        await User.objects.create(name="Allen")
        await User.objects.create(name="Bob")

        users = await User.objects.order_by("name").all()
        assert users[0].name == "Allen"
        assert users[1].name == "Bob"

        users = await User.objects.order_by("-name").all()
        assert users[1].name == "Bob"
        assert users[2].name == "Allen"

        users = await User.objects.order_by("name", "-id").all()
        assert users[0].name == "Allen"
        assert users[1].name == "Bob"
        assert users[0].id < users[1].id

        users = await User.objects.filter(name="Bob").order_by("-id").all()
        assert users[0].name == "Bob"
        assert users[1].name == "Bob"
        assert users[0].id > users[1].id

        users = await User.objects.order_by("id").limit(1).all()
        assert users[0].name == "Bob"

        users = await User.objects.order_by("id").limit(1).offset(1).all()
        assert users[0].name == "Allen"


async def test_model_exists():
    async with database:
        await User.objects.create(name="Tom")
        assert await User.objects.filter(name="Tom").exists() is True
        assert await User.objects.filter(name="Jane").exists() is False


async def test_model_count():
    async with database:
        await User.objects.create(name="Tom")
        await User.objects.create(name="Jane")
        await User.objects.create(name="Lucy")

        assert await User.objects.count() == 3
        assert await User.objects.filter(name__icontains="T").count() == 1


async def test_model_limit():
    async with database:
        await User.objects.create(name="Tom")
        await User.objects.create(name="Jane")
        await User.objects.create(name="Lucy")

        assert len(await User.objects.limit(2).all()) == 2


async def test_model_limit_with_filter():
    async with database:
        await User.objects.create(name="Tom")
        await User.objects.create(name="Tom")
        await User.objects.create(name="Tom")

        assert len(await User.objects.limit(2).filter(name__iexact="Tom").all()) == 2


async def test_offset():
    async with database:
        await User.objects.create(name="Tom")
        await User.objects.create(name="Jane")

        users = await User.objects.offset(1).limit(1).all()
        assert users[0].name == "Jane"


async def test_model_first():
    async with database:
        tom = await User.objects.create(name="Tom")
        jane = await User.objects.create(name="Jane")

        assert await User.objects.first() == tom
        assert await User.objects.first(name="Jane") == jane
        assert await User.objects.filter(name="Jane").first() == jane
        assert await User.objects.filter(name="Lucy").first() is None


async def test_model_get_or_create():
    async with database:
        user, created = await User.objects.get_or_create(name="Tom")

        assert created is True
        assert await User.objects.get(pk=user.id) == user

        user, created = await User.objects.get_or_create(name="Tom")
        assert created is False
