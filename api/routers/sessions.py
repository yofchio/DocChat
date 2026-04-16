import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger

from api.deps import get_current_user
from api.models import CreateSessionRequest
from core.database.repository import repo_query
from core.domain.notebook import ChatMessage, ChatSession
from core.domain.user import User

# Initialize FastAPI router for chat session endpoints
router = APIRouter(prefix="/chat/sessions", tags=["chat-sessions"])


def _highlight_snippet(text: str, query: str, context: int = 120) -> str:
    """
    Extract and highlight a snippet of text containing the search query.
    
    Args:
        text: The full text to extract snippet from
        query: The search query to find in text
        context: Number of characters to show on each side of the match
        
    Returns:
        A truncated snippet with ellipsis indicating if content continues before/after
    """
    if not text:
        return ""
    
    # Convert both text and query to lowercase for case-insensitive search
    lower_text = text.lower()
    lower_query = query.lower()
    
    # Find the position of the query in the text
    idx = lower_text.find(lower_query)
    
    # If query not found, return beginning of text with ellipsis if needed
    if idx == -1:
        return text[:context] + ("..." if len(text) > context else "")
    
    # Calculate start and end positions with context around the match
    start = max(0, idx - context // 2)
    end = min(len(text), idx + len(query) + context // 2)
    snippet = text[start:end]
    
    # Add ellipsis to indicate truncation
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
    """
    Search through user's chat history by session title and message content.
    
    Args:
        q: Search query string (required, minimum 1 character)
        current_user: Current authenticated user
        
    Returns:
        Dictionary containing list of search results with session info and match details
    """
    if not q.strip():
        return {"data": []}
    
    try:
        results: list[dict] = []
        # Keep track of sessions already added to avoid duplicates
        seen_sessions: set[str] = set()

        # First, search for matches in session titles
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
        
        # Process title matches and add to results
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

        # Search for matches in chat message content
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

        # Cache to store session info and avoid redundant queries
        session_cache: dict[str, dict] = {}
        
        # Process message matches
        for msg in (msg_hits or []):
            raw_sid = str(msg.get("session_id", ""))
            sid = raw_sid
            
            # Fetch session info if not already cached
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
            
            # Skip if this session was already added from title matches
            if sess_id_str in seen_sessions:
                continue
            
            seen_sessions.add(sess_id_str)

            # Add message match result with highlighted snippet
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
    """
    List all chat sessions for the current user, optionally filtered by source or notebook.
    
    Args:
        source_id: Optional source ID to filter sessions
        notebook_id: Optional notebook ID to filter sessions
        current_user: Current authenticated user
        
    Returns:
        Dictionary containing list of sessions with metadata
    """
    # Filter sessions based on provided parameters
    if source_id:
        sessions = await ChatSession.get_by_source(source_id, current_user.id)
    elif notebook_id:
        sessions = await ChatSession.get_by_notebook(notebook_id, current_user.id)
    else:
        # Get all sessions for user, ordered by most recently updated
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
    """
    Create a new chat session for the current user.
    
    Args:
        request: CreateSessionRequest containing session details (title, source_id, notebook_id)
        current_user: Current authenticated user
        
    Returns:
        Dictionary containing newly created session data
    """
    # Initialize new chat session with provided or default title
    session = ChatSession(
        title=request.title or "New Chat",
        source_id=request.source_id,
        notebook_id=request.notebook_id,
        user_id=current_user.id,
    )
    
    # Persist session to database
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
    """
    Retrieve all messages in a specific chat session.
    
    Args:
        session_id: ID of the session to retrieve messages from
        current_user: Current authenticated user
        
    Returns:
        Dictionary containing list of messages with content and metadata
        
    Raises:
        HTTPException: 403 if user doesn't own the session
    """
    session = await ChatSession.get(session_id)
    
    # Verify user has permission to access this session
    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Retrieve all messages from the session
    messages = await session.get_messages()
    
    return {
        "data": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                # Parse JSON references if available, otherwise return None
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
    """
    Update a chat session (e.g., change title).
    
    Args:
        session_id: ID of the session to update
        data: Dictionary containing fields to update
        current_user: Current authenticated user
        
    Returns:
        Dictionary containing updated session data
        
    Raises:
        HTTPException: 403 if user doesn't own the session
    """
    session = await ChatSession.get(session_id)
    
    # Verify user has permission to modify this session
    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Update session title if provided
    if "title" in data:
        session.title = data["title"]
    
    # Save changes to database
    await session.save()
    
    return {"data": {"id": session.id, "title": session.title}}


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Delete a chat session and all its messages.
    
    Args:
        session_id: ID of the session to delete
        current_user: Current authenticated user
        
    Returns:
        Dictionary confirming deletion
        
    Raises:
        HTTPException: 403 if user doesn't own the session
    """
    session = await ChatSession.get(session_id)
    
    # Verify user has permission to delete this session
    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Delete all messages in the session first
    await repo_query(
        "DELETE chat_message WHERE session_id = $sid",
        {"sid": str(session.id)},
    )
    
    # Delete the session itself
    await session.delete()
    
    return {"data": {"deleted": True}}