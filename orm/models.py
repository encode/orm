import typing
from abc import ABCMeta
from importlib import import_module

import databases
import sqlalchemy
import typesystem

from orm.exceptions import MultipleMatches, NoMatch
from orm.fields import ForeignKey


FILTER_OPERATORS = {
    "exact": "__eq__",
    "iexact": "ilike",
    "contains": "like",
    "icontains": "ilike",
    "in": "in_",
    "gt": "__gt__",
    "gte": "__ge__",
    "lt": "__lt__",
    "lte": "__le__",
}


class ModelRegistry:
    def __init__(self, database: databases.Database, installed: typing.Sequence[str] = None) -> None:
        self.database = database
        self.installed = [] if installed is None else list(installed)

    def load(self):
        metadata = sqlalchemy.MetaData()
        tables = {}
        models = {}

        for import_name in self.installed:
            module_name, class_name = import_name.rsplit('.', 1)
            module = import_module(module_name)
            model = getattr(module, class_name)
            models[model.tablename] = model

        for tablename, model in models.items():
            fields = getattr(model, 'fields')

            columns = []
            for name, field in fields.items():
                columns.append(field.get_column(name, models))

            tables[tablename] = sqlalchemy.Table(tablename, metadata, *columns)

        self._metadata = metadata
        self._tables = tables
        self._models = models

    @property
    def tables(self):
        if not hasattr(self, '_tables'):
            self.load()
        return self._tables

    @property
    def models(self):
        if not hasattr(self, '_models'):
            self.load()
        return self._models

    @property
    def metadata(self):
        if not hasattr(self, '_metadata'):
            self.load()
        return self._metadata


class ModelMeta(type):
    def __new__(cls, name, bases, attrs):
        model_class = super().__new__(cls, name, bases, attrs)
        for name, field in attrs.get('fields', {}).items():
            if field.primary_key:
                model_class.pkname = name
        if 'registry' in attrs:
            model_class.database = attrs['registry'].database
        return model_class


class QuerySet:
    ESCAPE_CHARACTERS = ['%', '_']

    def __init__(self, model_cls=None, filter_clauses=None, select_related=None, limit_count=None):
        self.model_cls = model_cls
        self.filter_clauses = [] if filter_clauses is None else filter_clauses
        self._select_related = [] if select_related is None else select_related
        self.limit_count = limit_count

    def __get__(self, instance, owner):
        return self.__class__(model_cls=owner)

    @property
    def database(self):
        return self.model_cls.registry.database

    @property
    def table(self):
        return self.model_cls.registry.tables[self.model_cls.tablename]

    @property
    def pkname(self):
        return self.model_cls.pkname

    def build_select_expression(self):
        table_map = self.model_cls.registry.tables
        model_map = self.model_cls.registry.models
        tables = [self.table]
        select_from = self.table

        for item in self._select_related:
            model_cls = self.model_cls
            select_from = self.table
            for part in item.split("__"):
                model_cls = model_map[model_cls.fields[part].to]
                table = table_map[model_cls.tablename]
                select_from = sqlalchemy.sql.join(select_from, table)
                tables.append(table)

        expr = sqlalchemy.sql.select(tables)
        expr = expr.select_from(select_from)

        if self.filter_clauses:
            if len(self.filter_clauses) == 1:
                clause = self.filter_clauses[0]
            else:
                clause = sqlalchemy.sql.and_(*self.filter_clauses)
            expr = expr.where(clause)

        if self.limit_count:
            expr = expr.limit(self.limit_count)

        return expr

    def filter(self, **kwargs):
        table_map = self.model_cls.registry.tables
        model_map = self.model_cls.registry.models

        filter_clauses = self.filter_clauses
        select_related = list(self._select_related)

        for key, value in kwargs.items():
            if "__" in key:
                parts = key.split("__")

                # Determine if we should treat the final part as a
                # filter operator or as a related field.
                if parts[-1] in FILTER_OPERATORS:
                    op = parts[-1]
                    field_name = parts[-2]
                    related_parts = parts[:-2]
                else:
                    op = "exact"
                    field_name = parts[-1]
                    related_parts = parts[:-1]

                model_cls = self.model_cls
                if related_parts:
                    # Add any implied select_related
                    related_str = "__".join(related_parts)
                    if related_str not in select_related:
                        select_related.append(related_str)

                    # Walk the relationships to the actual model class
                    # against which the comparison is being made.
                    for part in related_parts:
                        model_cls = model_map[model_cls.fields[part].to]

                column = table_map[model_cls.tablename].columns[field_name]

            else:
                op = "exact"
                column = self.table.columns[key]

            # Map the operation code onto SQLAlchemy's ColumnElement
            # https://docs.sqlalchemy.org/en/latest/core/sqlelement.html#sqlalchemy.sql.expression.ColumnElement
            op_attr = FILTER_OPERATORS[op]
            has_escaped_character = False

            if op in ["contains", "icontains"]:
                has_escaped_character = any(c for c in self.ESCAPE_CHARACTERS
                                            if c in value)
                if has_escaped_character:
                    # enable escape modifier
                    for char in self.ESCAPE_CHARACTERS:
                        value = value.replace(char, f'\\{char}')
                value = f"%{value}%"

            if isinstance(value, Model):
                value = value.pk

            clause = getattr(column, op_attr)(value)
            clause.modifiers['escape'] = '\\' if has_escaped_character else None
            filter_clauses.append(clause)

        return self.__class__(
            model_cls=self.model_cls,
            filter_clauses=filter_clauses,
            select_related=select_related,
            limit_count=self.limit_count
        )

    def select_related(self, related):
        if not isinstance(related, (list, tuple)):
            related = [related]

        related = list(self._select_related) + related
        return self.__class__(
            model_cls=self.model_cls,
            filter_clauses=self.filter_clauses,
            select_related=related,
            limit_count=self.limit_count
        )

    async def exists(self) -> bool:
        expr = self.build_select_expression()
        expr = sqlalchemy.exists(expr).select()
        return await self.database.fetch_val(expr)

    def limit(self, limit_count: int):
        return self.__class__(
            model_cls=self.model_cls,
            filter_clauses=self.filter_clauses,
            select_related=self._select_related,
            limit_count=limit_count
        )

    async def count(self) -> int:
        expr = self.build_select_expression()
        expr = sqlalchemy.func.count().select().select_from(expr)
        return await self.database.fetch_val(expr)

    async def all(self, **kwargs):
        if kwargs:
            return await self.filter(**kwargs).all()

        expr = self.build_select_expression()
        rows = await self.database.fetch_all(expr)
        return [
            self.model_cls.from_row(row, select_related=self._select_related)
            for row in rows
        ]

    async def get(self, **kwargs):
        if kwargs:
            return await self.filter(**kwargs).get()

        expr = self.build_select_expression().limit(2)
        rows = await self.database.fetch_all(expr)

        if not rows:
            raise NoMatch()
        if len(rows) > 1:
            raise MultipleMatches()
        return self.model_cls.from_row(rows[0], select_related=self._select_related)

    async def create(self, **kwargs):
        # Validate the keyword arguments.
        fields = self.model_cls.fields
        validator = typesystem.Schema(
            fields={key: value.validator for key, value in fields.items()}
        )
        kwargs = validator.validate(kwargs)

        # Remove primary key when None to prevent not null constraint in postgresql.
        pkname = self.pkname
        pk = self.model_cls.fields[pkname]
        if kwargs[pkname] is None and pk.allow_null:
            del kwargs[pkname]

        # Build the insert expression.
        expr = self.table.insert()
        expr = expr.values(**kwargs)

        # Execute the insert, and return a new model instance.
        instance = self.model_cls(**kwargs)
        instance.pk = await self.database.execute(expr)
        return instance


