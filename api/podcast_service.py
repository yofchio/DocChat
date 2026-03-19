import asyncio
import json
import os
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from core.domain.podcast import EpisodeProfile, PodcastEpisode, SpeakerProfile
from core.database.repository import repo_query


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


async def _update_progress(episode: PodcastEpisode, stage: str, detail: str, pct: int = 0):
    episode.progress = {"stage": stage, "detail": detail, "pct": min(pct, 100)}
    try:
        await episode.save()
    except Exception:
        pass


async def _load_user_ai_config(user_id: str) -> dict:
    uid = user_id.split(":")[1] if ":" in user_id else user_id
    result = await repo_query(
        "SELECT * FROM user_config WHERE id = $id",
        {"id": f"user_config:{uid}"},
    )
    return result[0] if result else {}


def _build_configs(episode: PodcastEpisode, default_provider: str, default_model: str):
    """Build podcast-creator configure() dicts from DB profiles."""
    from podcast_creator import configure

    ep_prof_dict = episode.episode_profile or {}
    ep_name = ep_prof_dict.get("name", "default")
    ep_prof_dict["outline_provider"] = default_provider
    ep_prof_dict["outline_model"] = default_model
    ep_prof_dict["outline_config"] = {}
    ep_prof_dict["transcript_provider"] = default_provider
    ep_prof_dict["transcript_model"] = default_model
    ep_prof_dict["transcript_config"] = {}
    configure("episode_config", {"profiles": {ep_name: ep_prof_dict}})

    sp_prof_dict = episode.speaker_profile or {}
    sp_name = sp_prof_dict.get("name", "default")

    voice_model = sp_prof_dict.get("voice_model") or os.getenv("DEFAULT_TTS_MODEL") or ""
    openai_key = os.getenv("OPENAI_API_KEY")
    tts_provider = "openai" if openai_key else "google"
    default_google_tts = "gemini-2.5-flash-preview-tts"
    tts_model = str(voice_model) if voice_model else (
        "tts-1" if tts_provider == "openai" else default_google_tts
    )
    if isinstance(voice_model, str) and ":" in voice_model:
        parts = voice_model.split(":", 1)
        if parts[0] and parts[1]:
            tts_provider, tts_model = parts[0].strip(), parts[1].strip()
    elif tts_provider == "google" and str(tts_model).lower().startswith("tts-"):
        tts_model = default_google_tts

    sp_prof_dict["tts_provider"] = tts_provider
    sp_prof_dict["tts_model"] = tts_model
    sp_prof_dict["tts_config"] = {}
    configure("speakers_config", {"profiles": {sp_name: sp_prof_dict}})


