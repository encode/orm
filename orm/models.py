import typing

import databases
import sqlalchemy
import typesystem
from sqlalchemy.ext.asyncio import create_async_engine

from orm.exceptions import MultipleMatches, NoMatch
from orm.fields import String, Text

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
        self.metadata = sqlalchemy.MetaData()

    async def create_all(self):
        url = self._get_database_url()
        engine = create_async_engine(url)

        for model_cls in self.models.values():
            model_cls.build_table()

        async with self.database:
            async with engine.begin() as conn:
                await conn.run_sync(self.metadata.create_all)

        await engine.dispose()

    async def drop_all(self):
        url = self._get_database_url()
        engine = create_async_engine(url)

        for model_cls in self.models.values():
            model_cls.build_table()

        async with self.database:
            async with engine.begin() as conn:
                await conn.run_sync(self.metadata.drop_all)

        await engine.dispose()

    def _get_database_url(self) -> str:
        url = self.database.url
        if not url.driver:
            if url.dialect == "postgresql":
                url = url.replace(driver="asyncpg")
            elif url.dialect == "mysql":
                url = url.replace(driver="aiomysql")
            elif url.dialect == "sqlite":
                url = url.replace(driver="aiosqlite")
        return str(url)


class ModelMeta(type):
    def __new__(cls, name, bases, attrs):
        model_class = super().__new__(cls, name, bases, attrs)

        if "registry" in attrs:
            model_class.database = attrs["registry"].database
            attrs["registry"].models[name] = model_class

            if "tablename" not in attrs:
                setattr(model_class, "tablename", name.lower())

        for name, field in attrs.get("fields", {}).items():
            setattr(field, "registry", attrs.get("registry"))
            if field.primary_key:
                model_class.pkname = name

        return model_class

    @property
    def table(cls):
        if not hasattr(cls, "_table"):
            cls._table = cls.build_table()
        return cls._table

    @property
    def columns(cls) -> sqlalchemy.sql.ColumnCollection:
        return cls._table.columns


class QuerySet:
    ESCAPE_CHARACTERS = ["%", "_"]

    def __init__(
        self,
        model_cls=None,
        filter_clauses=None,
        select_related=None,
        limit_count=None,
        offset=None,
        order_by=None,
    ):
        self.model_cls = model_cls
        self.filter_clauses = [] if filter_clauses is None else filter_clauses
        self._select_related = [] if select_related is None else select_related
        self.limit_count = limit_count
        self.query_offset = offset
        self._order_by = [] if order_by is None else order_by

    def __get__(self, instance, owner):
        return self.__class__(model_cls=owner)

    @property
    def database(self):
        return self.model_cls.registry.database

    @property
    def table(self) -> sqlalchemy.Table:
        return self.model_cls.table

    @property
    def schema(self):
        fields = {key: field.validator for key, field in self.model_cls.fields.items()}
        return typesystem.Schema(fields=fields)

    @property
    def pkname(self):
        return self.model_cls.pkname

    def _build_select_expression(self):
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

        if self._order_by:
            order_by = list(map(self._prepare_order_by, self._order_by))
            expr = expr.order_by(*order_by)

        if self.limit_count:
            expr = expr.limit(self.limit_count)

        if self.query_offset:
            expr = expr.offset(self.query_offset)

        return expr

    def filter(
        self,
        clause: typing.Optional[sqlalchemy.sql.expression.BinaryExpression] = None,
        **kwargs: typing.Any,
    ):
        if clause is not None:
            self.filter_clauses.append(clause)
            return self
        else:
            return self._filter_query(**kwargs)

    def exclude(
        self,
        clause: typing.Optional[sqlalchemy.sql.expression.BinaryExpression] = None,
        **kwargs: typing.Any,
    ):
        if clause is not None:
            self.filter_clauses.append(clause)
            return self
        else:
            return self._filter_query(_exclude=True, **kwargs)

    def _filter_query(self, _exclude: bool = False, **kwargs):
        clauses = []
        filter_clauses = self.filter_clauses
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
                has_escaped_character = any(
                    c for c in self.ESCAPE_CHARACTERS if c in value
                )
                if has_escaped_character:
                    # enable escape modifier
                    for char in self.ESCAPE_CHARACTERS:
                        value = value.replace(char, f"\\{char}")
                value = f"%{value}%"

            if isinstance(value, Model):
                value = value.pk

            clause = getattr(column, op_attr)(value)
            clause.modifiers["escape"] = "\\" if has_escaped_character else None

            clauses.append(clause)

        if _exclude:
            filter_clauses.append(sqlalchemy.not_(sqlalchemy.sql.and_(*clauses)))
        else:
            filter_clauses += clauses

        return self.__class__(
            model_cls=self.model_cls,
            filter_clauses=filter_clauses,
            select_related=select_related,
            limit_count=self.limit_count,
            offset=self.query_offset,
            order_by=self._order_by,
        )

    def search(self, term: typing.Any):
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

        search_fields = [
            name
            for name, field in self.model_cls.fields.items()
            if isinstance(field, (String, Text))
        ]
        search_clauses = [
            self.table.columns[name].ilike(value) for name in search_fields
        ]

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

    def order_by(self, *order_by):
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
        expr = self._build_select_expression()
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
        expr = self._build_select_expression().alias("subquery_for_count")
        expr = sqlalchemy.func.count().select().select_from(expr)
        return await self.database.fetch_val(expr)

    async def all(self, **kwargs):
        if kwargs:
            return await self.filter(**kwargs).all()

        expr = self._build_select_expression()
        rows = await self.database.fetch_all(expr)
        return [
            self.model_cls._from_row(row, select_related=self._select_related)
            for row in rows
        ]

    async def get(self, **kwargs):
        if kwargs:
            return await self.filter(**kwargs).get()

        expr = self._build_select_expression().limit(2)
        rows = await self.database.fetch_all(expr)

        if not rows:
            raise NoMatch()
        if len(rows) > 1:
            raise MultipleMatches()
        return self.model_cls._from_row(rows[0], select_related=self._select_related)

    async def first(self, **kwargs):
        if kwargs:
            return await self.filter(**kwargs).first()

        rows = await self.limit(1).all()
        if rows:
            return rows[0]

    async def create(self, **kwargs):
        fields = self.model_cls.fields
        validator = typesystem.Schema(
            fields={key: value.validator for key, value in fields.items()}
        )
        kwargs = validator.validate(kwargs)

        for key, value in fields.items():
            if value.validator.read_only and value.validator.has_default():
                kwargs[key] = value.validator.get_default_value()

        instance = self.model_cls(**kwargs)
        expr = self.table.insert().values(**kwargs)

        if self.pkname not in kwargs:
            instance.pk = await self.database.execute(expr)
        else:
            await self.database.execute(expr)

        return instance

    async def delete(self) -> None:
        expr = self.table.delete()
        for filter_clause in self.filter_clauses:
            expr = expr.where(filter_clause)

        await self.database.execute(expr)

    async def update(self, **kwargs) -> None:
        fields = {
            key: field.validator
            for key, field in self.model_cls.fields.items()
            if key in kwargs
        }
        validator = typesystem.Schema(fields=fields)
        kwargs = validator.validate(kwargs)

        expr = self.table.update().values(**kwargs)

        for filter_clause in self.filter_clauses:
            expr = expr.where(filter_clause)

        await self.database.execute(expr)

    async def get_or_create(
        self, defaults: typing.Dict[str, typing.Any], **kwargs
    ) -> typing.Tuple[typing.Any, bool]:
        try:
            instance = await self.get(**kwargs)
            return instance, False
        except NoMatch:
            kwargs.update(defaults)
            instance = await self.create(**kwargs)
            return instance, True

    async def update_or_create(
        self, defaults: typing.Dict[str, typing.Any], **kwargs
    ) -> typing.Tuple[typing.Any, bool]:
        try:
            instance = await self.get(**kwargs)
            await instance.update(**defaults)
            return instance, False
        except NoMatch:
            kwargs.update(defaults)
            instance = await self.create(**kwargs)
            return instance, True

    def _prepare_order_by(self, order_by: str):
        reverse = order_by.startswith("-")
        order_by = order_by.lstrip("-")
        order_col = self.table.columns[order_by]
        return order_col.desc() if reverse else order_col


