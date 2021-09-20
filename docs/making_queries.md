Let's say you have the following model defined:

```python
import databases
import orm

database = databases.Database("sqlite:///db.sqlite")
models = orm.ModelRegistry(database=database)


class Note(orm.Model):
    tablename = "notes"
    registry = models
    fields = {
        "id": orm.Integer(primary_key=True),
        "text": orm.String(max_length=100),
        "completed": orm.Boolean(default=False),
    }
```

ORM supports two types of queryset methods.
Some queryset methods return another queryset and can be chianed together like `.filter()`:

```python
Note.objects.filter().filter()
```

Other queryset methods return results and should be used as final method on the queryset like `.all()`:

```python
Note.objects.filter().all()
```

## Returning Querysets

### .exclude()

To exclude instances:

```python
notes = await Note.objects.exclude(completed=False).all()
```

### .filter()

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

### .limit()

To limit number of results:

```python
await Note.objects.limit(1).all()
```

### .offset()

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

### .order_by()

To order query results:

```python
notes = await Note.objects.order_by("text", "-id").all()
```

!!! note
    This will sort by ascending `text` and descending `id`.

## Returning results

### .all()

To retrieve all the instances:

```python
notes = await Note.objects.all()
```

### .create()

You need to pass the required model attributes and values to the `.create()` method:

```python
await Note.objects.create(text="Buy the groceries.", completed=False)
await Note.objects.create(text="Call Mum.", completed=True)
await Note.objects.create(text="Send invoices.", completed=True)
```

### .delete()

You can `delete` instances by calling `.delete()` on a queryset:

```python
await Note.objects.filter(completed=True).delete()
```

It's not very common, but to delete all rows in a table:

```python
await Note.objects.delete()
```

You can also call delete on a queried instance:

```python
note = await Note.objects.first()

await note.delete()
```

### .exists()

To check if any instances matching the query exist. Returns `True` or `False`.

```python
await Note.objects.filter(completed=True).exists()
```

### .first()

This will return the first instance or `None`:

```python
note = await Note.objects.filter(completed=True).first()
```

`pk` always refers to the model's primary key field:

```python
note = await Note.objects.get(pk=2)
note.pk  # 2
```

### .get()

To get only one instance:

```python
note = await Note.objects.get(id=1)
```

!!! note
    `.get()` expects to find only one instance. This can raise `NoMatch` or `MultipleMatches`.

### .update()

`.update()` method is defined on model instances.
You need to query to get a `Note` instance first:

```python
note = await Note.objects.first()
```

Then update the field(s):

```python
await note.update(completed=True)
```

## Convenience Methods

### .get_or_create()

To get an existing instance matching the query, or create a new one.
This will retuurn a tuple of `instance` and `created`.

```python
note, created = await Note.objects.get_or_create(text="Going to car wash")
```

!!! note
    Since `get_or_create()` is doing a [get()](#get), it can raise `MultipleMatches` exception.
