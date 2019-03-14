from orm.fields import Integer, String
from orm.models import Model


def test_model_class():
    class ExampleModel(Model):
        id = Integer(primary_key=True)
        name = String(max_length=100)

    assert list(ExampleModel.fields.keys()) == ["id", "name"]
    assert isinstance(ExampleModel.fields["id"], Integer)
    assert ExampleModel.fields["id"].primary_key is True
    assert isinstance(ExampleModel.fields["name"], String)
    assert ExampleModel.fields["name"].max_length == 100
