import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///test.db")
