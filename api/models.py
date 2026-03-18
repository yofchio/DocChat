from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Auth ──
class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    email: str
    password: str = Field(..., min_length=6)


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    created: Optional[Any] = None


# ── Notebook ──
class CreateNotebookRequest(BaseModel):
    name: str = Field(..., min_length=1)
    description: str = ""


class UpdateNotebookRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    archived: Optional[bool] = None


# ── Source ──
class CreateSourceFromURLRequest(BaseModel):
    url: str
    notebook_id: Optional[str] = None


class UpdateSourceRequest(BaseModel):
    title: Optional[str] = None


# ── Note ──
class CreateNoteRequest(BaseModel):
    title: Optional[str] = None
    content: str = Field(..., min_length=1)
    note_type: Optional[str] = "human"
    notebook_id: Optional[str] = None


class UpdateNoteRequest(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None


# ── Chat ──
class ChatRequest(BaseModel):
    message: str
    notebook_id: str
    session_id: Optional[str] = None
    model_override: Optional[str] = None


class CreateSessionRequest(BaseModel):
    source_id: Optional[str] = None
    notebook_id: Optional[str] = None
    title: Optional[str] = None


# ── Search ──
class SearchRequest(BaseModel):
    query: str
    search_type: str = "vector"
    results: int = 10
    search_sources: bool = True
    search_notes: bool = True
