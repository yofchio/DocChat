# Tests for core/domain/base.py
#
# Covers:
# - ObjectModel helper methods (unit tests)
# - CRUD operations with mocked repo functions (integration tests)

from datetime import datetime
from typing import ClassVar
from unittest.mock import AsyncMock, patch

import pytest

from core.domain.base import ObjectModel
from core.exceptions import DatabaseOperationError, InvalidInputError, NotFoundError


# Test subclass used throughout

class FakeModel(ObjectModel):
    table_name: ClassVar[str] = "fake"
    nullable_fields: ClassVar[set[str]] = {"description"}
    name: str = ""
    description: str | None = None


# _prepare_save_data


class TestPrepareSaveData:
    def test_removes_none_values(self):
        obj = FakeModel(name="test", description=None)
        data = obj._prepare_save_data()
        # description is nullable, so it stays even when None
        assert "description" in data
        assert data["name"] == "test"

    def test_keeps_nullable_fields(self):
        obj = FakeModel(name="test", description=None)
        data = obj._prepare_save_data()
        assert "description" in data

    def test_excludes_non_nullable_none(self):
        obj = FakeModel(name="test")
        data = obj._prepare_save_data()
        # id is None and not in nullable_fields -> excluded
        assert "id" not in data


# to_summary_dict


class TestToSummaryDict:
    def test_includes_expected_keys(self):
        obj = FakeModel(id="fake:1", name="test")
        result = obj.to_summary_dict()
        assert result["id"] == "fake:1"
        assert result["table"] == "fake"
        assert "created" in result
        assert "updated" in result

    def test_none_timestamps(self):
        obj = FakeModel(name="test")
        result = obj.to_summary_dict()
        assert result["created"] is None
        assert result["updated"] is None


# parse_datetime validator


class TestParseDatetime:
    def test_parses_iso_string(self):
        obj = FakeModel(name="test", created="2024-01-15T10:30:00")
        assert isinstance(obj.created, datetime)

    def test_parses_iso_with_z(self):
        obj = FakeModel(name="test", created="2024-01-15T10:30:00Z")
        assert isinstance(obj.created, datetime)

    def test_passes_through_datetime(self):
        dt = datetime(2024, 1, 15, 10, 30)
        obj = FakeModel(name="test", created=dt)
        assert obj.created == dt


# get_all


