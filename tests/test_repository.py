# Tests for core/database/repository.py
#
# Covers:
# - Pure utility functions (unit tests)
# - Repo CRUD helpers with mocked DB connections (integration tests)

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.database.repository import (
    ensure_record_id,
    get_database_password,
    get_database_url,
    parse_record_ids,
    repo_create,
    repo_delete,
    repo_insert,
    repo_query,
    repo_relate,
    repo_update,
    repo_upsert,
)
from surrealdb import RecordID


# get_database_url


class TestGetDatabaseUrl:
    def test_uses_surreal_url_env(self, monkeypatch):
        monkeypatch.setenv("SURREAL_URL", "ws://custom:9999/rpc")
        assert get_database_url() == "ws://custom:9999/rpc"

    def test_builds_from_address_and_port(self, monkeypatch):
        monkeypatch.delenv("SURREAL_URL", raising=False)
        monkeypatch.setenv("SURREAL_ADDRESS", "myhost")
        monkeypatch.setenv("SURREAL_PORT", "9090")
        assert get_database_url() == "ws://myhost/rpc:9090"

    def test_defaults_to_localhost(self, monkeypatch):
        monkeypatch.delenv("SURREAL_URL", raising=False)
        monkeypatch.delenv("SURREAL_ADDRESS", raising=False)
        monkeypatch.delenv("SURREAL_PORT", raising=False)
        assert get_database_url() == "ws://localhost/rpc:8000"


# get_database_password


class TestGetDatabasePassword:
    def test_prefers_surreal_password(self, monkeypatch):
        monkeypatch.setenv("SURREAL_PASSWORD", "secret1")
        monkeypatch.setenv("SURREAL_PASS", "secret2")
        assert get_database_password() == "secret1"

    def test_falls_back_to_surreal_pass(self, monkeypatch):
        monkeypatch.delenv("SURREAL_PASSWORD", raising=False)
        monkeypatch.setenv("SURREAL_PASS", "fallback")
        assert get_database_password() == "fallback"

    def test_returns_none_when_unset(self, monkeypatch):
        monkeypatch.delenv("SURREAL_PASSWORD", raising=False)
        monkeypatch.delenv("SURREAL_PASS", raising=False)
        assert get_database_password() is None


# parse_record_ids


class TestParseRecordIds:
    def test_converts_record_id_to_string(self):
        rid = RecordID("user", "abc")
        assert parse_record_ids(rid) == str(rid)

    def test_recurses_into_dict(self):
        rid = RecordID("user", "1")
        result = parse_record_ids({"id": rid, "name": "Alice"})
        assert result == {"id": str(rid), "name": "Alice"}

    def test_recurses_into_list(self):
        rid = RecordID("note", "2")
        result = parse_record_ids([rid, "plain"])
        assert result == [str(rid), "plain"]

    def test_nested_structure(self):
        rid = RecordID("source", "x")
        data = {"items": [{"id": rid}]}
        result = parse_record_ids(data)
        assert result == {"items": [{"id": str(rid)}]}

    def test_passes_through_plain_values(self):
        assert parse_record_ids("hello") == "hello"
        assert parse_record_ids(42) == 42
        assert parse_record_ids(None) is None


# ensure_record_id


class TestEnsureRecordId:
    def test_returns_existing_record_id(self):
        rid = RecordID("user", "1")
        assert ensure_record_id(rid) is rid

    def test_parses_string_to_record_id(self):
        result = ensure_record_id("user:abc")
        assert isinstance(result, RecordID)


# repo_query (mocked DB)


class TestRepoQuery:
    @pytest.mark.asyncio
    async def test_returns_parsed_results(self):
        mock_conn = AsyncMock()
        mock_conn.query.return_value = [{"id": "user:1", "name": "Alice"}]

        with patch("core.database.repository.db_connection") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await repo_query("SELECT * FROM user")

        assert result == [{"id": "user:1", "name": "Alice"}]

    @pytest.mark.asyncio
    async def test_raises_on_string_result(self):
        mock_conn = AsyncMock()
        mock_conn.query.return_value = "Some error from SurrealDB"

        with patch("core.database.repository.db_connection") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            with pytest.raises(RuntimeError):
                await repo_query("BAD QUERY")

    @pytest.mark.asyncio
    async def test_retries_once_on_transient_error(self):
        mock_conn = AsyncMock()
        mock_conn.query.side_effect = [ConnectionError("lost"), [{"ok": True}]]

        with patch("core.database.repository.db_connection") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await repo_query("SELECT 1")

        assert result == [{"ok": True}]
        assert mock_conn.query.call_count == 2


