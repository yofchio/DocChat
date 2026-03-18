import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel

from api.chat_service import (
    chat,
    notebook_chat_stream_with_refs,
    source_chat_stream_with_refs,
)
from api.deps import get_current_user
from api.models import ChatRequest
from core.domain.notebook import ChatMessage, ChatSession, Notebook, Source
from core.domain.user import User

router = APIRouter(prefix="/chat", tags=["chat"])


class SourceChatRequest(BaseModel):
    message: str
    source_id: str
    session_id: Optional[str] = None
    model_override: Optional[str] = None


async def _load_session_history(session: ChatSession) -> list[dict]:
    """Load message history from a session for LLM context."""
    messages = await session.get_messages()
    return [{"role": m.role, "content": m.content} for m in messages]


async def _save_message(
    session_id: str, role: str, content: str, user_id: str,
    references: list | None = None,
):
    msg = ChatMessage(
        session_id=str(session_id),
        role=role,
        content=content,
        user_id=user_id,
        references_data=json.dumps(references) if references else None,
    )
    await msg.save()


async def _auto_title_session(session: ChatSession, first_message: str):
    """Set session title to the first user message (truncated)."""
    if session.title == "New Chat" or not session.title:
        session.title = first_message[:50] + ("..." if len(first_message) > 50 else "")
        await session.save()


@router.post("")
async def chat_endpoint(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
):
    notebook = await Notebook.get(request.notebook_id)
    if notebook.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        response = await chat(
            message=request.message,
            notebook_id=request.notebook_id,
            model_override=request.model_override,
        )
        return {"data": {"response": response}}
    except Exception as e:
        logger.error(f"Chat failed: {e}")
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


@router.post("/stream")
async def chat_stream_endpoint(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
):
    notebook = await Notebook.get(request.notebook_id)
    if notebook.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    session = None
    history = None
    if request.session_id:
        session = await ChatSession.get(request.session_id)
        if session.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        history = await _load_session_history(session)

    if session:
        await _save_message(session.id, "human", request.message, current_user.id)
        await _auto_title_session(session, request.message)

    async def event_generator():
        try:
            references, stream = await notebook_chat_stream_with_refs(
                message=request.message,
                notebook_id=request.notebook_id,
                history=history,
                model_override=request.model_override,
            )

            if references:
                yield f"data: {json.dumps({'references': references})}\n\n"

            ai_content = ""
            async for chunk in stream:
                ai_content += chunk
                yield f"data: {json.dumps({'content': chunk})}\n\n"
            yield "data: [DONE]\n\n"

            if session:
                await _save_message(
                    session.id, "ai", ai_content, current_user.id,
                    references=references if references else None,
                )
        except Exception as e:
            logger.error(f"Stream chat failed: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/source/stream")
async def source_chat_stream_endpoint(
    request: SourceChatRequest,
    current_user: User = Depends(get_current_user),
):
    source = await Source.get(request.source_id)
    if source.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    session = None
    history = None
    if request.session_id:
        session = await ChatSession.get(request.session_id)
        if session.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        history = await _load_session_history(session)

    if session:
        await _save_message(session.id, "human", request.message, current_user.id)
        await _auto_title_session(session, request.message)

    async def event_generator():
        try:
            references, stream = await source_chat_stream_with_refs(
                message=request.message,
                source_id=request.source_id,
                history=history,
                model_override=request.model_override,
            )

            if references:
                yield f"data: {json.dumps({'references': references})}\n\n"

            ai_content = ""
            async for chunk in stream:
                ai_content += chunk
                yield f"data: {json.dumps({'content': chunk})}\n\n"
            yield "data: [DONE]\n\n"

            if session:
                await _save_message(
                    session.id, "ai", ai_content, current_user.id,
                    references=references if references else None,
                )
        except Exception as e:
            logger.error(f"Source chat stream failed: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
