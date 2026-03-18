from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from api.deps import get_current_user
from api.models import SearchRequest
from core.database.repository import repo_query
from core.domain.user import User
from core.utils.embedding import generate_embedding

router = APIRouter(prefix="/search", tags=["search"])


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
                source_results = await repo_query(
                    """
                    SELECT
                        id, content,
                        vector::similarity::cosine(embedding, $embed) AS score
                    FROM source_embedding
                    WHERE vector::similarity::cosine(embedding, $embed) > 0.2
                    ORDER BY score DESC
                    LIMIT $limit
                    """,
                    {"embed": embedding, "limit": request.results},
                )
                for r in source_results:
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
