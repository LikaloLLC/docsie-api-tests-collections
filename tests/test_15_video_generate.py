"""
Tests for the video-to-docs generate (re-generation) endpoint.

Uses the completed job from test_13 to request a re-generation with different
doc_style and rewrite_instructions.
"""
import pytest

from tests.test_13_video_poll_result import _state as result_state

pytestmark = [pytest.mark.video]

_state: dict = {}


class TestVideoGenerate:
    """POST /video-to-docs/{id}/generate/ — re-generate output with new parameters."""

    @pytest.mark.slow
    def test_generate_sop_from_completed_job(self, api):
        """Generate an SOP-style rewrite from a completed video-to-docs job."""
        job_id = result_state.get("job_id")
        terminal = result_state.get("terminal_status")
        if not job_id:
            pytest.skip("No completed job_id from test_13")
        if terminal != "done":
            pytest.skip(f"Job ended with status '{terminal}', cannot generate")

        resp = api.post(f"/video-to-docs/{job_id}/generate/", json={
            "doc_style": "sop",
            "rewrite_instructions": "Write for compliance",
        })
        assert resp.status_code in (200, 202), (
            f"Expected 200 or 202, got {resp.status_code}: {resp.text}"
        )
        data = resp.json()

        # Response should contain a generate job reference
        gen_key = None
        for key in ("generate_job_id", "job_id", "id"):
            if key in data:
                gen_key = key
                break
        assert gen_key is not None, (
            f"Response should contain a job identifier. Keys present: {list(data.keys())}"
        )
        _state["generate_job_id"] = data[gen_key]


class TestVideoGenerateNegative:
    """Negative cases for the generate endpoint."""

    @pytest.mark.negative
    def test_generate_on_nondone_job_returns_400(self, api):
        """Generate on a non-done (e.g., canceled) job returns 400."""
        # Use the canceled job from test_14 if available
        from tests.test_14_video_cancel import _state as cancel_state
        job_id = cancel_state.get("cancel_job_id")
        if not job_id:
            pytest.skip("No canceled job_id from test_14")

        resp = api.post(f"/video-to-docs/{job_id}/generate/", json={
            "doc_style": "guide",
        })
        assert resp.status_code in (400, 409), (
            f"Expected 400 or 409 for generate on non-done job, "
            f"got {resp.status_code}: {resp.text}"
        )

    @pytest.mark.negative
    def test_generate_nonexistent_job_returns_404(self, api):
        """Generate on a non-existent job returns 404."""
        resp = api.post("/video-to-docs/nonexistent_job_id_xyz/generate/", json={
            "doc_style": "guide",
        })
        assert resp.status_code == 404, (
            f"Expected 404 for nonexistent job, got {resp.status_code}: {resp.text}"
        )
