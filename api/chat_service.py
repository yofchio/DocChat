from typing import Any, Dict, List, Optional

from loguru import logger

from core.database.repository import ensure_record_id, repo_query
from core.domain.notebook import ChatSession, Notebook, Note, Source
from core.graphs.chat import run_chat, run_chat_stream
from core.utils.embedding import generate_embedding


# =============================================================================
# RAG (Retrieval-Augmented Generation) — Vector Search
# =============================================================================
# This is the core retrieval step of the RAG pipeline.  Given a user's
# question, we convert it into an embedding vector, then run a cosine-
# similarity search against pre-computed chunk embeddings stored in SurrealDB.
# The top-8 most relevant chunks are returned as "references" that will later
# be injected into the LLM prompt so the model can cite them.
# =============================================================================

async def search_relevant_chunks(
    query: str,
    notebook_id: Optional[str] = None,
    source_id: Optional[str] = None,
    limit: int = 8,
) -> List[Dict[str, Any]]:
    """Search for relevant source chunks using vector similarity.

    Returns a list of reference dicts, each containing:
      - content:      the original text chunk
      - score:        cosine similarity (0-1) between query and chunk
      - source_id:    which source document this chunk belongs to
      - source_title: human-readable title of that source
    """
    try:
        # Step 1: Turn the user's question into a dense vector using the
        #         same embedding model that was used when the source was
        #         originally processed (consistency is critical here).
        query_embedding = await generate_embedding(query)

        # Step 2a: Source-scoped search — only look at chunks belonging to
        #          a single source document.
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
        # Step 2b: Notebook-scoped search — first find all sources linked to
        #          this notebook via the `reference` edge table, then search
        #          across all their chunks.
        elif notebook_id:
            # Look up which sources are attached to this notebook
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

        # Step 3: Enrich each result with the source document's title so the
        #         frontend can display "Based on N references from <title>".
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


# =============================================================================
# Context builders — assemble the text that gets injected into the LLM prompt
# =============================================================================

def build_rag_context(references: List[Dict[str, Any]]) -> str:
    """Format retrieved chunks as a numbered list for the system prompt.

    Example output:
        [1] (Source: lecture-notes.pdf)
        Machine learning is a subset of AI...

        [2] (Source: textbook.pdf)
        Supervised learning requires labeled data...

    These numbers are what the LLM will cite as [1], [2] in its answer.
    The frontend later maps [N] → references[N-1] (1-indexed → 0-indexed).
    """
    if not references:
        return ""
    parts = []
    for i, ref in enumerate(references, 1):
        parts.append(f"[{i}] (Source: {ref['source_title']})\n{ref['content']}")
    return "\n\n".join(parts)


async def build_notebook_context(notebook: Notebook) -> str:
    """Fallback context when vector search returns no results.

    Concatenates raw full_text from every source (truncated to 5 000 chars
    each) and every note in the notebook.  This gives the LLM *something*
    to work with even if embeddings haven't been generated yet.
    """
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
    """Fallback context for source-scoped chat when no chunks are found."""
    if source.full_text:
        return f"### Source: {source.title}\n\n{source.full_text}"
    return f"Source '{source.title}' has no extracted content yet."


# =============================================================================
# Chat entry points — called by the router layer
# =============================================================================

async def chat(
    message: str,
    notebook_id: str,
    history: Optional[List[dict]] = None,
    model_override: Optional[str] = None,
) -> str:
    """Non-streaming chat (not used by the main UI, kept for API compat)."""
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
    """Basic streaming chat without RAG references (legacy path)."""
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
    """Streaming chat with RAG references scoped to a single source.

    Returns a tuple of (references, async-generator-of-content-chunks).
    The router layer sends `references` first, then iterates the generator
    to stream content chunks over SSE.
    """
    # 1. Vector search within this source's chunks
    references = await search_relevant_chunks(query=message, source_id=source_id)
    # 2. Build numbered context from search results
    rag_context = build_rag_context(references)

    source = await Source.get(source_id)
    if rag_context:
        # RAG path: use retrieved chunks as context
        context = f"### Source: {source.title}\n\n## Relevant Sections:\n{rag_context}"
    else:
        # Fallback: use the source's full text
        context = await build_source_context(source)

    # 3. Return references + a streaming generator
    #    use_citations=True tells run_chat_stream to instruct the LLM to
    #    insert [1], [2] markers in its answer
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
    """Streaming chat with RAG references scoped to an entire notebook.

    Same pattern as source_chat_stream_with_refs but the vector search
    covers ALL sources attached to the notebook.
    """
    # 1. Vector search across all sources in the notebook
    references = await search_relevant_chunks(query=message, notebook_id=notebook_id)
    rag_context = build_rag_context(references)

    if rag_context:
        context = f"## Relevant Sections from Notebook:\n{rag_context}"
    else:
        # Fallback when no embeddings are available
        notebook = await Notebook.get(notebook_id)
        context = await build_notebook_context(notebook)

    return references, run_chat_stream(
        message=message,
        notebook_context=context,
        history=history,
        model_override=model_override,
        use_citations=bool(references),
    )
