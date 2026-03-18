from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

from api.deps import get_current_user
from core.domain.notebook import Notebook
from core.domain.podcast import EpisodeProfile, PodcastEpisode, SpeakerProfile
from core.domain.user import User

router = APIRouter(prefix="/podcasts", tags=["podcasts"])


# ── Request models ──
class EpisodeProfileRequest(BaseModel):
    name: str
    description: Optional[str] = None
    speaker_config: str
    outline_llm: Optional[str] = None
    transcript_llm: Optional[str] = None
    language: Optional[str] = None
    default_briefing: str = ""
    num_segments: int = 5


class SpeakerProfileRequest(BaseModel):
    name: str
    description: Optional[str] = None
    voice_model: Optional[str] = None
    speakers: list = Field(default_factory=list)


class GeneratePodcastRequest(BaseModel):
    episode_profile_name: str
    speaker_profile_name: str
    episode_name: str
    notebook_id: Optional[str] = None
    content: Optional[str] = None


# ── Episode Profiles ──
@router.get("/episode-profiles")
async def list_episode_profiles(current_user: User = Depends(get_current_user)):
    profiles = await EpisodeProfile.get_all(user_id=current_user.id)
    return {"data": [p.model_dump() for p in profiles]}


@router.post("/episode-profiles")
async def create_episode_profile(
    request: EpisodeProfileRequest,
    current_user: User = Depends(get_current_user),
):
    profile = EpisodeProfile(user_id=current_user.id, **request.model_dump())
    await profile.save()
    return {"data": profile.model_dump()}


@router.put("/episode-profiles/{profile_id}")
async def update_episode_profile(
    profile_id: str,
    request: EpisodeProfileRequest,
    current_user: User = Depends(get_current_user),
):
    profile = await EpisodeProfile.get(profile_id)
    if profile.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    for key, value in request.model_dump().items():
        setattr(profile, key, value)
    await profile.save()
    return {"data": profile.model_dump()}


@router.delete("/episode-profiles/{profile_id}")
async def delete_episode_profile(
    profile_id: str, current_user: User = Depends(get_current_user)
):
    profile = await EpisodeProfile.get(profile_id)
    if profile.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    await profile.delete()
    return {"data": {"deleted": True}}


# ── Speaker Profiles ──
@router.get("/speaker-profiles")
async def list_speaker_profiles(current_user: User = Depends(get_current_user)):
    profiles = await SpeakerProfile.get_all(user_id=current_user.id)
    return {"data": [p.model_dump() for p in profiles]}


@router.post("/speaker-profiles")
async def create_speaker_profile(
    request: SpeakerProfileRequest,
    current_user: User = Depends(get_current_user),
):
    profile = SpeakerProfile(user_id=current_user.id, **request.model_dump())
    await profile.save()
    return {"data": profile.model_dump()}


@router.put("/speaker-profiles/{profile_id}")
async def update_speaker_profile(
    profile_id: str,
    request: SpeakerProfileRequest,
    current_user: User = Depends(get_current_user),
):
    profile = await SpeakerProfile.get(profile_id)
    if profile.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    for key, value in request.model_dump().items():
        setattr(profile, key, value)
    await profile.save()
    return {"data": profile.model_dump()}


@router.delete("/speaker-profiles/{profile_id}")
async def delete_speaker_profile(
    profile_id: str, current_user: User = Depends(get_current_user)
):
    profile = await SpeakerProfile.get(profile_id)
    if profile.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    await profile.delete()
    return {"data": {"deleted": True}}


# ── Episodes ──
@router.get("/episodes")
async def list_episodes(current_user: User = Depends(get_current_user)):
    episodes = await PodcastEpisode.get_all(
        order_by="updated DESC", user_id=current_user.id
    )
    return {"data": [e.model_dump(exclude={"content"}) for e in episodes]}


@router.get("/episodes/{episode_id}")
async def get_episode(episode_id: str, current_user: User = Depends(get_current_user)):
    episode = await PodcastEpisode.get(episode_id)
    if episode.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return {"data": episode.model_dump()}


@router.post("/generate")
async def generate_podcast(
    request: GeneratePodcastRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    ep_profile = await EpisodeProfile.get_by_name(request.episode_profile_name, current_user.id)
    if not ep_profile:
        raise HTTPException(status_code=404, detail="Episode profile not found")

    sp_profile = await SpeakerProfile.get_by_name(request.speaker_profile_name, current_user.id)
    if not sp_profile:
        raise HTTPException(status_code=404, detail="Speaker profile not found")

    content = request.content or ""
    if not content and request.notebook_id:
        notebook = await Notebook.get(request.notebook_id)
        if notebook.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        from api.chat_service import build_notebook_context
        content = await build_notebook_context(notebook)

    episode = PodcastEpisode(
        name=request.episode_name,
        episode_profile=ep_profile.model_dump(),
        speaker_profile=sp_profile.model_dump(),
        briefing=ep_profile.default_briefing,
        content=content,
        status="pending",
        user_id=current_user.id,
    )
    await episode.save()

    from api.podcast_service import generate_podcast_task
    background_tasks.add_task(generate_podcast_task, episode.id)

    return {"data": episode.model_dump(exclude={"content"})}


@router.delete("/episodes/{episode_id}")
async def delete_episode(
    episode_id: str, current_user: User = Depends(get_current_user)
):
    episode = await PodcastEpisode.get(episode_id)
    if episode.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    await episode.delete()
    return {"data": {"deleted": True}}
