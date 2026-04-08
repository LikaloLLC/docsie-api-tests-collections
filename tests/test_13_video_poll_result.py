"""
Tests for polling a video-to-docs job to completion and retrieving the result.

Depends on test_12 having submitted a draft job. The job_id is imported from
that module's _state dict. Polling uses a 10-minute timeout.
"""
import pytest

from tests.test_12_video_submit import _state as submit_state

pytestmark = [pytest.mark.video]

# Module-level state for downstream tests (test_15)
_state: dict = {}


class TestVideoPollToCompletion:
    """Poll the submitted job until it reaches a terminal state."""

    @pytest.mark.slow
    def test_poll_job_completes(self, api):
        """Poll the draft job from test_12 until done (10-minute timeout)."""
        job_id = submit_state.get("job_id")
        if not job_id:
            pytest.skip("No job_id available from test_12_video_submit")

        data = api.poll_video_job(job_id, timeout=600, interval=15)
        status = data.get("status", "")
        assert status in ("done", "failed", "canceled"), (
            f"Unexpected terminal status: {status}"
        )

        # Store for result retrieval and downstream tests
        _state["job_id"] = job_id
        _state["terminal_status"] = status


class TestVideoResult:
    """GET /video-to-docs/{id}/result/ — retrieve the completed result."""

    @pytest.mark.slow
    def test_result_structure(self, api):
        """Completed job result contains all expected fields."""
        job_id = _state.get("job_id")
        terminal = _state.get("terminal_status")
        if not job_id:
            pytest.skip("No completed job_id available (poll test may have been skipped)")
        if terminal != "done":
            pytest.skip(f"Job ended with status '{terminal}', not 'done'")

        resp = api.get(f"/video-to-docs/{job_id}/result/")
        assert resp.status_code == 200, (
            f"Expected 200, got {resp.status_code}: {resp.text}"
        )
        data = resp.json()

        # Core identification
        assert data["job_id"] == job_id
        assert data["status"] == "done"

        # Markdown output
        assert "markdown" in data, "Result must include 'markdown'"
        assert isinstance(data["markdown"], str) and len(data["markdown"]) > 0, (
            "markdown should be a non-empty string"
        )

        # Transcription
        assert "transcription" in data, "Result must include 'transcription'"

        # Sections
        assert "sections" in data, "Result must include 'sections'"
        assert isinstance(data["sections"], list), "sections should be a list"
        if data["sections"]:
            section = data["sections"][0]
            assert "title" in section, "Section item should have 'title'"
            assert "content" in section, "Section item should have 'content'"
            assert "heading_level" in section, "Section item should have 'heading_level'"

        # Images
        assert "images" in data, "Result must include 'images'"
        assert isinstance(data["images"], list), "images should be a list"

        # Duration
        assert "duration_minutes" in data
        if data["duration_minutes"] is not None:
            assert data["duration_minutes"] > 0, "duration_minutes should be positive"

        # Credits
        assert "credits_charged" in data
        if data["credits_charged"] is not None:
            assert data["credits_charged"] > 0, "credits_charged should be positive"

        # Quality matches submission
        submitted_quality = submit_state.get("quality", "draft")
        assert data.get("quality") == submitted_quality, (
            f"Expected quality='{submitted_quality}', got '{data.get('quality')}'"
        )

    @pytest.mark.slow
    def test_result_has_urls(self, api):
        """Completed result includes temporary download URLs."""
        job_id = _state.get("job_id")
        terminal = _state.get("terminal_status")
        if not job_id or terminal != "done":
            pytest.skip("No completed job available")

        data = api.get(f"/video-to-docs/{job_id}/result/").json()

        # result_url and transcription_url are required per schema (nullable)
        assert "result_url" in data
        assert "transcription_url" in data
        assert "expires_in_seconds" in data


class TestVideoResultNegative:
    """Negative cases for result and status retrieval."""

    @pytest.mark.negative
    def test_result_nonexistent_job_returns_404(self, api):
        """GET result for a non-existent job_id returns 404."""
        resp = api.get("/video-to-docs/nonexistent_job_id_xyz/result/")
        assert resp.status_code == 404, (
            f"Expected 404 for nonexistent job, got {resp.status_code}: {resp.text}"
        )

    @pytest.mark.negative
    def test_status_nonexistent_job_returns_404(self, api):
        """GET status for a non-existent job_id returns 404."""
        resp = api.get("/video-to-docs/nonexistent_job_id_xyz/status/")
        assert resp.status_code == 404, (
            f"Expected 404 for nonexistent job, got {resp.status_code}: {resp.text}"
        )
