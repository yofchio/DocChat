from loguru import logger

from core.domain.podcast import PodcastEpisode


async def generate_podcast_task(episode_id: str):
    """Background task to generate a podcast episode.

    Placeholder for full podcast-creator integration.
    For now, generates outline and transcript via LLM.
    """
    try:
        episode = await PodcastEpisode.get(episode_id)
        episode.status = "processing"
        await episode.save()

        logger.info(f"Generating podcast episode: {episode.name}")

        from core.ai.provision import provision_chat_model
        from langchain_core.messages import HumanMessage, SystemMessage

        model = await provision_chat_model()

        # Generate outline
        outline_prompt = f"""Generate a podcast episode outline with {episode.episode_profile.get('num_segments', 5)} segments.

Topic/Briefing: {episode.briefing}

Source Content:
{episode.content[:10000]}

Return a JSON object with:
- title: episode title
- segments: array of objects with "title" and "description" fields
"""
        outline_response = await model.ainvoke([
            SystemMessage(content="You are a podcast producer. Generate structured outlines."),
            HumanMessage(content=outline_prompt),
        ])
        episode.outline = {"raw": outline_response.content}

        # Generate transcript
        speakers = episode.speaker_profile.get("speakers", [{"name": "Host"}])
        speaker_names = [s.get("name", f"Speaker {i+1}") for i, s in enumerate(speakers)]

        transcript_prompt = f"""Write a natural conversational podcast transcript based on this outline:

{outline_response.content}

Speakers: {', '.join(speaker_names)}

Write an engaging conversation. Format as:
[Speaker Name]: dialogue text
"""
        transcript_response = await model.ainvoke([
            SystemMessage(content="You are a podcast scriptwriter. Write engaging, natural dialogue."),
            HumanMessage(content=transcript_prompt),
        ])
        episode.transcript = {"raw": transcript_response.content}
        episode.status = "completed"
        await episode.save()

        logger.success(f"Podcast episode generated: {episode.name}")

    except Exception as e:
        logger.error(f"Podcast generation failed for {episode_id}: {e}")
        try:
            episode = await PodcastEpisode.get(episode_id)
            episode.status = "failed"
            episode.error_message = str(e)
            await episode.save()
        except Exception:
            pass
