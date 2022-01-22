import sqlite3

import asyncpg
import databases
import pymysql
import pytest

import orm
from tests.settings import DATABASE_URL

pytestmark = pytest.mark.anyio

database = databases.Database(DATABASE_URL)
models = orm.ModelRegistry(database=database)


class Album(orm.Model):
    registry = models
    fields = {
        "id": orm.Integer(primary_key=True),
        "name": orm.String(max_length=100),
    }


class Track(orm.Model):
    registry = models
    fields = {
        "id": orm.Integer(primary_key=True),
        "album": orm.ForeignKey("Album", on_delete=orm.CASCADE),
        "title": orm.String(max_length=100),
        "position": orm.Integer(),
    }


class Organisation(orm.Model):
    registry = models
    fields = {
        "id": orm.Integer(primary_key=True),
        "ident": orm.String(max_length=100),
    }


class Team(orm.Model):
    registry = models
    fields = {
        "id": orm.Integer(primary_key=True),
        "org": orm.ForeignKey(Organisation, on_delete=orm.RESTRICT),
        "name": orm.String(max_length=100),
    }


class Member(orm.Model):
    registry = models
    fields = {
        "id": orm.Integer(primary_key=True),
        "team": orm.ForeignKey(Team, on_delete=orm.SET_NULL, allow_null=True),
        "email": orm.String(max_length=100),
    }


class Profile(orm.Model):
    registry = models
    fields = {
        "id": orm.Integer(primary_key=True),
        "website": orm.String(max_length=100),
    }


class Person(orm.Model):
    registry = models
    fields = {
        "id": orm.Integer(primary_key=True),
        "email": orm.String(max_length=100),
        "profile": orm.OneToOne(Profile),
    }


@pytest.fixture(autouse=True, scope="module")
async def create_test_database():
    await models.create_all()
    yield
    await models.drop_all()


@pytest.fixture(autouse=True)
async def rollback_connections():
    with database.force_rollback():
        async with database:
            yield


async def test_model_crud():
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


async def test_select_related():
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


async def test_fk_filter():
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


async def test_multiple_fk():
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


async def test_queryset_delete_with_fk():
    malibu = await Album.objects.create(name="Malibu")
    await Track.objects.create(album=malibu, title="The Bird", position=1)

    wall = await Album.objects.create(name="The Wall")
    await Track.objects.create(album=wall, title="The Wall", position=1)

    await Track.objects.filter(album=malibu).delete()
    assert await Track.objects.filter(album=malibu).count() == 0
    assert await Track.objects.filter(album=wall).count() == 1


async def test_queryset_update_with_fk():
    malibu = await Album.objects.create(name="Malibu")
    wall = await Album.objects.create(name="The Wall")
    await Track.objects.create(album=malibu, title="The Bird", position=1)

    await Track.objects.filter(album=malibu).update(album=wall)
    assert await Track.objects.filter(album=malibu).count() == 0
    assert await Track.objects.filter(album=wall).count() == 1


@pytest.mark.skipif(database.url.dialect == "sqlite", reason="Not supported on SQLite")
async def test_on_delete_cascade():
    album = await Album.objects.create(name="The Wall")
    await Track.objects.create(album=album, title="Hey You", position=1)
    await Track.objects.create(album=album, title="Breathe", position=2)

    assert await Track.objects.count() == 2

    await album.delete()

    assert await Track.objects.count() == 0


@pytest.mark.skipif(database.url.dialect == "sqlite", reason="Not supported on SQLite")
async def test_on_delete_retstrict():
    organisation = await Organisation.objects.create(ident="Encode")
    await Team.objects.create(org=organisation, name="Maintainers")

    exceptions = (
        asyncpg.exceptions.ForeignKeyViolationError,
        pymysql.err.IntegrityError,
    )

    with pytest.raises(exceptions):
        await organisation.delete()


@pytest.mark.skipif(database.url.dialect == "sqlite", reason="Not supported on SQLite")
async def test_on_delete_set_null():
    organisation = await Organisation.objects.create(ident="Encode")
    team = await Team.objects.create(org=organisation, name="Maintainers")
    await Member.objects.create(email="member@encode.io", team=team)

    await team.delete()

    member = await Member.objects.first()
    assert member.team.pk is None


async def test_one_to_one_crud():
    profile = await Profile.objects.create(website="https://encode.io")
    await Person.objects.create(email="info@encode.io", profile=profile)

    person = await Person.objects.get(email="info@encode.io")
    assert person.profile.pk == profile.pk
    assert not hasattr(person.profile, "website")

    await person.profile.load()
    assert person.profile.website == "https://encode.io"

    exceptions = (
        asyncpg.exceptions.UniqueViolationError,
        pymysql.err.IntegrityError,
        sqlite3.IntegrityError,
    )

    with pytest.raises(exceptions):
        await Person.objects.create(email="contact@encode.io", profile=profile)


async def test_nullable_foreign_key():
    await Member.objects.create(email="dev@encode.io")

    member = await Member.objects.get()

    assert member.email == "dev@encode.io"
    assert member.team.pk is None