# ────────────────────────────────────────────
# Phase 1: Generate outline + transcript only
# ────────────────────────────────────────────
async def generate_text_task(episode_id: str):
    """Background: outline + transcript, then status='review'."""
    episode: Optional[PodcastEpisode] = None
    try:
        episode = await PodcastEpisode.get(episode_id)
        episode.status = "processing"
        await _update_progress(episode, "init", "Preparing…", 0)

        user_cfg = await _load_user_ai_config(episode.user_id) if episode.user_id else {}
        default_provider = user_cfg.get("default_provider") or os.getenv("DEFAULT_AI_PROVIDER", "google")
        default_model = user_cfg.get("default_model") or os.getenv("DEFAULT_AI_MODEL", "gemini-2.5-flash")

        data_root = Path(os.getenv("DATA_FOLDER", "./data")).expanduser().resolve()
        output_root = data_root / "podcasts" / "episodes"
        _ensure_dir(output_root)
        episode_dir_name = str(uuid.uuid4())
        output_dir = (output_root / episode_dir_name).resolve()
        _ensure_dir(output_dir)

        from podcast_creator import configure
        from podcast_creator.graph import workflow as _base_workflow
        from podcast_creator.nodes import generate_outline_node, generate_transcript_node
        from podcast_creator.state import PodcastState
        from podcast_creator.episodes import load_episode_config
        from podcast_creator.speakers import load_speaker_config
        from podcast_creator.language import resolve_language_name
        from langgraph.graph import END, START, StateGraph

        _build_configs(episode, default_provider, default_model)

        ep_prof_name = episode.episode_profile.get("name") or ""
        sp_config_name = episode.speaker_profile.get("name") or episode.speaker_profile.get("speaker_config") or ""

        ep_cfg = load_episode_config(ep_prof_name)
        speaker_profile = load_speaker_config(sp_config_name)
        resolved_language = resolve_language_name(ep_cfg.language) if ep_cfg.language else None

        # Progress hooks via loguru sink
        def _log_sink(message):
            text = str(message)
            if "Generated outline with" in text:
                m = re.search(r"(\d+) segments", text)
                segs = m.group(1) if m else "?"
                try:
                    asyncio.get_event_loop().create_task(
                        _update_progress(episode, "outline", f"Outline: {segs} segments", 30)
                    )
                except Exception:
                    pass
            elif "Generating transcript for segment" in text:
                m = re.search(r"segment (\d+)/(\d+)", text)
                if m:
                    cur, total = int(m.group(1)), int(m.group(2))
                    pct = 30 + int(60 * cur / total)
                    try:
                        asyncio.get_event_loop().create_task(
                            _update_progress(episode, "transcript", f"Transcript {cur}/{total}", pct)
                        )
                    except Exception:
                        pass

        sink_id = logger.add(_log_sink, level="INFO")
        await _update_progress(episode, "outline", "Generating outline…", 5)

        text_wf = StateGraph(PodcastState)
        text_wf.add_node("generate_outline", generate_outline_node)
        text_wf.add_node("generate_transcript", generate_transcript_node)
        text_wf.add_edge(START, "generate_outline")
        text_wf.add_edge("generate_outline", "generate_transcript")
        text_wf.add_edge("generate_transcript", END)
        text_graph = text_wf.compile()

        num_segs = ep_cfg.num_segments or 5
        briefing_text = episode.briefing or ""
        briefing_text += (
            f"\n\n[STRICT LENGTH CONSTRAINT] This podcast MUST have exactly {num_segs} segments. "
            f"Each segment should have at most 3 dialogue turns. "
            f"Keep each dialogue turn to 1-2 sentences maximum. "
            f"The entire podcast should be concise and short."
        )

        initial_state = PodcastState(
            content=episode.content or "",
            briefing=briefing_text,
            num_segments=num_segs,
            language=resolved_language,
            outline=None,
            transcript=[],
            audio_clips=[],
            final_output_file_path=None,
            output_dir=output_dir,
            episode_name=episode_dir_name,
            speaker_profile=speaker_profile,
        )
        config = {"configurable": {
            "outline_provider": default_provider,
            "outline_model": default_model,
            "transcript_provider": default_provider,
            "transcript_model": default_model,
            "outline_config": {},
            "transcript_config": {},
        }}

        result = await text_graph.ainvoke(initial_state, config=config)
        logger.remove(sink_id)

        outline_data = result.get("outline")
        transcript_data: List = result.get("transcript") or []

        episode.outline = {
            "segments": outline_data.model_dump()["segments"]
        } if outline_data else {}
        episode.transcript = {
            "dialogues": [d.model_dump() for d in transcript_data]
        }
        episode.progress = {"stage": "review", "detail": f"{len(transcript_data)} dialogue turns", "pct": 100}
        episode.status = "review"
        # Stash output_dir so phase 2 can reuse it
        episode.outline["__output_dir"] = str(output_dir)
        await episode.save()

        logger.success(f"Text generation done for {episode.name}: {len(transcript_data)} dialogues")

    except Exception as e:
        logger.error(f"Text generation failed for {episode_id}: {e}")
        if not episode:
            try:
                episode = await PodcastEpisode.get(episode_id)
            except Exception:
                episode = None
        if episode:
            episode.status = "failed"
            episode.error_message = str(e)
            episode.progress = {"stage": "failed", "detail": str(e)[:200], "pct": 0}
            await episode.save()


