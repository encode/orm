import os

assert "TEST_DATABASE_URL" in os.environ, "TEST_DATABASE_URL is not set."

DATABASE_URL = os.environ["TEST_DATABASE_URL"]
