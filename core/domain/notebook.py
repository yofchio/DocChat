from typing import Any, ClassVar, Dict, List, Literal, Optional

from loguru import logger
from pydantic import Field, field_validator

from core.database.repository import ensure_record_id, repo_query
from core.domain.base import ObjectModel
from core.exceptions import DatabaseOperationError, InvalidInputError


class Notebook(ObjectModel):
    # Notebook model: simple container of notes and sources.
    table_name: ClassVar[str] = "notebook"
    name: str
    description: str = ""
    archived: Optional[bool] = False

    @field_validator("name")
    @classmethod
    def name_must_not_be_empty(cls, v):
        # Ensure notebook has a non-empty name.
        if not v.strip():
            raise InvalidInputError("Notebook name cannot be empty")
        return v

    async def get_sources(self) -> List["Source"]:
        # Return sources related to this notebook, newest first.
        try:
            srcs = await repo_query(
                """
                SELECT * OMIT source.full_text FROM (
                    SELECT in AS source FROM reference WHERE out=$id
                    FETCH source
                ) ORDER BY source.updated DESC
                """,
                {"id": ensure_record_id(self.id)},
            )
            return [Source(**src["source"]) for src in srcs] if srcs else []
        except Exception as e:
            logger.error(f"Error fetching sources for notebook {self.id}: {e}")
            raise DatabaseOperationError(e)

    async def get_notes(self) -> List["Note"]:
        # Return notes that belong to this notebook.
        try:
            srcs = await repo_query(
                """
                SELECT * OMIT note.content, note.embedding FROM (
                    SELECT in AS note FROM artifact WHERE out=$id
                    FETCH note
                ) ORDER BY note.updated DESC
                """,
                {"id": ensure_record_id(self.id)},
            )
            return [Note(**src["note"]) for src in srcs] if srcs else []
        except Exception as e:
            logger.error(f"Error fetching notes for notebook {self.id}: {e}")
            raise DatabaseOperationError(e)

    async def get_chat_sessions(self) -> List["ChatSession"]:
        # Return chat sessions associated with this notebook.
        try:
            srcs = await repo_query(
                """
                SELECT * FROM (
                    SELECT <- chat_session AS chat_session
                    FROM refers_to WHERE out=$id
                    FETCH chat_session
                ) ORDER BY chat_session.updated DESC
                """,
                {"id": ensure_record_id(self.id)},
            )
            return [ChatSession(**src["chat_session"][0]) for src in srcs] if srcs else []
        except Exception as e:
            logger.error(f"Error fetching chat sessions for notebook {self.id}: {e}")
            raise DatabaseOperationError(e)

    async def delete(self, delete_exclusive_sources: bool = False) -> Dict[str, int]:
        # Delete notebook and its related artifacts (notes and relations).
        if self.id is None:
            raise InvalidInputError("Cannot delete notebook without an ID")
        try:
            notebook_id = ensure_record_id(self.id)
            deleted_notes = 0

            # Delete each note record first.
            notes = await self.get_notes()
            for note in notes:
                await note.delete()
                deleted_notes += 1

            # Clean up relationship records pointing to this notebook.
            await repo_query(
                "DELETE artifact WHERE out = $notebook_id",
                {"notebook_id": notebook_id},
            )
            await repo_query(
                "DELETE reference WHERE out = $notebook_id",
                {"notebook_id": notebook_id},
            )
            await repo_query(
                "DELETE refers_to WHERE out = $notebook_id",
                {"notebook_id": notebook_id},
            )
            await super().delete()
            return {"deleted_notes": deleted_notes}
        except Exception as e:
            logger.error(f"Error deleting notebook {self.id}: {e}")
            raise DatabaseOperationError(f"Failed to delete notebook: {e}")


class Asset(ObjectModel.__bases__[0]):
    # Simple asset container for files or urls.
    file_path: Optional[str] = None
    url: Optional[str] = None


