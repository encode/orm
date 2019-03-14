from sqlalchemy.sql import and_


class NoMatch(Exception):
    pass


class MultipleMatches(Exception):
    pass


class Query:
    def __init__(self, database, table, cls):
        self.database = database
        self.table = table
        self.cls = cls
        self.query = self.table.select()

    def filter(self, **kwargs) -> "Query":
        if not kwargs:
            return self

        clauses = []
        for key, value in kwargs.items():
            clause = self.table.columns[key] == value
            clauses.append(clause)

        clause = and_(*clauses)

        self.query = self.query.where(clause)
        return self

    async def all(self):
        rows = await self.database.fetch_all(self.query)
        return [self.cls(**dict(row)) for row in rows]

    async def get(self):
        result = None
        seen_result = False

        async for row in self.database.iterate(self.query):
            if seen_result:
                raise MultipleMatches()
            result = row
            seen_result = True

        if not seen_result:
            raise NoMatch()

        return result


class Model:
    @classmethod
    def query(cls, **kwargs):
        return Query(cls.database, cls.table, cls).filter(**kwargs)

    @classmethod
    async def create(cls, **kwargs):
        query = cls.table.insert().values(**kwargs)
        kwargs[list(cls.table.primary_key)[0].name] = await cls.database.execute(query)
        return cls(**kwargs)

    async def update(self, **kwargs):
        query = self.table.update().values(**kwargs).where(self.table.c.id == self.id)
        await self.database.execute(query)
