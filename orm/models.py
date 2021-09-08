import typing

import sqlalchemy
import typesystem
from typesystem.schemas import SchemaMetaclass

from orm.exceptions import MultipleMatches, NoMatch

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


class ModelMetaclass(SchemaMetaclass):
    def __new__(
        cls: type, name: str, bases: typing.Sequence[type], attrs: dict
    ) -> type:
        new_model = super(ModelMetaclass, cls).__new__(  # type: ignore
            cls, name, bases, attrs
        )

        if attrs.get("__abstract__"):
            return new_model

        tablename = attrs["__tablename__"]
        metadata = attrs["__metadata__"]
        pkname = None

        columns = []
        for name, field in new_model.fields.items():
            if field.primary_key:
                pkname = name
            columns.append(field.get_column(name))

        new_model.__table__ = sqlalchemy.Table(tablename, metadata, *columns)
        new_model.__pkname__ = pkname

        return new_model


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
        return self.model_cls.__database__

    @property
    def table(self):
        return self.model_cls.__table__

    def build_select_expression(self):
        tables = [self.table]
        select_from = self.table

        for item in self._select_related:
            model_cls = self.model_cls
            select_from = self.table
            for part in item.split("__"):
                model_cls = model_cls.fields[part].to
                select_from = sqlalchemy.sql.join(select_from, model_cls.__table__)
                tables.append(model_cls.__table__)

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

    def filter(self, **kwargs):
        return self._filter_query(**kwargs)

    def exclude(self, **kwargs):
        return self._filter_query(_exclude=True, **kwargs)

    def _filter_query(self, _exclude: bool = False, **kwargs):
        clauses = []
        filter_clauses = self.filter_clauses
        select_related = list(self._select_related)

        if kwargs.get("pk"):
            pk_name = self.model_cls.__pkname__
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
                        model_cls = model_cls.fields[part].to

                column = model_cls.__table__.columns[field_name]

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

    def order_by(self, *order_by):
        return self.__class__(
            model_cls=self.model_cls,
            filter_clauses=self.filter_clauses,
            select_related=self._select_related,
            limit_count=self.limit_count,
            offset=self.query_offset,
            order_by=order_by,
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
        required = [key for key, value in fields.items() if not value.has_default()]
        validator = typesystem.Object(
            properties=fields, required=required, additional_properties=False
        )
        kwargs = validator.validate(kwargs)

        # Remove primary key when None to prevent not null constraint in postgresql.
        pkname = self.model_cls.__pkname__
        pk = self.model_cls.fields[pkname]
        if kwargs[pkname] is None and pk.allow_null:
            del kwargs[pkname]

        # Build the insert expression.
        expr = self.table.insert()
        expr = expr.values(**kwargs)

        # Execute the insert, and return a new model instance.
        instance = self.model_cls(kwargs)
        instance.pk = await self.database.execute(expr)
        return instance

    async def get_or_create(self, **kwargs) -> typing.Tuple[typing.Any, bool]:
        try:
            instance = await self.get(**kwargs)
            return instance, False
        except NoMatch:
            instance = await self.create(**kwargs)
            return instance, True

    def _prepare_order_by(self, order_by: str):
        reverse = order_by.startswith("-")
        order_by = order_by.lstrip("-")
        order_col = self.table.columns[order_by]
        return order_col.desc() if reverse else order_col


class Model(typesystem.Schema, metaclass=ModelMetaclass):
    __abstract__ = True

    objects = QuerySet()

    def __init__(self, *args, **kwargs):
        if "pk" in kwargs:
            kwargs[self.__pkname__] = kwargs.pop("pk")
        super().__init__(*args, **kwargs)

    @property
    def pk(self):
        return getattr(self, self.__pkname__)

    @pk.setter
    def pk(self, value):
        setattr(self, self.__pkname__, value)

    async def update(self, **kwargs):
        # Validate the keyword arguments.
        fields = {key: field for key, field in self.fields.items() if key in kwargs}
        validator = typesystem.Object(properties=fields)
        kwargs = validator.validate(kwargs)

        # Build the update expression.
        pk_column = getattr(self.__table__.c, self.__pkname__)
        expr = self.__table__.update()
        expr = expr.values(**kwargs).where(pk_column == self.pk)

        # Perform the update.
        await self.__database__.execute(expr)

        # Update the model instance.
        for key, value in kwargs.items():
            setattr(self, key, value)

    async def delete(self):
        # Build the delete expression.
        pk_column = getattr(self.__table__.c, self.__pkname__)
        expr = self.__table__.delete().where(pk_column == self.pk)

        # Perform the delete.
        await self.__database__.execute(expr)

    async def load(self):
        # Build the select expression.
        pk_column = getattr(self.__table__.c, self.__pkname__)
        expr = self.__table__.select().where(pk_column == self.pk)

        # Perform the fetch.
        row = await self.__database__.fetch_one(expr)

        # Update the instance.
        for key, value in dict(row._mapping).items():
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
                model_cls = cls.fields[first_part].to
                item[first_part] = model_cls.from_row(row, select_related=[remainder])
            else:
                model_cls = cls.fields[related].to
                item[related] = model_cls.from_row(row)

        # Pull out the regular column values.
        for column in cls.__table__.columns:
            if column.name not in item:
                item[column.name] = row[column]

        return cls(item)

    def __setattr__(self, key, value):
        if key in self.fields:
            # Setting a relationship to a raw pk value should set a
            # fully-fledged relationship instance, with just the pk loaded.
            value = self.fields[key].expand_relationship(value)
        super().__setattr__(key, value)
