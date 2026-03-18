import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger

from api.deps import get_current_user
from api.models import CreateSessionRequest
from core.domain.notebook import ChatMessage, ChatSession
from core.domain.user import User

router = APIRouter(prefix="/chat/sessions", tags=["chat-sessions"])


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

    from core.database.repository import repo_query
    await repo_query(
        "DELETE chat_message WHERE session_id = $sid",
        {"sid": str(session.id)},
    )
    await session.delete()
    return {"data": {"deleted": True}}
