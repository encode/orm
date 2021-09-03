## Queryset methods

ORM supports a range of query methods which can be chained together.

Let's say you have the following model defined:

```python
import databases
import orm
import sqlalchemy

database = databases.Database("sqlite:///db.sqlite")
metadata = sqlalchemy.MetaData()


class Note(orm.Model):
    __tablename__ = "notes"
    __database__ = database
    __metadata__ = metadata

    id = orm.Integer(primary_key=True)
    text = orm.String(max_length=100)
    completed = orm.Boolean(default=False)
```

You can use the following queryset methods:

### Creating instances

You need to pass the required model attributes and values to the `.create()` method:

```python
await Note.objects.create(text="Buy the groceries.", completed=False)
await Note.objects.create(text="Call Mum.", completed=True)
await Note.objects.create(text="Send invoices.", completed=True)
```

### Querying instances

#### .all()

To retrieve all the instances:

```python
notes = await Note.objects.all()
```

#### .get()

To get only one instance:

```python
note = await Note.objects.get(id=1)
```

**Note**: `.get()` expects to find only one instance. This can raise `NoMatch` or `MultipleMatches`.

#### .first()

This will return the first instance or `None`:

```python
note = await Note.objects.filter(completed=True).first()
```

`pk` always refers to the model's primary key field:

```python
note = await Note.objects.get(pk=2)
note.pk  # 2
```

#### .filter()

To filter instances:

```python
notes = await Note.objects.filter(completed=True).all()
```

There are some special operators defined automatically on every column:

* `in` - SQL `IN` operator.
* `exact` - filter instances matching exact value.
* `iexact` - same as `exact` but case-insensitive.
* `contains` - filter instances containing value.
* `icontains` - same as `contains` but case-insensitive.
* `lt` - filter instances having value `Less Than`.
* `lte` - filter instances having value `Less Than Equal`.
* `gt` - filter instances having value `Greater Than`.
* `gte` - filter instances having value `Greater Than Equal`.

Example usage:

```python
notes = await Note.objects.filter(text__icontains="mum").all()

notes = await Note.objects.filter(id__in=[1, 2, 3]).all()
```

#### .exclude()

To exclude instances:

```python
notes = await Note.objects.exclude(completed=False).all()
```

#### .order_by()

To order query results:

```python
notes = await Note.objects.order_by("text", "-id").all()
```

**Note**: This will sort by ascending `text` and descending `id`.

#### .limit()

To limit number of results:

```python
await Note.objects.limit(1).all()
```

#### .offset()

To apply offset to query results:

```python
await Note.objects.offset(1).all()
```

As mentioned before, you can chain multiple queryset methods together to form a query.
As an exmaple:

```python
await Note.objects.order_by("id").limit(1).offset(1).all()
await Note.objects.filter(text__icontains="mum").limit(2).all()
```

### Updating instances

`.update()` method is defined on model instances.
You need to query to get a `Note` instance first:

```python
note = await Note.objects.first()
```

Then update the field(s):

```python
await note.update(completed=True)
```

### Deleting instances

`.delete()` method is defined on model instances.
You need to query to get a `Note` instance first:

```python
note = await Note.objects.first()
```

Then delete the instance:

```python
await note.delete()
```
