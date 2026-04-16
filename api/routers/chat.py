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

# =============================================================================
# Chat Router — SSE streaming endpoints
# =============================================================================
# This router exposes two streaming endpoints:
#   POST /api/chat/stream        — chat within a notebook (all sources)
#   POST /api/chat/source/stream — chat within a single source
#
# Both follow the same Server-Sent Events (SSE) protocol:
#   1. Emit  data: {"references": [...]}     (RAG search results)
#   2. Emit  data: {"content": "..."}  × N   (LLM token chunks)
#   3. Emit  data: [DONE]                    (end-of-stream marker)
#
# The frontend reads these lines via a ReadableStream reader and updates
# the chat UI in real time (typewriter effect).
# =============================================================================

router = APIRouter(prefix="/chat", tags=["chat"])


class SourceChatRequest(BaseModel):
    message: str
    source_id: str
    session_id: Optional[str] = None
    model_override: Optional[str] = None


# ---- Session helpers (history + persistence) --------------------------------

async def _load_session_history(session: ChatSession) -> list[dict]:
    """Fetch all prior messages from this chat session.

    Returns them in the format the LLM layer expects:
        [{"role": "human", "content": "..."}, {"role": "ai", "content": "..."}]
    This list is injected between the SystemMessage and the current
    HumanMessage so the model has multi-turn conversation context.
    """
    messages = await session.get_messages()
    return [{"role": m.role, "content": m.content} for m in messages]


async def _save_message(
    session_id: str, role: str, content: str, user_id: str,
    references: list | None = None,
):
    """Persist a single conversation turn to the database.

    Timing:
      - The human message is saved BEFORE the stream starts (so it's
        immediately visible if the user refreshes).
      - The AI message is saved AFTER the stream completes, because we
        need to accumulate all chunks into the final content first.
      - references (if any) are stored as JSON so they can be re-displayed
        when the user revisits this session.
    """
    msg = ChatMessage(
        session_id=str(session_id),
        role=role,
        content=content,
        user_id=user_id,
        references_data=json.dumps(references) if references else None,
    )
    await msg.save()


async def _auto_title_session(session: ChatSession, first_message: str):
    """Auto-generate a session title from the first user message.

    Only triggers when the title is still the default "New Chat".
    Truncates to 50 characters for a clean sidebar display.
    """
    if session.title == "New Chat" or not session.title:
        session.title = first_message[:50] + ("..." if len(first_message) > 50 else "")
        await session.save()


# ---- Non-streaming endpoint (kept for API compatibility) --------------------

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


# ---- Notebook-scoped streaming endpoint ------------------------------------

@router.post("/stream")
async def chat_stream_endpoint(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
):
    """Stream a chat response for a notebook, with RAG citations.

    Request body: { message, notebook_id, session_id?, model_override? }
    Response:     text/event-stream (SSE)
    """
    # Access control: verify notebook belongs to this user
    notebook = await Notebook.get(request.notebook_id)
    if notebook.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # If session_id is provided, load conversation history for context
    session = None
    history = None
    if request.session_id:
        session = await ChatSession.get(request.session_id)
        if session.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        history = await _load_session_history(session)

    # Persist the user's message BEFORE streaming begins
    if session:
        await _save_message(session.id, "human", request.message, current_user.id)
        await _auto_title_session(session, request.message)

    async def event_generator():
        """Async generator that yields SSE-formatted lines.

        The SSE protocol:
          data: {"references": [...]}   ← sent once, before any content
          data: {"content": "Hello"}    ← sent many times (one per LLM chunk)
          data: {"content": " world"}
          data: [DONE]                  ← signals end of stream
        """
        try:
            # notebook_chat_stream_with_refs does two things:
            #   1. Runs vector search → returns references list
            #   2. Returns an async generator that streams LLM output
            references, stream = await notebook_chat_stream_with_refs(
                message=request.message,
                notebook_id=request.notebook_id,
                history=history,
                model_override=request.model_override,
            )

            # Send references FIRST so the frontend knows what [1],[2] mean
            # before the content starts arriving
            if references:
                yield f"data: {json.dumps({'references': references})}\n\n"

            # Stream LLM output chunk by chunk
            ai_content = ""
            async for chunk in stream:
                ai_content += chunk
                yield f"data: {json.dumps({'content': chunk})}\n\n"
            yield "data: [DONE]\n\n"

            # After streaming completes, persist the full AI response
            if session:
                await _save_message(
                    session.id, "ai", ai_content, current_user.id,
                    references=references if references else None,
                )
        except Exception as e:
            logger.error(f"Stream chat failed: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ---- Source-scoped streaming endpoint --------------------------------------

@router.post("/source/stream")
async def source_chat_stream_endpoint(
    request: SourceChatRequest,
    current_user: User = Depends(get_current_user),
):
    """Stream a chat response scoped to a single source document.

    Same SSE protocol as /stream, but vector search is limited to chunks
    from this one source instead of all sources in a notebook.
    """
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