# repo_create (mocked DB)


class TestRepoCreate:
    @pytest.mark.asyncio
    async def test_adds_timestamps_and_strips_id(self):
        mock_conn = AsyncMock()
        mock_conn.insert.return_value = [{"id": "note:1", "title": "hi"}]

        with patch("core.database.repository.db_connection") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await repo_create("note", {"id": "should_be_removed", "title": "hi"})

        call_data = mock_conn.insert.call_args[0][1]
        assert "id" not in call_data
        assert isinstance(call_data["created"], datetime)
        assert isinstance(call_data["updated"], datetime)
        assert result == [{"id": "note:1", "title": "hi"}]


# repo_relate (mocked)


class TestRepoRelate:
    @pytest.mark.asyncio
    async def test_builds_correct_query(self):
        with patch("core.database.repository.repo_query", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = [{"id": "reference:1"}]
            result = await repo_relate("source:1", "reference", "notebook:1")

        mock_q.assert_called_once()
        query_str = mock_q.call_args[0][0]
        assert "RELATE source:1->reference->notebook:1" in query_str


# repo_upsert (mocked)


class TestRepoUpsert:
    @pytest.mark.asyncio
    async def test_without_timestamp(self):
        with patch("core.database.repository.repo_query", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = [{"id": "user:1"}]
            await repo_upsert("user", "user:1", {"name": "Bob"}, add_timestamp=False)

        data = mock_q.call_args[0][1]["data"]
        assert "updated" not in data

    @pytest.mark.asyncio
    async def test_with_timestamp(self):
        with patch("core.database.repository.repo_query", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = [{"id": "user:1"}]
            await repo_upsert("user", "user:1", {"name": "Bob"}, add_timestamp=True)

        data = mock_q.call_args[0][1]["data"]
        assert isinstance(data["updated"], datetime)


# repo_update (mocked)


class TestRepoUpdate:
    @pytest.mark.asyncio
    async def test_normalizes_plain_id(self):
        with patch("core.database.repository.repo_query", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = [{"id": "user:abc"}]
            await repo_update("user", "abc", {"name": "Alice"})

        query = mock_q.call_args[0][0]
        assert "user:abc" in query

    @pytest.mark.asyncio
    async def test_keeps_full_record_id(self):
        with patch("core.database.repository.repo_query", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = [{"id": "user:abc"}]
            await repo_update("user", "user:abc", {"name": "Alice"})

        query = mock_q.call_args[0][0]
        assert "user:abc" in query

    @pytest.mark.asyncio
    async def test_converts_created_string_to_datetime(self):
        with patch("core.database.repository.repo_query", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = [{"id": "user:1"}]
            await repo_update("user", "user:1", {"created": "2024-01-01T00:00:00"})

        data = mock_q.call_args[0][1]["data"]
        assert isinstance(data["created"], datetime)


# repo_delete (mocked)


class TestRepoDelete:
    @pytest.mark.asyncio
    async def test_calls_connection_delete(self):
        mock_conn = AsyncMock()
        mock_conn.delete.return_value = None

        with patch("core.database.repository.db_connection") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            await repo_delete("user:1")

        mock_conn.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_wraps_errors(self):
        mock_conn = AsyncMock()
        mock_conn.delete.side_effect = Exception("db down")

        with patch("core.database.repository.db_connection") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            with pytest.raises(RuntimeError, match="Failed to delete"):
                await repo_delete("user:1")


# repo_insert (mocked)


class TestRepoInsert:
    @pytest.mark.asyncio
    async def test_inserts_multiple_records(self):
        mock_conn = AsyncMock()
        mock_conn.insert.return_value = [{"id": "note:1"}, {"id": "note:2"}]

        with patch("core.database.repository.db_connection") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await repo_insert("note", [{"title": "a"}, {"title": "b"}])

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_ignore_duplicates_returns_empty(self):
        mock_conn = AsyncMock()
        mock_conn.insert.side_effect = Exception("already contains")

        with patch("core.database.repository.db_connection") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await repo_insert("note", [{"title": "dup"}], ignore_duplicates=True)

        assert result == []

    @pytest.mark.asyncio
    async def test_raises_on_duplicate_without_flag(self):
        mock_conn = AsyncMock()
        mock_conn.insert.side_effect = RuntimeError("already contains xyz")

        with patch("core.database.repository.db_connection") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            with pytest.raises(RuntimeError):
                await repo_insert("note", [{"title": "dup"}], ignore_duplicates=False)
