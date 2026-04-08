"""
Tests for canceling a video-to-docs job.

Submits a fresh draft job and immediately cancels it. Also covers negative
cases for double-cancel and non-existent job IDs.
"""
import pytest

pytestmark = [pytest.mark.video]

from conftest import TEST_WORKSPACE_ID as WORKSPACE_ID

_state: dict = {}


class TestVideoCancel:
    """Submit then cancel a video-to-docs job."""

    def test_submit_job_for_cancel(self, api, video_url):
        """Submit a draft job specifically to test cancellation."""
        resp = api.post("/video-to-docs/submit/", json={
            "video_url": video_url,
            "quality": "draft",
            "workspace_id": WORKSPACE_ID,
        })
        assert resp.status_code in (200, 202), (
            f"Expected 200/202, got {resp.status_code}: {resp.text}"
        )
        data = resp.json()
        _state["cancel_job_id"] = data["job_id"]

    def test_cancel_job(self, api):
        """POST /video-to-docs/{id}/cancel/ on a pending job succeeds."""
        job_id = _state.get("cancel_job_id")
        if not job_id:
            pytest.skip("No job_id from submit step")

        resp = api.post(f"/video-to-docs/{job_id}/cancel/", json={})
        assert resp.status_code == 200, (
            f"Expected 200 for cancel, got {resp.status_code}: {resp.text}"
        )
        data = resp.json()
        assert data.get("status") in ("canceled", "cancelled"), (
            f"Expected canceled status, got: {data.get('status')}"
        )
        assert data.get("job_id") == job_id

    def test_status_shows_canceled(self, api):
        """After cancellation, the status endpoint reflects canceled."""
        job_id = _state.get("cancel_job_id")
        if not job_id:
            pytest.skip("No job_id from submit step")

        resp = api.get(f"/video-to-docs/{job_id}/status/")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") in ("canceled", "cancelled"), (
            f"Expected canceled, got: {data.get('status')}"
        )


class TestVideoCancelNegative:
    """Negative cases for the cancel endpoint."""

    @pytest.mark.negative
    def test_cancel_already_canceled_returns_400(self, api):
        """Canceling an already-canceled job returns 400."""
        job_id = _state.get("cancel_job_id")
        if not job_id:
            pytest.skip("No canceled job_id available")

        resp = api.post(f"/video-to-docs/{job_id}/cancel/", json={})
        assert resp.status_code == 400, (
            f"Expected 400 for double cancel, got {resp.status_code}: {resp.text}"
        )

    @pytest.mark.negative
    def test_cancel_nonexistent_job_returns_404(self, api):
        """Canceling a non-existent job returns 404."""
        resp = api.post("/video-to-docs/nonexistent_job_id_xyz/cancel/", json={})
        assert resp.status_code == 404, (
            f"Expected 404 for nonexistent job, got {resp.status_code}: {resp.text}"
        )
