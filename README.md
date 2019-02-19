# ORM

```python
models = orm.Models(default_database=database)


class Notes(models.Model):
    id = orm.Integer(primary_key=True)
    text = orm.String(max_length=100, allow_empty=False)
    completed = orm.Boolean(default=False)


notes = await Notes.query().all()
note = await Notes.create(text="Buy the milk", completed=False)
await note.update(completed=True)
await Notes.query(id==note.id).get()
```
