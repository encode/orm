class Query:
    def __init__(self, database, table, cls):
        self.database = database
        self.table = table
        self.cls = cls

    async def all(self):
        query = self.table.select()
        rows = await self.database.fetch_all(query)
        return [self.cls(**dict(row)) for row in rows]


class Model:
    @classmethod
    def query(cls):
        return Query(cls.database, cls.table, cls)

    @classmethod
    async def create(cls, **kwargs):
        query = cls.table.insert().values(**kwargs)
        await cls.database.execute(query)
        return cls(**kwargs)

    async def update(self, **kwargs):
        query = self.table.update().values(**kwargs).where(self.table.c.id==self.id)
        await self.database.execute(query)
