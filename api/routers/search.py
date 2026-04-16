from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from api.deps import get_current_user
from api.models import SearchRequest
from core.database.repository import ensure_record_id, repo_query
from core.domain.user import User
from core.utils.embedding import generate_embedding

router = APIRouter(prefix="/search", tags=["search"])


def format_result_preview(content: str, max_length: int = 200) -> str:
    if not content:
        return ""
    content = content.strip()
    if len(content) <= max_length:
        return content
    return content[:max_length].rsplit(" ", 1)[0] + "..."


def is_valid_query(query: str) -> bool:
    return bool(query and query.strip())


def normalize_score(score: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    if max_val == min_val:
        return 0.0
    return max(0.0, min(1.0, (score - min_val) / (max_val - min_val)))


def deduplicate_results(results: list, key: str = "id") -> list:
    seen = set()
    unique = []
    for r in results:
        val = r.get(key)
        if val not in seen:
            seen.add(val)
            unique.append(r)
    return unique


@router.post("")
async def search(
    request: SearchRequest,
    current_user: User = Depends(get_current_user),
):
    try:
        results = []

        if request.search_type == "vector":
            embedding = await generate_embedding(request.query)

            if request.search_sources:
                owned_sources = await repo_query(
                    "SELECT id FROM source WHERE user_id = $user_id",
                    {"user_id": current_user.id},
                )
                source_ids = [
                    ensure_record_id(row["id"])
                    for row in (owned_sources or [])
                    if row.get("id") is not None
                ]
                source_results = []
                if source_ids:
                    source_results = await repo_query(
                        """
                        SELECT
                            id, content,
                            vector::similarity::cosine(embedding, $embed) AS score
                        FROM source_embedding
                        WHERE source IN $source_ids
                            AND vector::similarity::cosine(embedding, $embed) > 0.2
                        ORDER BY score DESC
                        LIMIT $limit
                        """,
                        {
                            "embed": embedding,
                            "source_ids": source_ids,
                            "limit": request.results,
                        },
                    )
                for r in source_results or []:
                    results.append({
                        "type": "source_chunk",
                        "id": r.get("id"),
                        "content": r.get("content"),
                        "score": r.get("score"),
                    })

            if request.search_notes:
                note_results = await repo_query(
                    """
                    SELECT id, title, content,
                        vector::similarity::cosine(embedding, $embed) AS score
                    FROM note
                    WHERE user_id = $user_id
                        AND embedding IS NOT NONE
                        AND vector::similarity::cosine(embedding, $embed) > 0.2
                    ORDER BY score DESC
                    LIMIT $limit
                    """,
                    {
                        "embed": embedding,
                        "user_id": current_user.id,
                        "limit": request.results,
                    },
                )
                for r in note_results:
                    results.append({
                        "type": "note",
                        "id": r.get("id"),
                        "title": r.get("title"),
                        "content": r.get("content", "")[:200],
                        "score": r.get("score"),
                    })

        elif request.search_type == "text":
            if request.search_sources:
                source_results = await repo_query(
                    """
                    SELECT id, title, full_text
                    FROM source
                    WHERE user_id = $user_id
                        AND (title CONTAINS $query OR full_text CONTAINS $query)
                    LIMIT $limit
                    """,
                    {
                        "user_id": current_user.id,
                        "query": request.query,
                        "limit": request.results,
                    },
                )
                for r in source_results:
                    results.append({
                        "type": "source",
                        "id": r.get("id"),
                        "title": r.get("title"),
                        "content": (r.get("full_text") or "")[:200],
                    })

            if request.search_notes:
                note_results = await repo_query(
                    """
                    SELECT id, title, content
                    FROM note
                    WHERE user_id = $user_id
                        AND (title CONTAINS $query OR content CONTAINS $query)
                    LIMIT $limit
                    """,
                    {
                        "user_id": current_user.id,
                        "query": request.query,
                        "limit": request.results,
                    },
                )
                for r in note_results:
                    results.append({
                        "type": "note",
                        "id": r.get("id"),
                        "title": r.get("title"),
                        "content": (r.get("content") or "")[:200],
                    })

        results.sort(key=lambda x: x.get("score", 0), reverse=True)
        return {"data": results}

    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")
