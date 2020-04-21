import asyncio
import typing
from abc import ABCMeta

import databases
import sqlalchemy
import typesystem

from orm.exceptions import MultipleMatches, NoMatch
from orm.fields import ForeignKey, String, Text


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
    def __init__(self, database: databases.Database) -> None:
        self.database = database
        self.models = {}
        self._metadata = sqlalchemy.MetaData()
        self._loaded = False

    @property
    def metadata(self):
        if not self._loaded:
            for model_cls in self.models.values():
                model_cls.table
            self._loaded = True
        return self._metadata

    def create_all(self):
        asyncio.run(self._create_all())

    def drop_all(self):
        asyncio.run(self._drop_all())

    async def _create_all(self):
        async with self.database as database:
            for model_cls in self.models.values():
                expr = sqlalchemy.schema.CreateTable(model_cls.table)
                await self.database.execute(str(expr))

    async def _drop_all(self):
        async with self.database as database:
            for model_cls in self.models.values():
                expr = sqlalchemy.schema.DropTable(model_cls.table)
                await self.database.execute(str(expr))


class ModelMeta(type):
    def __new__(cls, name, bases, attrs):
        model_class = super().__new__(cls, name, bases, attrs)

        if 'registry' in attrs:
            model_class.database = attrs['registry'].database
            attrs['registry'].models[name] = model_class

            if 'tablename' not in attrs:
                setattr(model_class, 'tablename', name.lower())

        for name, field in attrs.get('fields', {}).items():
            setattr(field, 'registry', attrs.get('registry'))
            if field.primary_key:
                model_class.pkname = name

        return model_class

    @property
    def table(cls):
        if not hasattr(cls, '_table'):
            cls._table = cls.build_table()
        return cls._table


