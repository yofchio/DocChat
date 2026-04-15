# Tests for core/domain/podcast.py
#
# Covers:
# - Validators (unit tests)
# - Model construction (unit tests)
# - DB queries with mocked repo functions (integration tests)

from unittest.mock import AsyncMock, patch

import pytest

from core.domain.podcast import EpisodeProfile, PodcastEpisode, SpeakerProfile


# EpisodeProfile


VALID_SPEAKER = {
    "name": "Host",
    "voice_id": "v1",
    "backstory": "A curious host",
    "personality": "friendly",
}


class TestEpisodeProfile:
    def test_valid_profile(self):
        ep = EpisodeProfile(name="Tech Talk", speaker_config="config1", num_segments=5)
        assert ep.name == "Tech Talk"
        assert ep.num_segments == 5

    def test_default_num_segments(self):
        ep = EpisodeProfile(name="Talk", speaker_config="c1")
        assert ep.num_segments == 5

    def test_segments_too_low(self):
        with pytest.raises(ValueError):
            EpisodeProfile(name="Talk", speaker_config="c1", num_segments=2)

    def test_segments_too_high(self):
        with pytest.raises(ValueError):
            EpisodeProfile(name="Talk", speaker_config="c1", num_segments=21)

    def test_segments_boundary_low(self):
        ep = EpisodeProfile(name="Talk", speaker_config="c1", num_segments=3)
        assert ep.num_segments == 3

    def test_segments_boundary_high(self):
        ep = EpisodeProfile(name="Talk", speaker_config="c1", num_segments=20)
        assert ep.num_segments == 20

    @pytest.mark.asyncio
    async def test_get_by_name_found(self):
        with patch("core.domain.podcast.repo_query", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = [
                {"id": "ep:1", "name": "Tech Talk", "speaker_config": "c1", "num_segments": 5}
            ]
            result = await EpisodeProfile.get_by_name("Tech Talk")

        assert result is not None
        assert result.name == "Tech Talk"

    @pytest.mark.asyncio
    async def test_get_by_name_not_found(self):
        with patch("core.domain.podcast.repo_query", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = []
            result = await EpisodeProfile.get_by_name("Nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_name_with_user_id(self):
        with patch("core.domain.podcast.repo_query", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = []
            await EpisodeProfile.get_by_name("Talk", user_id="user:1")

        query = mock_q.call_args[0][0]
        assert "user_id" in query


# SpeakerProfile


class TestSpeakerProfile:
    def test_valid_profile(self):
        sp = SpeakerProfile(name="Default Speakers", speakers=[VALID_SPEAKER])
        assert sp.name == "Default Speakers"
        assert len(sp.speakers) == 1

    def test_empty_speakers_allowed(self):
        sp = SpeakerProfile(name="Empty", speakers=[])
        assert sp.speakers == []

    def test_too_many_speakers(self):
        speakers = [
            {**VALID_SPEAKER, "name": f"Speaker {i}"} for i in range(5)
        ]
        with pytest.raises(ValueError, match="between 1 and 4"):
            SpeakerProfile(name="Crowded", speakers=speakers)

    def test_missing_required_field(self):
        bad_speaker = {"name": "Host"}  # missing voice_id, backstory, personality
        with pytest.raises(ValueError, match="missing required field"):
            SpeakerProfile(name="Bad", speakers=[bad_speaker])

    def test_max_speakers(self):
        speakers = [
            {**VALID_SPEAKER, "name": f"Speaker {i}"} for i in range(4)
        ]
        sp = SpeakerProfile(name="Full", speakers=speakers)
        assert len(sp.speakers) == 4

    @pytest.mark.asyncio
    async def test_get_by_name_found(self):
        with patch("core.domain.podcast.repo_query", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = [
                {"id": "sp:1", "name": "Default", "speakers": [VALID_SPEAKER]}
            ]
            result = await SpeakerProfile.get_by_name("Default")

        assert result is not None
        assert result.name == "Default"

    @pytest.mark.asyncio
    async def test_get_by_name_not_found(self):
        with patch("core.domain.podcast.repo_query", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = []
            result = await SpeakerProfile.get_by_name("Ghost")

        assert result is None


# PodcastEpisode


class TestPodcastEpisode:
    def test_default_status_is_pending(self):
        ep = PodcastEpisode(name="Ep 1")
        assert ep.status == "pending"

    def test_is_finished_completed(self):
        ep = PodcastEpisode(name="Ep 1", status="completed")
        assert ep.is_finished() is True

    def test_is_finished_failed(self):
        ep = PodcastEpisode(name="Ep 1", status="failed")
        assert ep.is_finished() is True

    def test_is_finished_pending(self):
        ep = PodcastEpisode(name="Ep 1", status="pending")
        assert ep.is_finished() is False

    def test_is_finished_processing(self):
        ep = PodcastEpisode(name="Ep 1", status="processing")
        assert ep.is_finished() is False

    @pytest.mark.asyncio
    async def test_get_all_by_status(self):
        with patch("core.domain.podcast.repo_query", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = [
                {"id": "ep:1", "name": "Ep 1", "status": "pending"},
                {"id": "ep:2", "name": "Ep 2", "status": "pending"},
            ]
            episodes = await PodcastEpisode.get_all_by_status("pending")

        assert len(episodes) == 2

    @pytest.mark.asyncio
    async def test_get_all_by_status_with_user(self):
        with patch("core.domain.podcast.repo_query", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = []
            await PodcastEpisode.get_all_by_status("pending", user_id="user:1")

        query = mock_q.call_args[0][0]
        assert "user_id" in query

    @pytest.mark.asyncio
    async def test_get_all_by_status_handles_error(self):
        with patch("core.domain.podcast.repo_query", new_callable=AsyncMock) as mock_q:
            mock_q.side_effect = Exception("db error")
            result = await PodcastEpisode.get_all_by_status("pending")

        assert result == []

    @pytest.mark.asyncio
    async def test_mark_failed(self):
        with (
            patch("core.domain.base.repo_update", new_callable=AsyncMock) as mock_update,
        ):
            mock_update.return_value = [{"id": "ep:1", "name": "Ep 1", "status": "failed"}]
            ep = PodcastEpisode(
                id="ep:1", name="Ep 1", status="processing",
                created="2024-01-01T00:00:00",
            )
            await ep.mark_failed("Something broke badly")

        assert ep.status == "failed"
        assert ep.error_message == "Something broke badly"

    @pytest.mark.asyncio
    async def test_mark_failed_truncates_long_message(self):
        with patch("core.domain.base.repo_update", new_callable=AsyncMock) as mock_update:
            mock_update.return_value = [{"id": "ep:1", "name": "Ep 1", "status": "failed"}]
            ep = PodcastEpisode(
                id="ep:1", name="Ep 1", status="processing",
                created="2024-01-01T00:00:00",
            )
            long_msg = "x" * 1000
            await ep.mark_failed(long_msg)

        assert len(ep.error_message) == 500

    @pytest.mark.asyncio
    async def test_reset_to_pending(self):
        with patch("core.domain.base.repo_update", new_callable=AsyncMock) as mock_update:
            mock_update.return_value = [{"id": "ep:1", "name": "Ep 1", "status": "pending"}]
            ep = PodcastEpisode(
                id="ep:1", name="Ep 1", status="failed",
                error_message="old error", created="2024-01-01T00:00:00",
            )
            await ep.reset_to_pending()

        assert ep.status == "pending"
        assert ep.error_message is None
        assert ep.progress == {}
