# Tests for core/database/migrate.py
#
# Covers:
# - Migration file discovery (unit)
# - Version tracking and migration running (mocked DB)

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from core.database.migrate import MigrationManager


# Migration file discovery


class TestMigrationFiles:
    def test_finds_surql_files(self, tmp_path):
        (tmp_path / "001_init.surql").write_text("CREATE TABLE user;")
        (tmp_path / "002_add_notes.surql").write_text("CREATE TABLE note;")
        (tmp_path / "002_add_notes_down.surql").write_text("DROP TABLE note;")
        (tmp_path / "readme.txt").write_text("ignore me")

        mgr = MigrationManager(migrations_dir=str(tmp_path))
        files = mgr._get_migration_files()

        assert len(files) == 2
        assert all(f.suffix == ".surql" for f in files)
        assert all("_down" not in f.name for f in files)

    def test_returns_sorted_order(self, tmp_path):
        (tmp_path / "002_second.surql").write_text("")
        (tmp_path / "001_first.surql").write_text("")

        mgr = MigrationManager(migrations_dir=str(tmp_path))
        files = mgr._get_migration_files()
        assert files[0].name == "001_first.surql"
        assert files[1].name == "002_second.surql"

    def test_returns_empty_for_missing_dir(self):
        mgr = MigrationManager(migrations_dir="/nonexistent/path")
        assert mgr._get_migration_files() == []


# get_current_version


class TestGetCurrentVersion:
    @pytest.mark.asyncio
    async def test_returns_version_from_db(self):
        with patch("core.database.migrate.repo_query", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = [{"version": 3}]
            mgr = MigrationManager()
            version = await mgr.get_current_version()

        assert version == 3

    @pytest.mark.asyncio
    async def test_returns_zero_when_no_migrations(self):
        with patch("core.database.migrate.repo_query", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = [{"version": None}]
            mgr = MigrationManager()
            version = await mgr.get_current_version()

        assert version == 0

    @pytest.mark.asyncio
    async def test_returns_zero_on_error(self):
        with patch("core.database.migrate.repo_query", new_callable=AsyncMock) as mock_q:
            mock_q.side_effect = Exception("table not found")
            mgr = MigrationManager()
            version = await mgr.get_current_version()

        assert version == 0


# needs_migration


class TestNeedsMigration:
    @pytest.mark.asyncio
    async def test_true_when_behind(self, tmp_path):
        (tmp_path / "001_init.surql").write_text("")
        (tmp_path / "002_more.surql").write_text("")

        with patch("core.database.migrate.repo_query", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = [{"version": 1}]
            mgr = MigrationManager(migrations_dir=str(tmp_path))
            assert await mgr.needs_migration() is True

    @pytest.mark.asyncio
    async def test_false_when_up_to_date(self, tmp_path):
        (tmp_path / "001_init.surql").write_text("")

        with patch("core.database.migrate.repo_query", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = [{"version": 1}]
            mgr = MigrationManager(migrations_dir=str(tmp_path))
            assert await mgr.needs_migration() is False


# run_migrations


class TestRunMigrations:
    @pytest.mark.asyncio
    async def test_runs_pending_migrations(self, tmp_path):
        (tmp_path / "001_init.surql").write_text("CREATE TABLE user;")
        (tmp_path / "002_notes.surql").write_text("CREATE TABLE note;")

        mock_conn = AsyncMock()

        with (
            patch("core.database.migrate.repo_query", new_callable=AsyncMock) as mock_q,
            patch("core.database.migrate.db_connection") as mock_ctx,
        ):
            mock_q.return_value = [{"version": 1}]
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            mgr = MigrationManager(migrations_dir=str(tmp_path))
            await mgr.run_migrations()

        # Only migration 002 should have run (001 already applied)
        mock_conn.query.assert_called_once_with("CREATE TABLE note;")

    @pytest.mark.asyncio
    async def test_skips_when_up_to_date(self, tmp_path):
        (tmp_path / "001_init.surql").write_text("CREATE TABLE user;")

        mock_conn = AsyncMock()

        with (
            patch("core.database.migrate.repo_query", new_callable=AsyncMock) as mock_q,
            patch("core.database.migrate.db_connection") as mock_ctx,
        ):
            mock_q.return_value = [{"version": 1}]
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            mgr = MigrationManager(migrations_dir=str(tmp_path))
            await mgr.run_migrations()

        mock_conn.query.assert_not_called()
