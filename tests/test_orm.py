import asyncio
import databases
import functools
import pytest
import sqlalchemy
from orm.core import Model


DATABASE_URL = "sqlite:///test.db"

metadata = sqlalchemy.MetaData()

notes = sqlalchemy.Table(
    "notes",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("text", sqlalchemy.String(length=100)),
    sqlalchemy.Column("completed", sqlalchemy.Boolean),
)

database = databases.Database(DATABASE_URL, force_rollback=True)


class Notes(Model):
    database = database
    table = notes

    def __init__(self, id, text, completed):
        self.id = id
        self.text = text
        self.completed = completed


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
async def test_queries():
    async with database:
        note = await Notes.create(id=None, text="example", completed=False)
        notes = await Notes.query().all()
        assert len(notes) == 1
        assert note[0].text == "example"
        await note.update(text="foo")
