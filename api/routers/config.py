import os
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api.deps import get_current_user
from core.database.repository import repo_query, repo_upsert
from core.domain.user import User

router = APIRouter(prefix="/config", tags=["config"])


class AIConfig(BaseModel):
    default_provider: str = "google"
    default_model: str = "gemini-2.5-flash"
    google_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None


class AIConfigResponse(BaseModel):
    default_provider: str
    default_model: str
    # For UI display we return the masked key string (never the full key).
    # If not configured, these will be null.
    google_api_key_set: Optional[str] = None
    openai_api_key_set: Optional[str] = None


PROVIDER_MODELS = {
    "google": [
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-2.5-flash-lite",
        "gemini-2.0-flash-lite",
        "gemini-3-flash-preview",
        "gemini-3-pro-preview",
    ],
    "openai": [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
        "gpt-3.5-turbo",
    ],
}


def _mask_api_key(key: Optional[str]) -> Optional[str]:
    """
    Return a masked version of an API key for UI display.

    Security note: never return the full key to the frontend.
    Format: first 4 chars + '******' + last 2 chars.
    """
    if not key:
        return None
    key = key.strip()
    if len(key) <= 6:
        return f"{key[:2]}******"
    return f"{key[:4]}******{key[-2:]}"


@router.get("")
async def get_config(current_user: User = Depends(get_current_user)):
    config = await _load_user_config(current_user.id)
    google_key = config.get("google_api_key") or os.getenv("GOOGLE_API_KEY")
    openai_key = config.get("openai_api_key") or os.getenv("OPENAI_API_KEY")
    return {
        "data": {
            "default_provider": config.get("default_provider", os.getenv("DEFAULT_AI_PROVIDER", "google")),
            "default_model": config.get("default_model", os.getenv("DEFAULT_AI_MODEL", "gemini-2.5-flash")),
            "google_api_key_set": _mask_api_key(google_key),
            "openai_api_key_set": _mask_api_key(openai_key),
        }
    }


@router.put("")
async def update_config(
    config: AIConfig,
    current_user: User = Depends(get_current_user),
):
    data = {
        "user_id": current_user.id,
        "default_provider": config.default_provider,
        "default_model": config.default_model,
    }
    if config.google_api_key is not None:
        data["google_api_key"] = config.google_api_key
    if config.openai_api_key is not None:
        data["openai_api_key"] = config.openai_api_key

    config_id = f"user_config:{current_user.id.split(':')[1]}"
    await repo_upsert("user_config", config_id, data)
    return {"data": {"saved": True}}


@router.get("/providers")
async def get_providers(current_user: User = Depends(get_current_user)):
    return {"data": PROVIDER_MODELS}


async def get_user_ai_config(user_id: str) -> dict:
    """Get resolved AI config for a user (used by other services)."""
    config = await _load_user_config(user_id)
    return {
        "provider": config.get("default_provider", os.getenv("DEFAULT_AI_PROVIDER", "google")),
        "model": config.get("default_model", os.getenv("DEFAULT_AI_MODEL", "gemini-2.5-flash")),
        "google_api_key": config.get("google_api_key") or os.getenv("GOOGLE_API_KEY"),
        "openai_api_key": config.get("openai_api_key") or os.getenv("OPENAI_API_KEY"),
    }


async def _load_user_config(user_id: str) -> dict:
    uid = user_id.split(":")[1] if ":" in user_id else user_id
    try:
        result = await repo_query(
            "SELECT * FROM user_config WHERE id = $id",
            {"id": f"user_config:{uid}"},
        )
        if result:
            return result[0]
        return {}
    except RuntimeError as e:
        # Backward-compat:
        # Some environments may not yet have `user_config` table (e.g. after
        # switching SurrealDB storage backends). Treat it as "no config".
        if "user_config" in str(e) and "does not exist" in str(e):
            return {}
        raise