class Model(metaclass=ModelMeta):
    objects = QuerySet()

    def __init__(self, **kwargs):
        if "pk" in kwargs:
            kwargs[self.pkname] = kwargs.pop("pk")
        for key, value in kwargs.items():
            if key not in self.fields:
                raise ValueError(f"Invalid keyword {key} for class {self.__class__.__name__}")
            setattr(self, key, value)

    @property
    def pk(self):
        return getattr(self, self.pkname)

    @pk.setter
    def pk(self, value):
        setattr(self, self.pkname, value)

    @property
    def table(self):
        return self.registry.tables[self.tablename]

    async def update(self, **kwargs):
        # Validate the keyword arguments.
        fields = {key: field.validator for key, field in self.fields.items() if key in kwargs}
        validator = typesystem.Schema(fields=fields)
        kwargs = validator.validate(kwargs)

        # Build the update expression.
        pk_column = getattr(self.table.c, self.pkname)
        expr = self.table.update()
        expr = expr.values(**kwargs).where(pk_column == self.pk)

        # Perform the update.
        await self.database.execute(expr)

        # Update the model instance.
        for key, value in kwargs.items():
            setattr(self, key, value)

    async def delete(self):
        # Build the delete expression.
        pk_column = getattr(self.table.c, self.pkname)
        expr = self.table.delete().where(pk_column == self.pk)

        # Perform the delete.
        await self.database.execute(expr)

    async def load(self):
        # Build the select expression.
        pk_column = getattr(self.table.c, self.pkname)
        expr = self.table.select().where(pk_column == self.pk)

        # Perform the fetch.
        row = await self.database.fetch_one(expr)

        # Update the instance.
        for key, value in dict(row).items():
            setattr(self, key, value)

    @classmethod
    def from_row(cls, row, select_related=[]):
        """
        Instantiate a model instance, given a database row.
        """
        table_map = cls.registry.tables
        model_map = cls.registry.models
        item = {}

        # Instantiate any child instances first.
        for related in select_related:
            if "__" in related:
                first_part, remainder = related.split("__", 1)
                model_cls = model_map[cls.fields[first_part].to]
                item[first_part] = model_cls.from_row(row, select_related=[remainder])
            else:
                model_cls = model_map[cls.fields[related].to]
                item[related] = model_cls.from_row(row)

        # Pull out the regular column values.
        for column in table_map[cls.tablename].columns:
            if column.name not in item:
                item[column.name] = row[column]

        return cls(**item)

    def __setattr__(self, key, value):
        if key in self.fields:
            # Setting a relationship to a raw pk value should set a
            # fully-fledged relationship instance, with just the pk loaded.
            value = self.fields[key].expand_relationship(value, self.registry.models)
        super().__setattr__(key, value)

    def __eq__(self, other):
        if self.__class__ != other.__class__:
            return False
        for key in self.fields.keys():
            if getattr(self, key, None) != getattr(other, key, None):
                return False
        return True
