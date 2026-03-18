from typing import Any, Dict, List, Optional

from loguru import logger

from core.database.repository import ensure_record_id, repo_query
from core.domain.notebook import ChatSession, Notebook, Note, Source
from core.graphs.chat import run_chat, run_chat_stream
from core.utils.embedding import generate_embedding


async def search_relevant_chunks(
    query: str,
    notebook_id: Optional[str] = None,
    source_id: Optional[str] = None,
    limit: int = 8,
) -> List[Dict[str, Any]]:
    """Search for relevant source chunks using vector similarity."""
    try:
        query_embedding = await generate_embedding(query)

        if source_id:
            results = await repo_query(
                """
                SELECT
                    id, content, source,
                    vector::similarity::cosine(embedding, $embed) AS score
                FROM source_embedding
                WHERE source = $source_id
                  AND vector::similarity::cosine(embedding, $embed) > 0.3
                ORDER BY score DESC
                LIMIT $limit
                """,
                {
                    "embed": query_embedding,
                    "source_id": ensure_record_id(source_id),
                    "limit": limit,
                },
            )
        elif notebook_id:
            sources = await repo_query(
                "SELECT in AS source FROM reference WHERE out = $nb_id",
                {"nb_id": ensure_record_id(notebook_id)},
            )
            source_ids = [s["source"] for s in sources] if sources else []
            if not source_ids:
                return []
            results = await repo_query(
                """
                SELECT
                    id, content, source,
                    vector::similarity::cosine(embedding, $embed) AS score
                FROM source_embedding
                WHERE source IN $source_ids
                  AND vector::similarity::cosine(embedding, $embed) > 0.3
                ORDER BY score DESC
                LIMIT $limit
                """,
                {
                    "embed": query_embedding,
                    "source_ids": source_ids,
                    "limit": limit,
                },
            )
        else:
            return []

        refs = []
        for r in results:
            src_id = r.get("source")
            src_title = "Unknown"
            if src_id:
                try:
                    src = await Source.get(str(src_id))
                    src_title = src.title or "Untitled"
                except Exception:
                    pass
            refs.append({
                "content": r.get("content", ""),
                "score": round(r.get("score", 0), 3),
                "source_id": str(src_id) if src_id else None,
                "source_title": src_title,
            })
        return refs
    except Exception as e:
        logger.error(f"Failed to search relevant chunks: {e}")
        return []


def build_rag_context(references: List[Dict[str, Any]]) -> str:
    """Build numbered reference context for the LLM prompt."""
    if not references:
        return ""
    parts = []
    for i, ref in enumerate(references, 1):
        parts.append(f"[{i}] (Source: {ref['source_title']})\n{ref['content']}")
    return "\n\n".join(parts)


async def build_notebook_context(notebook: Notebook) -> str:
    """Build context string from all sources and notes in a notebook."""
    parts = []

    sources = await notebook.get_sources()
    for src in sources:
        full_source = await Source.get(src.id)
        if full_source.full_text:
            parts.append(f"### Source: {full_source.title}\n{full_source.full_text[:5000]}")

    notes = await notebook.get_notes()
    for n in notes:
        full_note = await Note.get(n.id)
        if full_note.content:
            parts.append(f"### Note: {full_note.title or 'Untitled'}\n{full_note.content}")

    return "\n\n---\n\n".join(parts) if parts else "No sources or notes in this notebook yet."


async def build_source_context(source: Source) -> str:
    """Build context string from a single source."""
    if source.full_text:
        return f"### Source: {source.title}\n\n{source.full_text}"
    return f"Source '{source.title}' has no extracted content yet."


async def chat(
    message: str,
    notebook_id: str,
    history: Optional[List[dict]] = None,
    model_override: Optional[str] = None,
) -> str:
    notebook = await Notebook.get(notebook_id)
    context = await build_notebook_context(notebook)
    return await run_chat(
        message=message,
        notebook_context=context,
        history=history,
        model_override=model_override,
    )


async def chat_stream(
    message: str,
    notebook_id: str,
    history: Optional[List[dict]] = None,
    model_override: Optional[str] = None,
):
    notebook = await Notebook.get(notebook_id)
    context = await build_notebook_context(notebook)
    async for chunk in run_chat_stream(
        message=message,
        notebook_context=context,
        history=history,
        model_override=model_override,
    ):
        yield chunk


async def source_chat_stream_with_refs(
    message: str,
    source_id: str,
    history: Optional[List[dict]] = None,
    model_override: Optional[str] = None,
):
    """Stream chat with RAG references from a single source."""
    references = await search_relevant_chunks(query=message, source_id=source_id)
    rag_context = build_rag_context(references)

    source = await Source.get(source_id)
    if rag_context:
        context = f"### Source: {source.title}\n\n## Relevant Sections:\n{rag_context}"
    else:
        context = await build_source_context(source)

    return references, run_chat_stream(
        message=message,
        notebook_context=context,
        history=history,
        model_override=model_override,
        use_citations=bool(references),
    )


async def notebook_chat_stream_with_refs(
    message: str,
    notebook_id: str,
    history: Optional[List[dict]] = None,
    model_override: Optional[str] = None,
):
    """Stream chat with RAG references from a notebook."""
    references = await search_relevant_chunks(query=message, notebook_id=notebook_id)
    rag_context = build_rag_context(references)

    if rag_context:
        context = f"## Relevant Sections from Notebook:\n{rag_context}"
    else:
        notebook = await Notebook.get(notebook_id)
        context = await build_notebook_context(notebook)

    return references, run_chat_stream(
        message=message,
        notebook_context=context,
        history=history,
        model_override=model_override,
        use_citations=bool(references),
    )
