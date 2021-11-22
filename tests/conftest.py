import pytest


@pytest.fixture(scope="module")
def anyio_backend():
    return ("asyncio", {"debug": True})
