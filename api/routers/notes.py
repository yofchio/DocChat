from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from api.deps import get_current_user
from api.models import CreateNoteRequest, UpdateNoteRequest
from core.domain.notebook import Note
from core.domain.user import User

router = APIRouter(prefix="/notes", tags=["notes"])


@router.get("")
async def list_notes(current_user: User = Depends(get_current_user)):
    notes = await Note.get_all(order_by="updated DESC", user_id=current_user.id)
    return {"data": [n.model_dump(exclude={"content"}) for n in notes]}


@router.post("")
async def create_note(
    request: CreateNoteRequest,
    current_user: User = Depends(get_current_user),
):
    note = Note(
        title=request.title,
        content=request.content,
        note_type=request.note_type,
        user_id=current_user.id,
    )
    await note.save()

    if request.notebook_id:
        await note.add_to_notebook(request.notebook_id)

    return {"data": note.model_dump()}


@router.get("/{note_id}")
async def get_note(
    note_id: str,
    current_user: User = Depends(get_current_user),
):
    note = await Note.get(note_id)
    if note.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return {"data": note.model_dump()}


@router.put("/{note_id}")
async def update_note(
    note_id: str,
    request: UpdateNoteRequest,
    current_user: User = Depends(get_current_user),
):
    note = await Note.get(note_id)
    if note.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    if request.title is not None:
        note.title = request.title
    if request.content is not None:
        note.content = request.content

    await note.save()
    return {"data": note.model_dump()}


@router.delete("/{note_id}")
async def delete_note(
    note_id: str,
    current_user: User = Depends(get_current_user),
):
    note = await Note.get(note_id)
    if note.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    await note.delete()
    return {"data": {"deleted": True}}
