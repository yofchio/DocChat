from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from api.deps import get_current_user
from api.models import CreateNotebookRequest, UpdateNotebookRequest
from core.domain.notebook import Notebook
from core.domain.user import User
from core.exceptions import NotFoundError

router = APIRouter(prefix="/notebooks", tags=["notebooks"])


@router.get("")
async def list_notebooks(current_user: User = Depends(get_current_user)):
    notebooks = await Notebook.get_all(order_by="updated DESC", user_id=current_user.id)
    return {"data": [n.model_dump() for n in notebooks]}


@router.post("")
async def create_notebook(
    request: CreateNotebookRequest,
    current_user: User = Depends(get_current_user),
):
    notebook = Notebook(
        name=request.name,
        description=request.description,
        user_id=current_user.id,
    )
    await notebook.save()
    return {"data": notebook.model_dump()}


@router.get("/{notebook_id}")
async def get_notebook(
    notebook_id: str,
    current_user: User = Depends(get_current_user),
):
    notebook = await Notebook.get(notebook_id)
    if notebook.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    sources = await notebook.get_sources()
    notes = await notebook.get_notes()
    return {
        "data": {
            **notebook.model_dump(),
            "sources": [s.model_dump(exclude={"full_text"}) for s in sources],
            "notes": [n.model_dump(exclude={"content"}) for n in notes],
        }
    }


@router.put("/{notebook_id}")
async def update_notebook(
    notebook_id: str,
    request: UpdateNotebookRequest,
    current_user: User = Depends(get_current_user),
):
    notebook = await Notebook.get(notebook_id)
    if notebook.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    if request.name is not None:
        notebook.name = request.name
    if request.description is not None:
        notebook.description = request.description
    if request.archived is not None:
        notebook.archived = request.archived

    await notebook.save()
    return {"data": notebook.model_dump()}


@router.delete("/{notebook_id}")
async def delete_notebook(
    notebook_id: str,
    current_user: User = Depends(get_current_user),
):
    notebook = await Notebook.get(notebook_id)
    if notebook.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    result = await notebook.delete()
    return {"data": result}
