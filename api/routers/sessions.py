import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger

from api.deps import get_current_user
from api.models import CreateSessionRequest
from core.database.repository import repo_query
from core.domain.notebook import ChatMessage, ChatSession
from core.domain.user import User

router = APIRouter(prefix="/chat/sessions", tags=["chat-sessions"])


def _highlight_snippet(text: str, query: str, context: int = 120) -> str:
    if not text:
        return ""
    lower_text = text.lower()
    lower_query = query.lower()
    idx = lower_text.find(lower_query)
    if idx == -1:
        return text[:context] + ("..." if len(text) > context else "")
    start = max(0, idx - context // 2)
    end = min(len(text), idx + len(query) + context // 2)
    snippet = text[start:end]
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    return snippet


@router.get("/search")
async def search_chat_history(
    q: str = Query(..., min_length=1),
    current_user: User = Depends(get_current_user),
):
    if not q.strip():
        return {"data": []}
    try:
        results: list[dict] = []
        seen_sessions: set[str] = set()

        title_hits = await repo_query(
            """
            SELECT id, title, notebook_id, source_id, updated
            FROM chat_session
            WHERE user_id = $uid AND string::lowercase(title) CONTAINS string::lowercase($q)
            ORDER BY updated DESC
            LIMIT 20
            """,
            {"uid": current_user.id, "q": q},
        )
        for s in (title_hits or []):
            sid = str(s.get("id", ""))
            seen_sessions.add(sid)
            results.append({
                "session_id": sid,
                "session_title": s.get("title") or "Untitled",
                "notebook_id": s.get("notebook_id"),
                "source_id": s.get("source_id"),
                "match_type": "title",
                "snippet": s.get("title") or "",
                "role": None,
                "updated": str(s.get("updated")) if s.get("updated") else None,
            })

        msg_hits = await repo_query(
            """
            SELECT id, content, session_id, role, created
            FROM chat_message
            WHERE user_id = $uid AND string::lowercase(content) CONTAINS string::lowercase($q)
            ORDER BY created DESC
            LIMIT 40
            """,
            {"uid": current_user.id, "q": q},
        )

        session_cache: dict[str, dict] = {}
        for msg in (msg_hits or []):
            raw_sid = str(msg.get("session_id", ""))
            sid = raw_sid
            if sid not in session_cache:
                try:
                    sess_rows = await repo_query(
                        "SELECT id, title, notebook_id, source_id, updated FROM chat_session WHERE id = $sid",
                        {"sid": raw_sid},
                    )
                    session_cache[sid] = sess_rows[0] if sess_rows else {}
                except Exception:
                    session_cache[sid] = {}

            sess = session_cache[sid]
            sess_id_str = str(sess.get("id", sid))
            if sess_id_str in seen_sessions:
                continue
            seen_sessions.add(sess_id_str)

            results.append({
                "session_id": sess_id_str,
                "session_title": sess.get("title") or "Untitled",
                "notebook_id": sess.get("notebook_id"),
                "source_id": sess.get("source_id"),
                "match_type": "message",
                "snippet": _highlight_snippet(msg.get("content", ""), q),
                "role": msg.get("role"),
                "updated": str(sess.get("updated")) if sess.get("updated") else None,
            })

        return {"data": results}

    except Exception as e:
        logger.error(f"Chat history search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("")
async def list_sessions(
    source_id: Optional[str] = Query(None),
    notebook_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
):
    if source_id:
        sessions = await ChatSession.get_by_source(source_id, current_user.id)
    elif notebook_id:
        sessions = await ChatSession.get_by_notebook(notebook_id, current_user.id)
    else:
        sessions = await ChatSession.get_all(order_by="updated DESC", user_id=current_user.id)

    return {
        "data": [
            {
                "id": s.id,
                "title": s.title,
                "source_id": s.source_id,
                "notebook_id": s.notebook_id,
                "created": str(s.created) if s.created else None,
                "updated": str(s.updated) if s.updated else None,
            }
            for s in sessions
        ]
    }


@router.post("")
async def create_session(
    request: CreateSessionRequest,
    current_user: User = Depends(get_current_user),
):
    session = ChatSession(
        title=request.title or "New Chat",
        source_id=request.source_id,
        notebook_id=request.notebook_id,
        user_id=current_user.id,
    )
    await session.save()
    return {
        "data": {
            "id": session.id,
            "title": session.title,
            "source_id": session.source_id,
            "notebook_id": session.notebook_id,
            "created": str(session.created) if session.created else None,
            "updated": str(session.updated) if session.updated else None,
        }
    }


@router.get("/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    current_user: User = Depends(get_current_user),
):
    session = await ChatSession.get(session_id)
    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    messages = await session.get_messages()
    return {
        "data": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "references": json.loads(m.references_data) if m.references_data else None,
                "created": str(m.created) if m.created else None,
            }
            for m in messages
        ]
    }


@router.put("/{session_id}")
async def update_session(
    session_id: str,
    data: dict,
    current_user: User = Depends(get_current_user),
):
    session = await ChatSession.get(session_id)
    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    if "title" in data:
        session.title = data["title"]
    await session.save()
    return {"data": {"id": session.id, "title": session.title}}


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
):
    session = await ChatSession.get(session_id)
    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    await repo_query(
        "DELETE chat_message WHERE session_id = $sid",
        {"sid": str(session.id)},
    )
    await session.delete()
    return {"data": {"deleted": True}}
