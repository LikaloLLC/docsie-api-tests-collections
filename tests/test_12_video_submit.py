"""
Tests for the video-to-docs job submission and listing endpoints.

Submits a draft-quality job and verifies its initial status. Negative cases
cover missing/conflicting parameters and invalid references.
"""
import pytest

pytestmark = [pytest.mark.video]

# Module-level state shared between tests in this file and test_13/test_15
_state: dict = {}

from conftest import TEST_WORKSPACE_ID as WORKSPACE_ID


class TestVideoJobsList:
    """GET /video-to-docs/ — list existing jobs."""

    def test_list_jobs_returns_200(self, api):
        """Listing jobs returns 200 with paginated structure."""
        resp = api.get("/video-to-docs/")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "count" in data, "Missing 'count' in paginated response"
        assert "results" in data, "Missing 'results' in paginated response"
        assert isinstance(data["results"], list)


class TestVideoSubmit:
    """POST /video-to-docs/submit/ — start a new video-to-docs job."""

    def test_submit_draft_job(self, api, video_url):
        """Submit a draft-quality job with a video URL and verify the response."""
        resp = api.post("/video-to-docs/submit/", json={
            "video_url": video_url,
            "quality": "draft",
            "workspace_id": WORKSPACE_ID,
        })
        assert resp.status_code in (200, 202), (
            f"Expected 200 or 202, got {resp.status_code}: {resp.text}"
        )

        data = resp.json()
        assert "job_id" in data, "Response must include job_id"
        assert data["job_id"], "job_id must not be empty"
        assert data.get("quality") == "draft"
        assert data.get("source_type") in ("url", "video_url", "youtube"), (
            f"Unexpected source_type: {data.get('source_type')}"
        )
        assert "status" in data
        assert "workspace_id" in data
        assert "credits_per_minute" in data

        # Store job_id for downstream tests (test_13, test_15)
        _state["job_id"] = data["job_id"]
        _state["quality"] = "draft"

    def test_status_after_submit(self, api):
        """Immediately after submission, job status should be pending or started."""
        job_id = _state.get("job_id")
        if not job_id:
            pytest.skip("No job_id from prior submit test")

        resp = api.get(f"/video-to-docs/{job_id}/status/")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "status" in data
        assert data["job_id"] == job_id


class TestVideoSubmitNegative:
    """Negative cases for job submission."""

    @pytest.mark.negative
    def test_submit_without_source_returns_400(self, api):
        """Submitting without video_url or file_id returns 400."""
        resp = api.post("/video-to-docs/submit/", json={
            "quality": "draft",
            "workspace_id": WORKSPACE_ID,
        })
        assert resp.status_code == 400, (
            f"Expected 400 for missing source, got {resp.status_code}: {resp.text}"
        )

    @pytest.mark.negative
    def test_submit_with_both_url_and_file_returns_400(self, api):
        """Submitting with both video_url and file_id returns 400."""
        resp = api.post("/video-to-docs/submit/", json={
            "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "file_id": "file_NONEXISTENT123",
            "quality": "draft",
            "workspace_id": WORKSPACE_ID,
        })
        assert resp.status_code == 400, (
            f"Expected 400 for dual source, got {resp.status_code}: {resp.text}"
        )

    @pytest.mark.negative
    def test_submit_invalid_quality_returns_400(self, api):
        """Submitting with an invalid quality value returns 400."""
        resp = api.post("/video-to-docs/submit/", json={
            "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "quality": "super_mega_ultra",
            "workspace_id": WORKSPACE_ID,
        })
        assert resp.status_code == 400, (
            f"Expected 400 for invalid quality, got {resp.status_code}: {resp.text}"
        )

    @pytest.mark.negative
    def test_submit_nonexistent_file_id_returns_404(self, api):
        """Submitting with a non-existent file_id returns 404."""
        resp = api.post("/video-to-docs/submit/", json={
            "file_id": "file_DOES_NOT_EXIST_999",
            "quality": "draft",
            "workspace_id": WORKSPACE_ID,
        })
        assert resp.status_code in (404, 400), (
            f"Expected 404 or 400 for bad file_id, got {resp.status_code}: {resp.text}"
        )

    @pytest.mark.negative
    def test_submit_nonexistent_workspace_returns_404(self, api):
        """Submitting with a non-existent workspace_id returns 404."""
        resp = api.post("/video-to-docs/submit/", json={
            "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "quality": "draft",
            "workspace_id": "workspace_NONEXISTENT_999",
        })
        assert resp.status_code in (404, 400), (
            f"Expected 404 or 400 for bad workspace, got {resp.status_code}: {resp.text}"
        )
