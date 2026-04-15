# Tests for core/domain/notebook.py
#
# Covers:
# - Notebook, Source, Note, ChatSession, ChatMessage models
# - Validators (unit tests)
# - Context helpers (unit tests)
# - DB operations with mocked repo functions (integration tests)

from unittest.mock import AsyncMock, patch

import pytest

from core.domain.notebook import (
    Asset,
    ChatMessage,
    ChatSession,
    Note,
    Notebook,
    Source,
)
from core.exceptions import InvalidInputError


# Notebook validators


class TestNotebookValidators:
    def test_valid_notebook(self):
        nb = Notebook(name="My Notebook")
        assert nb.name == "My Notebook"

    def test_empty_name_raises(self):
        with pytest.raises(InvalidInputError):
            Notebook(name="   ")

    def test_default_values(self):
        nb = Notebook(name="test")
        assert nb.description == ""
        assert nb.archived is False


# Notebook DB operations


class TestNotebookOperations:
    @pytest.mark.asyncio
    async def test_get_sources(self):
        with patch("core.domain.notebook.repo_query", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = [
                {"source": {"id": "source:1", "title": "Doc A"}},
                {"source": {"id": "source:2", "title": "Doc B"}},
            ]
            nb = Notebook(id="notebook:1", name="test")
            sources = await nb.get_sources()

        assert len(sources) == 2
        assert sources[0].title == "Doc A"

    @pytest.mark.asyncio
    async def test_get_notes(self):
        with patch("core.domain.notebook.repo_query", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = [
                {"note": {"id": "note:1", "title": "Note A"}},
            ]
            nb = Notebook(id="notebook:1", name="test")
            notes = await nb.get_notes()

        assert len(notes) == 1
        assert notes[0].title == "Note A"

    @pytest.mark.asyncio
    async def test_get_sources_empty(self):
        with patch("core.domain.notebook.repo_query", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = []
            nb = Notebook(id="notebook:1", name="test")
            sources = await nb.get_sources()

        assert sources == []

    @pytest.mark.asyncio
    async def test_delete_cleans_up_relations(self):
        with (
            patch("core.domain.notebook.repo_query", new_callable=AsyncMock) as mock_q,
            patch("core.domain.base.repo_delete", new_callable=AsyncMock) as mock_del,
        ):
            # get_notes returns one note, all subsequent queries succeed
            mock_q.side_effect = [
                [{"note": {"id": "note:1", "title": "N"}}],  # get_notes
                None,  # delete note relation (artifact)
                None,  # delete reference relations
                None,  # delete refers_to relations
            ]
            mock_del.return_value = True

            nb = Notebook(id="notebook:1", name="test")
            result = await nb.delete()

        assert result["deleted_notes"] == 1
        # repo_delete should be called for the note + the notebook itself
        assert mock_del.call_count == 2

    @pytest.mark.asyncio
    async def test_delete_raises_without_id(self):
        nb = Notebook(name="test")
        with pytest.raises(InvalidInputError):
            await nb.delete()

    @pytest.mark.asyncio
    async def test_get_source_count(self):
        with patch("core.domain.notebook.repo_query", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = [{"total": 3}]
            nb = Notebook(id="notebook:1", name="test")
            count = await nb.get_source_count()

        assert count == 3

    @pytest.mark.asyncio
    async def test_get_note_count(self):
        with patch("core.domain.notebook.repo_query", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = [{"total": 7}]
            nb = Notebook(id="notebook:1", name="test")
            count = await nb.get_note_count()

        assert count == 7


# Asset


class TestAsset:
    def test_create_with_file_path(self):
        a = Asset(file_path="/tmp/doc.pdf")
        assert a.file_path == "/tmp/doc.pdf"
        assert a.url is None

    def test_create_with_url(self):
        a = Asset(url="https://example.com/doc.pdf")
        assert a.url == "https://example.com/doc.pdf"


# Source


class TestSource:
    def test_default_status_is_pending(self):
        s = Source()
        assert s.status == "pending"

    @pytest.mark.asyncio
    async def test_get_context_short(self):
        s = Source(id="source:1", title="My Doc", full_text="long text here")
        ctx = await s.get_context("short")
        assert ctx == {"id": "source:1", "title": "My Doc"}
        assert "full_text" not in ctx

    @pytest.mark.asyncio
    async def test_get_context_long(self):
        s = Source(id="source:1", title="My Doc", full_text="long text here")
        ctx = await s.get_context("long")
        assert ctx["full_text"] == "long text here"

    @pytest.mark.asyncio
    async def test_add_to_notebook(self):
        with patch("core.domain.base.repo_relate", new_callable=AsyncMock) as mock_rel:
            mock_rel.return_value = [{"id": "ref:1"}]
            s = Source(id="source:1", title="Doc")
            await s.add_to_notebook("notebook:1")

        mock_rel.assert_called_once_with(
            source="source:1", relationship="reference", target="notebook:1", data={}
        )

    @pytest.mark.asyncio
    async def test_add_to_notebook_raises_without_notebook_id(self):
        s = Source(id="source:1", title="Doc")
        with pytest.raises(InvalidInputError):
            await s.add_to_notebook("")

    @pytest.mark.asyncio
    async def test_delete_cleans_up(self):
        with (
            patch("core.domain.notebook.repo_query", new_callable=AsyncMock) as mock_q,
            patch("core.domain.base.repo_delete", new_callable=AsyncMock) as mock_del,
        ):
            mock_q.return_value = None
            mock_del.return_value = True
            s = Source(id="source:1", title="Doc")
            await s.delete()

        # Should have called repo_query for cleanup and repo_delete for the record
        assert mock_q.call_count == 2  # embedding cleanup + reference cleanup
        mock_del.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_embedded_chunks(self):
        with patch("core.domain.notebook.repo_query", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = [{"chunks": 42}]
            s = Source(id="source:1", title="Doc")
            count = await s.get_embedded_chunks()

        assert count == 42


# Note


class TestNote:
    def test_get_context_short_truncates(self):
        content = "x" * 200
        n = Note(id="note:1", title="My Note", content=content)
        ctx = n.get_context("short")
        assert len(ctx["content"]) == 100

    def test_get_context_long(self):
        n = Note(id="note:1", title="My Note", content="full content")
        ctx = n.get_context("long")
        assert ctx["content"] == "full content"

    def test_get_context_short_with_none_content(self):
        n = Note(id="note:1", title="My Note", content=None)
        ctx = n.get_context("short")
        assert ctx["content"] is None

    @pytest.mark.asyncio
    async def test_add_to_notebook(self):
        with patch("core.domain.base.repo_relate", new_callable=AsyncMock) as mock_rel:
            mock_rel.return_value = [{"id": "art:1"}]
            n = Note(id="note:1", title="Note")
            await n.add_to_notebook("notebook:1")

        mock_rel.assert_called_once_with(
            source="note:1", relationship="artifact", target="notebook:1", data={}
        )


# ChatSession


class TestChatSession:
    @pytest.mark.asyncio
    async def test_get_messages(self):
        with patch("core.domain.notebook.repo_query", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = [
                {"id": "msg:1", "session_id": "chat:1", "role": "human", "content": "Hello"},
                {"id": "msg:2", "session_id": "chat:1", "role": "ai", "content": "Hi there"},
            ]
            session = ChatSession(id="chat:1", title="Test Chat")
            messages = await session.get_messages()

        assert len(messages) == 2
        assert messages[0].role == "human"
        assert messages[1].role == "ai"

    @pytest.mark.asyncio
    async def test_relate_to_notebook(self):
        with patch("core.domain.base.repo_relate", new_callable=AsyncMock) as mock_rel:
            mock_rel.return_value = [{"id": "rel:1"}]
            session = ChatSession(id="chat:1", title="Test")
            await session.relate_to_notebook("notebook:1")

        mock_rel.assert_called_once()

    @pytest.mark.asyncio
    async def test_relate_to_notebook_raises_without_id(self):
        session = ChatSession(id="chat:1", title="Test")
        with pytest.raises(InvalidInputError):
            await session.relate_to_notebook("")

    @pytest.mark.asyncio
    async def test_get_by_source(self):
        with patch("core.domain.notebook.repo_query", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = [
                {"id": "chat:1", "title": "S Chat", "source_id": "source:1"}
            ]
            sessions = await ChatSession.get_by_source("source:1", "user:1")

        assert len(sessions) == 1

    @pytest.mark.asyncio
    async def test_get_by_notebook(self):
        with patch("core.domain.notebook.repo_query", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = [
                {"id": "chat:1", "title": "NB Chat", "notebook_id": "notebook:1"}
            ]
            sessions = await ChatSession.get_by_notebook("notebook:1", "user:1")

        assert len(sessions) == 1

    @pytest.mark.asyncio
    async def test_delete_with_messages(self):
        with (
            patch("core.domain.notebook.repo_query", new_callable=AsyncMock) as mock_q,
            patch("core.domain.base.repo_delete", new_callable=AsyncMock) as mock_del,
        ):
            mock_q.return_value = [
                {"id": "msg:1", "session_id": "chat:1", "role": "human", "content": "Hi"},
            ]
            mock_del.return_value = True
            session = ChatSession(id="chat:1", title="Test")
            count = await session.delete_with_messages()

        assert count == 1
        # One delete for the message, one for the session
        assert mock_del.call_count == 2

    @pytest.mark.asyncio
    async def test_delete_with_messages_raises_without_id(self):
        session = ChatSession(title="Test")
        with pytest.raises(InvalidInputError):
            await session.delete_with_messages()


# ChatMessage


class TestChatMessage:
    def test_create_human_message(self):
        msg = ChatMessage(session_id="chat:1", role="human", content="Hello")
        assert msg.role == "human"
        assert msg.content == "Hello"

    def test_create_ai_message(self):
        msg = ChatMessage(session_id="chat:1", role="ai", content="Hi!")
        assert msg.role == "ai"

    def test_default_values(self):
        msg = ChatMessage()
        assert msg.session_id == ""
        assert msg.role == "human"
        assert msg.content == ""
        assert msg.references_data is None