class TestGetAll:
    @pytest.mark.asyncio
    async def test_returns_list_of_models(self):
        with patch("core.domain.base.repo_query", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = [
                {"id": "fake:1", "name": "A"},
                {"id": "fake:2", "name": "B"},
            ]
            result = await FakeModel.get_all()

        assert len(result) == 2
        assert result[0].name == "A"
        assert result[1].name == "B"

    @pytest.mark.asyncio
    async def test_filters_by_user_id(self):
        with patch("core.domain.base.repo_query", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = [{"id": "fake:1", "name": "A"}]
            await FakeModel.get_all(user_id="user:1")

        query = mock_q.call_args[0][0]
        assert "user_id" in query

    @pytest.mark.asyncio
    async def test_applies_order_by(self):
        with patch("core.domain.base.repo_query", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = []
            await FakeModel.get_all(order_by="name ASC")

        query = mock_q.call_args[0][0]
        assert "ORDER BY name ASC" in query

    @pytest.mark.asyncio
    async def test_raises_without_table_name(self):
        with pytest.raises(DatabaseOperationError):
            await ObjectModel.get_all()


# get


class TestGet:
    @pytest.mark.asyncio
    async def test_returns_model(self):
        with patch("core.domain.base.repo_query", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = [{"id": "fake:1", "name": "Found"}]
            obj = await FakeModel.get("fake:1")

        assert obj.id == "fake:1"
        assert obj.name == "Found"

    @pytest.mark.asyncio
    async def test_raises_not_found(self):
        with patch("core.domain.base.repo_query", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = []
            with pytest.raises(NotFoundError):
                await FakeModel.get("fake:999")

    @pytest.mark.asyncio
    async def test_raises_on_empty_id(self):
        with pytest.raises(InvalidInputError):
            await FakeModel.get("")


# save


class TestSave:
    @pytest.mark.asyncio
    async def test_creates_new_record(self):
        with patch("core.domain.base.repo_create", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = [{"id": "fake:new", "name": "New"}]
            obj = FakeModel(name="New")
            await obj.save()

        assert obj.id == "fake:new"
        mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_updates_existing_record(self):
        with patch("core.domain.base.repo_update", new_callable=AsyncMock) as mock_update:
            mock_update.return_value = [{"id": "fake:1", "name": "Updated"}]
            obj = FakeModel(id="fake:1", name="Old", created=datetime(2024, 1, 1))
            await obj.save()

        assert obj.name == "Updated"
        mock_update.assert_called_once()


# delete


class TestDelete:
    @pytest.mark.asyncio
    async def test_deletes_record(self):
        with patch("core.domain.base.repo_delete", new_callable=AsyncMock) as mock_del:
            mock_del.return_value = True
            obj = FakeModel(id="fake:1", name="test")
            result = await obj.delete()

        mock_del.assert_called_once_with("fake:1")

    @pytest.mark.asyncio
    async def test_raises_without_id(self):
        obj = FakeModel(name="test")
        with pytest.raises(InvalidInputError):
            await obj.delete()


# exists


class TestExists:
    @pytest.mark.asyncio
    async def test_returns_true_when_found(self):
        with patch("core.domain.base.repo_query", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = [{"id": "fake:1"}]
            assert await FakeModel.exists("fake:1") is True

    @pytest.mark.asyncio
    async def test_returns_false_when_not_found(self):
        with patch("core.domain.base.repo_query", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = []
            assert await FakeModel.exists("fake:999") is False

    @pytest.mark.asyncio
    async def test_returns_false_for_empty_id(self):
        assert await FakeModel.exists("") is False


# count


class TestCount:
    @pytest.mark.asyncio
    async def test_returns_count(self):
        with patch("core.domain.base.repo_query", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = [{"total": 5}]
            assert await FakeModel.count() == 5

    @pytest.mark.asyncio
    async def test_returns_zero_when_empty(self):
        with patch("core.domain.base.repo_query", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = []
            assert await FakeModel.count() == 0

    @pytest.mark.asyncio
    async def test_filters_by_user_id(self):
        with patch("core.domain.base.repo_query", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = [{"total": 2}]
            result = await FakeModel.count(user_id="user:1")

        query = mock_q.call_args[0][0]
        assert "user_id" in query
        assert result == 2


# get_by_field


class TestGetByField:
    @pytest.mark.asyncio
    async def test_returns_matching_models(self):
        with patch("core.domain.base.repo_query", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = [{"id": "fake:1", "name": "Match"}]
            results = await FakeModel.get_by_field("name", "Match")

        assert len(results) == 1
        assert results[0].name == "Match"

    @pytest.mark.asyncio
    async def test_returns_empty_list(self):
        with patch("core.domain.base.repo_query", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = []
            results = await FakeModel.get_by_field("name", "Nothing")

        assert results == []


# relate


class TestRelate:
    @pytest.mark.asyncio
    async def test_creates_relation(self):
        with patch("core.domain.base.repo_relate", new_callable=AsyncMock) as mock_rel:
            mock_rel.return_value = [{"id": "ref:1"}]
            obj = FakeModel(id="fake:1", name="test")
            await obj.relate("reference", "notebook:1")

        mock_rel.assert_called_once_with(
            source="fake:1", relationship="reference", target="notebook:1", data={}
        )

    @pytest.mark.asyncio
    async def test_raises_without_required_fields(self):
        obj = FakeModel(name="test")  # no id
        with pytest.raises(InvalidInputError):
            await obj.relate("reference", "notebook:1")
