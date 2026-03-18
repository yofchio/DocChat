import os

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, UploadFile
from loguru import logger

from api.deps import get_current_user
from api.models import CreateSourceFromURLRequest, UpdateSourceRequest
from api.sources_service import generate_source_guide, process_source
from core.domain.notebook import Source
from core.domain.user import User

router = APIRouter(prefix="/sources", tags=["sources"])

UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "data/uploads")


@router.get("")
async def list_sources(current_user: User = Depends(get_current_user)):
    sources = await Source.get_all(order_by="updated DESC", user_id=current_user.id)
    return {"data": [s.model_dump(exclude={"full_text"}) for s in sources]}


@router.post("/upload")
async def upload_source(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    notebook_id: str = Form(None),
    current_user: User = Depends(get_current_user),
):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    source = Source(
        title=file.filename,
        asset={"file_path": file_path},
        status="pending",
        user_id=current_user.id,
    )
    await source.save()

    if notebook_id:
        await source.add_to_notebook(notebook_id)

    background_tasks.add_task(process_source, source.id)

    return {"data": source.model_dump(exclude={"full_text"})}


@router.post("/url")
async def create_source_from_url(
    request: CreateSourceFromURLRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    source = Source(
        title=request.url,
        asset={"url": request.url},
        status="pending",
        user_id=current_user.id,
    )
    await source.save()

    if request.notebook_id:
        await source.add_to_notebook(request.notebook_id)

    background_tasks.add_task(process_source, source.id)

    return {"data": source.model_dump(exclude={"full_text"})}


@router.get("/{source_id}")
async def get_source(
    source_id: str,
    current_user: User = Depends(get_current_user),
):
    source = await Source.get(source_id)
    if source.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return {"data": source.model_dump()}


@router.put("/{source_id}")
async def update_source(
    source_id: str,
    request: UpdateSourceRequest,
    current_user: User = Depends(get_current_user),
):
    source = await Source.get(source_id)
    if source.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    if request.title is not None:
        source.title = request.title

    await source.save()
    return {"data": source.model_dump(exclude={"full_text"})}


@router.post("/{source_id}/process")
async def process_source_endpoint(
    source_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    source = await Source.get(source_id)
    if source.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    background_tasks.add_task(process_source, source.id)
    return {"data": {"status": "processing"}}


@router.post("/{source_id}/generate-guide")
async def generate_guide_endpoint(
    source_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    source = await Source.get(source_id)
    if source.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    if not source.full_text:
        raise HTTPException(status_code=400, detail="Source has no content to summarize")
    background_tasks.add_task(generate_source_guide, source)
    return {"data": {"status": "generating"}}


@router.delete("/{source_id}")
async def delete_source(
    source_id: str,
    current_user: User = Depends(get_current_user),
):
    source = await Source.get(source_id)
    if source.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    await source.delete()
    return {"data": {"deleted": True}}