class Model(metaclass=ModelMeta):
    objects = QuerySet()

    def __init__(self, **kwargs):
        if "pk" in kwargs:
            kwargs[self.pkname] = kwargs.pop("pk")
        for key, value in kwargs.items():
            if key not in self.fields:
                raise ValueError(
                    f"Invalid keyword {key} for class {self.__class__.__name__}"
                )
            setattr(self, key, value)

    @property
    def pk(self):
        return getattr(self, self.pkname)

    @pk.setter
    def pk(self, value):
        setattr(self, self.pkname, value)

    def __repr__(self):
        return f"<{self.__class__.__name__}: {self}>"

    def __str__(self):
        return f"{self.__class__.__name__}({self.pkname}={self.pk})"

    @classmethod
    def build_table(cls):
        tablename = cls.tablename
        metadata = cls.registry.metadata
        columns = []
        for name, field in cls.fields.items():
            columns.append(field.get_column(name))
        return sqlalchemy.Table(tablename, metadata, *columns, extend_existing=True)

    @property
    def table(self) -> sqlalchemy.Table:
        return self.__class__.table

    async def update(self, **kwargs):
        fields = {
            key: field.validator for key, field in self.fields.items() if key in kwargs
        }
        validator = typesystem.Schema(fields=fields)
        kwargs = validator.validate(kwargs)

        pk_column = getattr(self.table.c, self.pkname)
        expr = self.table.update().values(**kwargs).where(pk_column == self.pk)

        await self.database.execute(expr)

        # Update the model instance.
        for key, value in kwargs.items():
            setattr(self, key, value)

    async def delete(self) -> None:
        pk_column = getattr(self.table.c, self.pkname)
        expr = self.table.delete().where(pk_column == self.pk)

        await self.database.execute(expr)

    async def load(self):
        # Build the select expression.
        pk_column = getattr(self.table.c, self.pkname)
        expr = self.table.select().where(pk_column == self.pk)

        # Perform the fetch.
        row = await self.database.fetch_one(expr)

        # Update the instance.
        for key, value in dict(row._mapping).items():
            setattr(self, key, value)

    @classmethod
    def _from_row(cls, row, select_related=[]):
        """
        Instantiate a model instance, given a database row.
        """
        item = {}

        # Instantiate any child instances first.
        for related in select_related:
            if "__" in related:
                first_part, remainder = related.split("__", 1)
                model_cls = cls.fields[first_part].target
                item[first_part] = model_cls._from_row(row, select_related=[remainder])
            else:
                model_cls = cls.fields[related].target
                item[related] = model_cls._from_row(row)

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
