from orm.fields import Integer, String
from orm.models import Model
import sqlalchemy


def test_model_class():
    metadata = sqlalchemy.MetaData()

    class Users(Model):
        __tablename__ = 'users'
        __metadata__ = metadata

        id = Integer(primary_key=True)
        name = String(max_length=100)

    assert list(Users.fields.keys()) == ["id", "name"]
    assert isinstance(Users.fields["id"], Integer)
    assert Users.fields["id"].primary_key is True
    assert isinstance(Users.fields["name"], String)
    assert Users.fields["name"].max_length == 100
    assert isinstance(Users.__table__, sqlalchemy.Table)
