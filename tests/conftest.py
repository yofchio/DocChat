import pytest


@pytest.fixture(autouse=True)
def _patch_db(monkeypatch):
    # Block real database connections in every test by default.
    # Individual tests can override specific repo helpers with their own mocks.
    import core.database.repository as repo

    async def _no_connection(*a, **kw):
        raise RuntimeError("Tests must not open real DB connections")

    monkeypatch.setattr(repo._pool, "acquire", _no_connection)