class Source(ObjectModel):
    # Source is an external document or file used in notebooks.
    table_name: ClassVar[str] = "source"
    nullable_fields: ClassVar[set[str]] = {"status_message", "summary"}
    asset: Optional[Asset] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    topics: Optional[List[str]] = Field(default_factory=list)
    full_text: Optional[str] = None
    status: Optional[Literal["pending", "processing", "completed", "error"]] = "pending"
    status_message: Optional[str] = None

    async def add_to_notebook(self, notebook_id: str) -> Any:
        # Relate this source to a notebook via a `reference` relation.
        if not notebook_id:
            raise InvalidInputError("Notebook ID must be provided")
        return await self.relate("reference", notebook_id)

    async def get_context(
        self, context_size: Literal["short", "long"] = "short"
    ) -> Dict[str, Any]:
        # Return a small or large context for use by the chat system.
        if context_size == "long":
            return dict(id=self.id, title=self.title, full_text=self.full_text)
        return dict(id=self.id, title=self.title)

    async def get_embedded_chunks(self) -> int:
        # Count how many embedding chunks exist for this source.
        try:
            result = await repo_query(
                "SELECT count() AS chunks FROM source_embedding WHERE source=$id GROUP ALL",
                {"id": ensure_record_id(self.id)},
            )
            return result[0]["chunks"] if result else 0
        except Exception as e:
            logger.error(f"Error counting chunks for source {self.id}: {e}")
            raise DatabaseOperationError(e)

    async def delete(self) -> bool:
        # Clean up embedding and reference rows, then delete the source record.
        try:
            source_id = ensure_record_id(self.id)
            await repo_query(
                "DELETE source_embedding WHERE source = $source_id",
                {"source_id": source_id},
            )
            await repo_query(
                "DELETE reference WHERE in = $source_id",
                {"source_id": source_id},
            )
        except Exception as e:
            # Non-fatal cleanup error; log and continue with deletion.
            logger.warning(f"Failed to clean up source {self.id} relations: {e}")
        return await super().delete()


class Note(ObjectModel):
    # Notes are short pieces of content stored in a notebook.
    table_name: ClassVar[str] = "note"
    title: Optional[str] = None
    note_type: Optional[Literal["human", "ai"]] = None
    content: Optional[str] = None

    async def add_to_notebook(self, notebook_id: str) -> Any:
        # Relate this note to a notebook via an `artifact` relation.
        if not notebook_id:
            raise InvalidInputError("Notebook ID must be provided")
        return await self.relate("artifact", notebook_id)

    def get_context(
        self, context_size: Literal["short", "long"] = "short"
    ) -> Dict[str, Any]:
        # Return a small or large context for the note.
        if context_size == "long":
            return dict(id=self.id, title=self.title, content=self.content)
        return dict(
            id=self.id,
            title=self.title,
            content=self.content[:100] if self.content else None,
        )


class ChatSession(ObjectModel):
    # Chat session attached to a notebook or source.
    table_name: ClassVar[str] = "chat_session"
    nullable_fields: ClassVar[set[str]] = {"model_override", "source_id", "notebook_id"}
    title: Optional[str] = None
    model_override: Optional[str] = None
    source_id: Optional[str] = None
    notebook_id: Optional[str] = None

    async def relate_to_notebook(self, notebook_id: str) -> Any:
        # Make this session refer to a notebook.
        if not notebook_id:
            raise InvalidInputError("Notebook ID must be provided")
        return await self.relate("refers_to", notebook_id)

    async def get_messages(self) -> List["ChatMessage"]:
        # Return messages for this session in chronological order.
        try:
            result = await repo_query(
                "SELECT * FROM chat_message WHERE session_id = $sid ORDER BY created ASC",
                {"sid": str(self.id)},
            )
            return [ChatMessage(**r) for r in result] if result else []
        except Exception as e:
            logger.error(f"Error fetching messages for session {self.id}: {e}")
            raise DatabaseOperationError(e)

    @classmethod
    async def get_by_source(cls, source_id: str, user_id: str) -> List["ChatSession"]:
        # Return sessions for a source, filtered by user.
        try:
            result = await repo_query(
                "SELECT * FROM chat_session WHERE source_id = $sid AND user_id = $uid ORDER BY updated DESC",
                {"sid": source_id, "uid": user_id},
            )
            return [cls(**r) for r in result] if result else []
        except Exception as e:
            logger.error(f"Error fetching sessions for source {source_id}: {e}")
            raise DatabaseOperationError(e)

    @classmethod
    async def get_by_notebook(cls, notebook_id: str, user_id: str) -> List["ChatSession"]:
        # Return sessions for a notebook, filtered by user.
        try:
            result = await repo_query(
                "SELECT * FROM chat_session WHERE notebook_id = $nid AND user_id = $uid ORDER BY updated DESC",
                {"nid": notebook_id, "uid": user_id},
            )
            return [cls(**r) for r in result] if result else []
        except Exception as e:
            logger.error(f"Error fetching sessions for notebook {notebook_id}: {e}")
            raise DatabaseOperationError(e)


class ChatMessage(ObjectModel):
    # Single message inside a chat session.
    table_name: ClassVar[str] = "chat_message"
    nullable_fields: ClassVar[set[str]] = {"references_data"}
    session_id: str = ""
    role: Literal["human", "ai"] = "human"
    content: str = ""
    references_data: Optional[str] = None
