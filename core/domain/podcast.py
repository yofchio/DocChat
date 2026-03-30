from typing import Any, ClassVar, Dict, List, Optional

from loguru import logger
from pydantic import ConfigDict, Field, field_validator

from core.database.repository import ensure_record_id, repo_query
from core.domain.base import ObjectModel
from core.exceptions import InvalidInputError


class EpisodeProfile(ObjectModel):
    # Profile for generating episode structure and defaults.
    table_name: ClassVar[str] = "episode_profile"
    nullable_fields: ClassVar[set[str]] = {"description", "outline_llm", "transcript_llm", "language"}

    name: str
    description: Optional[str] = None
    speaker_config: str
    outline_llm: Optional[str] = None
    transcript_llm: Optional[str] = None
    language: Optional[str] = None
    default_briefing: str = ""
    num_segments: int = 5

    @field_validator("num_segments")
    @classmethod
    def validate_segments(cls, v):
        # Require a reasonable number of segments.
        if not 3 <= v <= 20:
            raise ValueError("Number of segments must be between 3 and 20")
        return v

    @classmethod
    async def get_by_name(cls, name: str, user_id: str = None) -> Optional["EpisodeProfile"]:
        # Load an episode profile by name, optionally scoped to a user.
        params = {"name": name}
        query = "SELECT * FROM episode_profile WHERE name = $name"
        if user_id:
            query += " AND user_id = $user_id"
            params["user_id"] = user_id
        result = await repo_query(query, params)
        return cls(**result[0]) if result else None


class SpeakerProfile(ObjectModel):
    # Speaker configuration used when producing episodes.
    table_name: ClassVar[str] = "speaker_profile"
    nullable_fields: ClassVar[set[str]] = {"description", "voice_model"}

    name: str
    description: Optional[str] = None
    voice_model: Optional[str] = None
    speakers: List[Dict[str, Any]] = Field(default_factory=list)

    @field_validator("speakers")
    @classmethod
    def validate_speakers(cls, v):
        # Validate speaker list length and required fields.
        if v and not 1 <= len(v) <= 4:
            raise ValueError("Must have between 1 and 4 speakers")
        required_fields = ["name", "voice_id", "backstory", "personality"]
        for speaker in v:
            for field in required_fields:
                if field not in speaker:
                    raise ValueError(f"Speaker missing required field: {field}")
        return v

    @classmethod
    async def get_by_name(cls, name: str, user_id: str = None) -> Optional["SpeakerProfile"]:
        # Load a speaker profile by name, optionally scoped to a user.
        params = {"name": name}
        query = "SELECT * FROM speaker_profile WHERE name = $name"
        if user_id:
            query += " AND user_id = $user_id"
            params["user_id"] = user_id
        result = await repo_query(query, params)
        return cls(**result[0]) if result else None


class PodcastEpisode(ObjectModel):
    # Main episode record. Stores content, progress and status.
    table_name: ClassVar[str] = "episode"
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    episode_profile: Dict[str, Any] = Field(default_factory=dict)
    speaker_profile: Dict[str, Any] = Field(default_factory=dict)
    briefing: str = ""
    content: str = ""
    audio_file: Optional[str] = None
    transcript: Optional[Dict[str, Any]] = Field(default_factory=dict)
    outline: Optional[Dict[str, Any]] = Field(default_factory=dict)
    status: Optional[str] = "pending"
    progress: Optional[Dict[str, Any]] = Field(default_factory=dict)
    error_message: Optional[str] = None

    @classmethod
    async def get_all_by_status(
        cls, status: str, user_id: Optional[str] = None
    ) -> List["PodcastEpisode"]:
        # Fetch all episodes with a given status (e.g. "pending", "failed").
        params: Dict[str, Any] = {"status": status}
        where = "WHERE status = $status"
        if user_id:
            where += " AND user_id = $user_id"
            params["user_id"] = user_id
        try:
            result = await repo_query(
                f"SELECT * FROM episode {where} ORDER BY updated DESC",
                params,
            )
            return [cls(**row) for row in result] if result else []
        except Exception as e:
            logger.error(f"Error fetching episodes by status {status}: {e}")
            return []

    async def reset_to_pending(self) -> None:
        # Reset a failed or stuck episode back to pending so it can be retried.
        self.status = "pending"
        self.error_message = None
        self.progress = {}
        await self.save()

    async def mark_failed(self, error_msg: str) -> None:
        # Mark this episode as failed with an error message.
        self.status = "failed"
        self.error_message = error_msg[:500]  # keep it short
        self.progress = {"stage": "failed", "detail": error_msg[:200], "pct": 0}
        await self.save()

    def is_finished(self) -> bool:
        # Quick check: is this episode done (completed or failed)?
        return self.status in ("completed", "failed")
