import databases
import pytest

import orm
from tests.settings import DATABASE_URL

database = databases.Database(DATABASE_URL)
models = orm.ModelRegistry(database=database)


class User(orm.Model):
    tablename = "users"
    registry = models
    fields = {
        "id": orm.Integer(primary_key=True),
        "name": orm.String(max_length=100),
    }


class Product(orm.Model):
    registry = models
    fields = {
        "id": orm.Integer(primary_key=True),
        "name": orm.String(max_length=100),
        "rating": orm.Integer(minimum=1, maximum=5),
        "in_stock": orm.Boolean(default=False),
    }


@pytest.fixture(autouse=True, scope="module")
def create_test_database():
    models.create_all()
    yield
    models.drop_all()


@pytest.fixture(autouse=True)
async def rollback_connections():
    with database.force_rollback():
        async with database:
            yield


def test_model_class():
    assert list(User.fields.keys()) == ["id", "name"]
    assert isinstance(User.fields["id"], orm.Integer)
    assert User.fields["id"].primary_key is True
    assert isinstance(User.fields["name"], orm.String)
    assert User.fields["name"].validator.max_length == 100

    with pytest.raises(ValueError):
        User(invalid="123")

    assert User(id=1) != Product(id=1)
    assert User(id=1) != User(id=2)
    assert User(id=1) == User(id=1)


def test_model_pk():
    user = User(pk=1)
    assert user.pk == 1
    assert user.id == 1


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_model_get():
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


@pytest.mark.asyncio
async def test_model_filter():
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


@pytest.mark.asyncio
async def test_model_exists():
    await User.objects.create(name="Tom")
    assert await User.objects.filter(name="Tom").exists() is True
    assert await User.objects.filter(name="Jane").exists() is False


@pytest.mark.asyncio
async def test_model_count():
    await User.objects.create(name="Tom")
    await User.objects.create(name="Jane")
    await User.objects.create(name="Lucy")

    assert await User.objects.count() == 3
    assert await User.objects.filter(name__icontains="T").count() == 1


@pytest.mark.asyncio
async def test_model_limit():
    await User.objects.create(name="Tom")
    await User.objects.create(name="Jane")
    await User.objects.create(name="Lucy")

    assert len(await User.objects.limit(2).all()) == 2


@pytest.mark.asyncio
async def test_model_limit_with_filter():
    await User.objects.create(name="Tom")
    await User.objects.create(name="Tom")
    await User.objects.create(name="Tom")

    assert len(await User.objects.limit(2).filter(name__iexact="Tom").all()) == 2


@pytest.mark.asyncio
async def test_offset():
    await User.objects.create(name="Tom")
    await User.objects.create(name="Jane")

    users = await User.objects.offset(1).limit(1).all()
    assert users[0].name == "Jane"


@pytest.mark.asyncio
async def test_model_first():
    tom = await User.objects.create(name="Tom")
    jane = await User.objects.create(name="Jane")

    assert await User.objects.first() == tom
    assert await User.objects.first(name="Jane") == jane
    assert await User.objects.filter(name="Jane").first() == jane
    assert await User.objects.filter(name="Lucy").first() is None