class QuerySet:
    ESCAPE_CHARACTERS = ['%', '_']

    def __init__(self, model_cls=None, filter_clauses=None, select_related=None, limit_count=None, offset=None, order_by=None):
        self.model_cls = model_cls
        self.filter_clauses = [] if filter_clauses is None else filter_clauses
        self._select_related = [] if select_related is None else select_related
        self.limit_count = limit_count
        self.query_offset = offset
        self._order_by = order_by

    def __get__(self, instance, owner):
        return self.__class__(model_cls=owner)

    @property
    def database(self):
        return self.model_cls.registry.database

    @property
    def table(self):
        return self.model_cls.table

    @property
    def schema(self):
        fields = {key: field.validator for key, field in self.model_cls.fields.items()}
        return typesystem.Schema(fields=fields)

    @property
    def pkname(self):
        return self.model_cls.pkname

    def build_select_expression(self):
        tables = [self.table]
        select_from = self.table

        for item in self._select_related:
            model_cls = self.model_cls
            select_from = self.table
            for part in item.split("__"):
                model_cls = model_cls.fields[part].target
                table = model_cls.table
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

        if self._order_by is not None:
            reverse = self._order_by.startswith("-")
            order_by = self._order_by.lstrip("-")
            order_col = self.table.columns[order_by]
            if reverse:
                order_col = order_col.desc()
            expr = expr.order_by(order_col)

        if self.limit_count:
            expr = expr.limit(self.limit_count)

        if self.query_offset:
            expr = expr.offset(self.query_offset)

        return expr

    def filter(self, **kwargs):
        filter_clauses = list(self.filter_clauses)
        select_related = list(self._select_related)

        if kwargs.get("pk"):
            pk_name = self.model_cls.pkname
            kwargs[pk_name] = kwargs.pop("pk")

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
                        model_cls = model_cls.fields[part].target

                column = model_cls.table.columns[field_name]

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
            limit_count=self.limit_count,
            offset=self.query_offset,
            order_by=self._order_by,
        )

    def search(self, term):
        if not term:
            return self

        filter_clauses = list(self.filter_clauses)
        value = f"%{term}%"

        # has_escaped_character = any(c for c in self.ESCAPE_CHARACTERS if c in term)
        # if has_escaped_character:
        #     # enable escape modifier
        #     for char in self.ESCAPE_CHARACTERS:
        #         term = term.replace(char, f'\\{char}')
        #     term = f"%{value}%"
        #
        # clause.modifiers['escape'] = '\\' if has_escaped_character else None

        search_fields = [name for name, field in self.model_cls.fields.items() if isinstance(field, (String, Text))]
        search_clauses = [self.table.columns[name].ilike(value) for name in search_fields]

        if len(search_clauses) > 1:
            filter_clauses.append(sqlalchemy.sql.or_(*search_clauses))
        else:
            filter_clauses.extend(search_clauses)

        return self.__class__(
            model_cls=self.model_cls,
            filter_clauses=filter_clauses,
            select_related=self._select_related,
            limit_count=self.limit_count,
            offset=self.query_offset,
            order_by=self._order_by,
        )

    def order_by(self, order_by):
        return self.__class__(
            model_cls=self.model_cls,
            filter_clauses=self.filter_clauses,
            select_related=self._select_related,
            limit_count=self.limit_count,
            offset=self.query_offset,
            order_by=order_by,
        )

    def select_related(self, related):
        if not isinstance(related, (list, tuple)):
            related = [related]

        related = list(self._select_related) + related
        return self.__class__(
            model_cls=self.model_cls,
            filter_clauses=self.filter_clauses,
            select_related=related,
            limit_count=self.limit_count,
            offset=self.query_offset,
            order_by=self._order_by,
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
            limit_count=limit_count,
            offset=self.query_offset,
            order_by=self._order_by,
        )

    def offset(self, offset: int):
        return self.__class__(
            model_cls=self.model_cls,
            filter_clauses=self.filter_clauses,
            select_related=self._select_related,
            limit_count=self.limit_count,
            offset=offset,
            order_by=self._order_by,
        )

    async def count(self) -> int:
        expr = self.build_select_expression().alias("subquery_for_count")
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

    async def first(self, **kwargs):
        if kwargs:
            return await self.filter(**kwargs).first()

        rows = await self.limit(1).all()
        if rows:
            return rows[0]

    async def create(self, **kwargs):
        # Validate the keyword arguments.
        fields = self.model_cls.fields
        validator = typesystem.Schema(
            fields={key: value.validator for key, value in fields.items()}
        )
        kwargs = validator.validate(kwargs)

        for key, value in fields.items():
            if value.validator.read_only and value.validator.has_default():
                kwargs[key] = value.validator.get_default_value()

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

    @classmethod
    def build_table(cls):
        tablename = cls.tablename
        metadata = cls.registry._metadata
        columns = []
        for name, field in cls.fields.items():
            columns.append(field.get_column(name))
        return sqlalchemy.Table(tablename, metadata, *columns)

    @property
    def table(self):
        return self.__class__.table

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
        item = {}

        # Instantiate any child instances first.
        for related in select_related:
            if "__" in related:
                first_part, remainder = related.split("__", 1)
                model_cls = cls.fields[first_part].target
                item[first_part] = model_cls.from_row(row, select_related=[remainder])
            else:
                model_cls = cls.fields[related].target
                item[related] = model_cls.from_row(row)

        # Pull out the regular column values.
        for column in cls.table.columns:
            if column.name not in item:
                item[column.name] = row[column]

        return cls(**item)

    def __setattr__(self, key, value):
        if key in self.fields:
            # Setting a relationship to a raw pk value should set a
            # fully-fledged relationship instance, with just the pk loaded.
            value = self.fields[key].expand_relationship(value)
        super().__setattr__(key, value)

    def __eq__(self, other):
        if self.__class__ != other.__class__:
            return False
        for key in self.fields.keys():
            if getattr(self, key, None) != getattr(other, key, None):
                return False
        return True