# ────────────────────────────────────────────
# Phase 2: TTS + combine from approved transcript
# ────────────────────────────────────────────
async def generate_audio_task(episode_id: str):
    """Background: TTS on transcript, then combine audio."""
    episode: Optional[PodcastEpisode] = None
    try:
        episode = await PodcastEpisode.get(episode_id)
        episode.status = "processing"
        await _update_progress(episode, "tts_init", "Preparing audio generation…", 0)

        user_cfg = await _load_user_ai_config(episode.user_id) if episode.user_id else {}
        default_provider = user_cfg.get("default_provider") or os.getenv("DEFAULT_AI_PROVIDER", "google")
        default_model = user_cfg.get("default_model") or os.getenv("DEFAULT_AI_MODEL", "gemini-2.5-flash")

        from podcast_creator import configure
        from podcast_creator.nodes import generate_all_audio_node, combine_audio_node
        from podcast_creator.state import PodcastState
        from podcast_creator.core import Dialogue, Outline, Segment
        from podcast_creator.speakers import load_speaker_config
        from langgraph.graph import END, START, StateGraph

        _build_configs(episode, default_provider, default_model)

        sp_config_name = episode.speaker_profile.get("name") or ""
        speaker_profile = load_speaker_config(sp_config_name)

        output_dir_str = (episode.outline or {}).get("__output_dir")
        if not output_dir_str:
            data_root = Path(os.getenv("DATA_FOLDER", "./data")).expanduser().resolve()
            output_dir = (data_root / "podcasts" / "episodes" / str(uuid.uuid4())).resolve()
        else:
            output_dir = Path(output_dir_str).resolve()
        _ensure_dir(output_dir)

        dialogues_raw = (episode.transcript or {}).get("dialogues") or []
        transcript = [Dialogue(**d) for d in dialogues_raw]

        outline_segs = (episode.outline or {}).get("segments") or []
        outline = Outline(segments=[Segment(**s) for s in outline_segs]) if outline_segs else None

        episode_dir_name = output_dir.name

        # Progress tracking
        _progress = {"total": len(transcript), "done": 0}

        def _log_sink(message):
            text = str(message)
            if "audio clips in sequential batches" in text:
                m = re.search(r"Generating (\d+) audio clips", text)
                if m:
                    _progress["total"] = int(m.group(1))
                    try:
                        asyncio.get_event_loop().create_task(
                            _update_progress(episode, "tts", f"TTS: 0/{m.group(1)} clips", 5)
                        )
                    except Exception:
                        pass
            elif "Generated audio clip:" in text:
                _progress["done"] += 1
                done, total = _progress["done"], _progress["total"] or 1
                pct = 5 + int(80 * done / total)
                try:
                    asyncio.get_event_loop().create_task(
                        _update_progress(episode, "tts", f"TTS: {done}/{total} clips", pct)
                    )
                except Exception:
                    pass
            elif "Combining" in text or "combine" in text.lower():
                try:
                    asyncio.get_event_loop().create_task(
                        _update_progress(episode, "combining", "Combining audio…", 90)
                    )
                except Exception:
                    pass

        sink_id = logger.add(_log_sink, level="INFO")
        await _update_progress(episode, "tts", "Starting TTS…", 2)

        audio_wf = StateGraph(PodcastState)
        audio_wf.add_node("generate_all_audio", generate_all_audio_node)
        audio_wf.add_node("combine_audio", combine_audio_node)
        audio_wf.add_edge(START, "generate_all_audio")
        audio_wf.add_edge("generate_all_audio", "combine_audio")
        audio_wf.add_edge("combine_audio", END)
        audio_graph = audio_wf.compile()

        initial_state = PodcastState(
            content=episode.content or "",
            briefing=episode.briefing or "",
            num_segments=len(outline.segments) if outline else 5,
            language=None,
            outline=outline,
            transcript=transcript,
            audio_clips=[],
            final_output_file_path=None,
            output_dir=output_dir,
            episode_name=episode_dir_name,
            speaker_profile=speaker_profile,
        )

        result = await audio_graph.ainvoke(initial_state, config={"configurable": {}})
        logger.remove(sink_id)

        final_audio_path = result.get("final_output_file_path")
        if final_audio_path:
            ap = Path(str(final_audio_path))
            if not ap.is_absolute():
                ap = (output_dir / ap).resolve()
            if ap.exists():
                final_audio_path = str(ap)

        if not final_audio_path:
            audio_exts = [".mp3", ".wav", ".m4a"]
            for ext in audio_exts:
                matches = list(output_dir.rglob(f"*{ext}"))
                audio_subdir = output_dir / "audio"
                if audio_subdir.exists():
                    matches = list(audio_subdir.rglob(f"*{ext}")) + matches
                if matches:
                    final_audio_path = str(matches[0].resolve())
                    break

        episode.audio_file = str(final_audio_path) if final_audio_path else None
        episode.status = "completed"
        episode.progress = {"stage": "done", "detail": "Audio ready", "pct": 100}
        await episode.save()
        logger.success(f"Audio generated for {episode.name}: {episode.audio_file}")

    except Exception as e:
        logger.error(f"Audio generation failed for {episode_id}: {e}")
        if not episode:
            try:
                episode = await PodcastEpisode.get(episode_id)
            except Exception:
                episode = None
        if episode:
            episode.status = "failed"
            episode.error_message = str(e)
            episode.progress = {"stage": "failed", "detail": str(e)[:200], "pct": 0}
            await episode.save()
