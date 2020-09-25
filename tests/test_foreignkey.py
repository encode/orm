import asyncio
import functools

import databases
import pytest
import sqlalchemy

import orm
from tests.settings import DATABASE_URL

database = databases.Database(DATABASE_URL, force_rollback=True)
metadata = sqlalchemy.MetaData()


class Album(orm.Model):
    __tablename__ = "album"
    __metadata__ = metadata
    __database__ = database

    id = orm.Integer(primary_key=True)
    name = orm.String(max_length=100)


class Track(orm.Model):
    __tablename__ = "track"
    __metadata__ = metadata
    __database__ = database

    id = orm.Integer(primary_key=True)
    album = orm.ForeignKey(Album)
    title = orm.String(max_length=100)
    position = orm.Integer()


class Organisation(orm.Model):
    __tablename__ = "org"
    __metadata__ = metadata
    __database__ = database

    id = orm.Integer(primary_key=True)
    ident = orm.String(max_length=100)


class Team(orm.Model):
    __tablename__ = "team"
    __metadata__ = metadata
    __database__ = database

    id = orm.Integer(primary_key=True)
    org = orm.ForeignKey(Organisation)
    name = orm.String(max_length=100)


class Member(orm.Model):
    __tablename__ = "member"
    __metadata__ = metadata
    __database__ = database

    id = orm.Integer(primary_key=True)
    team = orm.ForeignKey(Team)
    email = orm.String(max_length=100)


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
async def test_model_crud():
    async with database:
        album = await Album.objects.create(name="Malibu")
        await Track.objects.create(album=album, title="The Bird", position=1)
        await Track.objects.create(
            album=album, title="Heart don't stand a chance", position=2
        )
        await Track.objects.create(album=album, title="The Waters", position=3)

        track = await Track.objects.get(title="The Bird")
        assert track.album.pk == album.pk
        assert not hasattr(track.album, "name")
        await track.album.load()
        assert track.album.name == "Malibu"


@async_adapter
async def test_select_related():
    async with database:
        album = await Album.objects.create(name="Malibu")
        await Track.objects.create(album=album, title="The Bird", position=1)
        await Track.objects.create(
            album=album, title="Heart don't stand a chance", position=2
        )
        await Track.objects.create(album=album, title="The Waters", position=3)

        fantasies = await Album.objects.create(name="Fantasies")
        await Track.objects.create(album=fantasies, title="Help I'm Alive", position=1)
        await Track.objects.create(album=fantasies, title="Sick Muse", position=2)
        await Track.objects.create(album=fantasies, title="Satellite Mind", position=3)

        track = await Track.objects.select_related("album").get(title="The Bird")
        assert track.album.name == "Malibu"

        tracks = await Track.objects.select_related("album").all()
        assert len(tracks) == 6


@async_adapter
async def test_fk_filter():
    async with database:
        malibu = await Album.objects.create(name="Malibu")
        await Track.objects.create(album=malibu, title="The Bird", position=1)
        await Track.objects.create(
            album=malibu, title="Heart don't stand a chance", position=2
        )
        await Track.objects.create(album=malibu, title="The Waters", position=3)

        fantasies = await Album.objects.create(name="Fantasies")
        await Track.objects.create(album=fantasies, title="Help I'm Alive", position=1)
        await Track.objects.create(album=fantasies, title="Sick Muse", position=2)
        await Track.objects.create(album=fantasies, title="Satellite Mind", position=3)

        tracks = (
            await Track.objects.select_related("album")
            .filter(album__name="Fantasies")
            .all()
        )
        assert len(tracks) == 3
        for track in tracks:
            assert track.album.name == "Fantasies"

        tracks = (
            await Track.objects.select_related("album")
            .filter(album__name__icontains="fan")
            .all()
        )
        assert len(tracks) == 3
        for track in tracks:
            assert track.album.name == "Fantasies"

        tracks = await Track.objects.filter(album__name__icontains="fan").all()
        assert len(tracks) == 3
        for track in tracks:
            assert track.album.name == "Fantasies"

        tracks = await Track.objects.filter(album=malibu).select_related("album").all()
        assert len(tracks) == 3
        for track in tracks:
            assert track.album.name == "Malibu"


@async_adapter
async def test_multiple_fk():
    async with database:
        acme = await Organisation.objects.create(ident="ACME Ltd")
        red_team = await Team.objects.create(org=acme, name="Red Team")
        blue_team = await Team.objects.create(org=acme, name="Blue Team")
        await Member.objects.create(team=red_team, email="a@example.org")
        await Member.objects.create(team=red_team, email="b@example.org")
        await Member.objects.create(team=blue_team, email="c@example.org")
        await Member.objects.create(team=blue_team, email="d@example.org")

        other = await Organisation.objects.create(ident="Other ltd")
        team = await Team.objects.create(org=other, name="Green Team")
        await Member.objects.create(team=team, email="e@example.org")

        members = (
            await Member.objects.select_related("team__org")
            .filter(team__org__ident="ACME Ltd")
            .all()
        )
        assert len(members) == 4
        for member in members:
            assert member.team.org.ident == "ACME Ltd"
