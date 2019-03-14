# import asyncio
# import databases
# import functools
# import pytest
# import sqlalchemy
# from orm.core import Model, NoMatch, MultipleMatches
#
#
# DATABASE_URL = "sqlite:///test.db"
#
# metadata = sqlalchemy.MetaData()
#
# notes = sqlalchemy.Table(
#     "notes",
#     metadata,
#     sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
#     sqlalchemy.Column("text", sqlalchemy.String(length=100)),
#     sqlalchemy.Column("completed", sqlalchemy.Boolean),
# )
#
# database = databases.Database(DATABASE_URL, force_rollback=True)
#
#
# class Notes(Model):
#     database = database
#     table = notes
#
#     def __init__(self, id, text, completed):
#         self.id = id
#         self.text = text
#         self.completed = completed
#
#
# @pytest.fixture(autouse=True, scope="module")
# def create_test_database():
#     engine = sqlalchemy.create_engine(DATABASE_URL)
#     metadata.create_all(engine)
#     yield
#     metadata.drop_all(engine)
#
#
# def async_adapter(wrapped_func):
#     """
#     Decorator used to run async test cases.
#     """
#
#     @functools.wraps(wrapped_func)
#     def run_sync(*args, **kwargs):
#         loop = asyncio.get_event_loop()
#         task = wrapped_func(*args, **kwargs)
#         return loop.run_until_complete(task)
#
#     return run_sync
#
#
# @async_adapter
# async def test_queries():
#     async with database:
#         await Notes.create(text="example1", completed=False)
#         await Notes.create(text="example2", completed=True)
#         await Notes.create(text="example3", completed=False)
#
#         notes = await Notes.query().all()
#         assert len(notes) == 3
#         assert notes[0].text == "example1"
#         assert notes[0].completed is False
#
#         await notes[0].update(text="updated")
#
#         note = await Notes.query(id=notes[0].id).get()
#         assert note.text == "updated"
#         assert note.completed is False
#
#         with pytest.raises(NoMatch):
#             await Notes.query(text="nope").get()
#
#         with pytest.raises(MultipleMatches):
#             await Notes.query(completed=False).get()
