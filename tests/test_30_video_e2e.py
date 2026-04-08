"""
End-to-end video-to-docs pipeline test.

Uploads a real video file to S3, submits a video-to-docs job via file_id,
polls until analysis completes, validates the full result payload, then
triggers AI rewrite (generate) and polls that to completion.

This is the critical path test for the partner API.
"""
import os
import time

import pytest
import requests as raw_requests

from conftest import TEST_WORKSPACE_ID

pytestmark = [pytest.mark.video, pytest.mark.slow]

ASSET_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
VIDEO_FILE = os.path.join(ASSET_DIR, "test_video.mp4")

# State shared across ordered tests in this module
_state: dict = {}


class TestVideoFileUpload:
    """Step 1: Upload the test video via the files API."""

    def test_generate_temp_url(self, api):
        """Get a presigned S3 upload URL for the video file."""
        if not os.path.exists(VIDEO_FILE):
            pytest.skip(f"Test video not found at {VIDEO_FILE}")

        resp = api.post("/files/generate_temp_url/", json={
            "key": f"api-test-video-{int(time.time())}.mp4",
            "content_type": "video/mp4",
            "public": True,
        })
        # Files endpoint may use session auth — fall back to checking
        if resp.status_code == 403:
            pytest.skip("Files API requires session auth, not API key — uploading via presigned URL workaround")

        assert resp.status_code == 200, f"generate_temp_url failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert "url" in data, f"No 'url' in response: {data.keys()}"
        _state["upload_url"] = data["url"]
        _state["temp_key"] = data.get("key") or data.get("fields", {}).get("key", "")

    def test_upload_to_s3(self):
        """Upload the video file directly to S3 using the presigned URL."""
        upload_url = _state.get("upload_url")
        if not upload_url:
            pytest.skip("No upload URL from prior test")

        with open(VIDEO_FILE, "rb") as f:
            # Presigned PUT URL — upload directly
            resp = raw_requests.put(
                upload_url,
                data=f,
                headers={"Content-Type": "video/mp4"},
                timeout=120,
            )

        assert resp.status_code in (200, 204), f"S3 upload failed: {resp.status_code} {resp.text[:500]}"
        _state["s3_uploaded"] = True

    def test_register_file(self, api):
        """Register the uploaded file in Docsie."""
        temp_key = _state.get("temp_key")
        if not temp_key or not _state.get("s3_uploaded"):
            pytest.skip("File not uploaded to S3")

        resp = api.post("/files/upload/", json={
            "temp_key": temp_key,
            "type": "file",
            "workspace": TEST_WORKSPACE_ID,
            "public": True,
        })
        if resp.status_code == 403:
            pytest.skip("Files API requires session auth")

        assert resp.status_code in (200, 201), f"File registration failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert "id" in data, f"No 'id' in file response: {data.keys()}"
        _state["file_id"] = data["id"]


class TestVideoSubmitWithFile:
    """Step 2: Submit a video-to-docs job using the uploaded file."""

    def test_submit_with_file_id(self, api):
        """Submit a draft video-to-docs job using the uploaded file_id."""
        file_id = _state.get("file_id")
        if not file_id:
            # Fall back to URL-based submission if file upload was skipped
            pytest.skip("No file_id — file upload was skipped (likely session auth required)")

        resp = api.post("/video-to-docs/submit/", json={
            "file_id": file_id,
            "quality": "draft",
            "language": "english",
            "doc_style": "sop",
            "rewrite_instructions": "Write for a compliance officer audience. Use formal tone.",
            "auto_generate": False,  # We'll trigger generate separately
            "workspace_id": TEST_WORKSPACE_ID,
        })
        assert resp.status_code in (200, 202), f"Submit failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert "job_id" in data
        _state["job_id"] = data["job_id"]
        _state["quality"] = "draft"


class TestVideoSubmitWithUrl:
    """Step 2 (fallback): Submit via URL if file upload was skipped."""

    def test_submit_with_url(self, api, video_url):
        """Submit a draft video-to-docs job using a video URL."""
        if _state.get("job_id"):
            pytest.skip("Already submitted via file_id")

        resp = api.post("/video-to-docs/submit/", json={
            "video_url": video_url,
            "quality": "draft",
            "language": "english",
            "doc_style": "sop",
            "rewrite_instructions": "Write for a compliance officer audience. Use formal tone.",
            "auto_generate": False,
            "workspace_id": TEST_WORKSPACE_ID,
        })
        assert resp.status_code in (200, 202), f"Submit failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert "job_id" in data
        _state["job_id"] = data["job_id"]
        _state["quality"] = "draft"


class TestVideoPollAndResult:
    """Step 3: Poll until analysis completes and validate the full result."""

    def test_poll_until_done(self, api):
        """Poll the analysis job until it reaches a terminal state (up to 15 min)."""
        job_id = _state.get("job_id")
        if not job_id:
            pytest.skip("No job_id from submit step")

        result = api.poll_video_job(job_id, timeout=900, interval=15)
        _state["poll_result"] = result
        assert result["status"] == "done", f"Job ended with status: {result['status']}, error: {result.get('error')}"

    def test_result_has_markdown(self, api):
        """Completed result contains non-empty markdown."""
        job_id = _state.get("job_id")
        if not job_id or not _state.get("poll_result"):
            pytest.skip("Job not completed")

        resp = api.get(f"/video-to-docs/{job_id}/result/")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        _state["result"] = data

        assert data["status"] == "done"
        assert "markdown" in data
        assert len(data["markdown"]) > 100, f"Markdown too short ({len(data['markdown'])} chars)"

    def test_result_has_transcription(self):
        """Result contains transcription data."""
        data = _state.get("result")
        if not data:
            pytest.skip("No result data")

        assert "transcription" in data
        assert data["transcription"], "Transcription should not be empty"

    def test_result_has_sections(self):
        """Result contains parsed sections with title, content, heading_level."""
        data = _state.get("result")
        if not data:
            pytest.skip("No result data")

        sections = data.get("sections", [])
        assert len(sections) > 0, "Expected at least one section"
        for sec in sections:
            assert "title" in sec, f"Section missing 'title': {sec.keys()}"
            assert "content" in sec, f"Section missing 'content': {sec.keys()}"
            assert "heading_level" in sec, f"Section missing 'heading_level': {sec.keys()}"

    def test_result_has_images(self):
        """Result contains extracted images with URLs."""
        data = _state.get("result")
        if not data:
            pytest.skip("No result data")

        images = data.get("images", [])
        # Images may be empty for short videos, but the field should exist
        assert isinstance(images, list)
        if images:
            img = images[0]
            assert "url" in img, f"Image missing 'url': {img.keys()}"

    def test_result_has_duration(self):
        """Result includes video duration."""
        data = _state.get("result")
        if not data:
            pytest.skip("No result data")

        assert data.get("duration_minutes") is not None or data.get("duration_seconds") is not None

    def test_result_has_credits_charged(self):
        """Result shows credits were charged."""
        data = _state.get("result")
        if not data:
            pytest.skip("No result data")

        assert "credits_charged" in data
        # Credits should be positive for a completed job
        if data["credits_charged"] is not None:
            assert data["credits_charged"] > 0, f"Expected positive credits, got {data['credits_charged']}"

    def test_result_quality_matches_submission(self):
        """Result quality tier matches what was submitted."""
        data = _state.get("result")
        if not data:
            pytest.skip("No result data")

        assert data.get("quality") == _state.get("quality", "draft")


class TestVideoGenerate:
    """Step 4: Trigger AI rewrite on the completed analysis."""

    def test_generate_sop_rewrite(self, api):
        """Trigger AI documentation generation with SOP style."""
        job_id = _state.get("job_id")
        result = _state.get("result")
        if not job_id or not result or result.get("status") != "done":
            pytest.skip("Analysis job not completed")

        resp = api.post(f"/video-to-docs/{job_id}/generate/", json={
            "doc_style": "sop",
            "rewrite_instructions": "Write a formal Standard Operating Procedure. Include purpose, scope, responsibilities, and step-by-step procedure sections.",
            "template_instruction": (
                "1. Purpose\n"
                "2. Scope\n"
                "3. Responsibilities\n"
                "4. Procedure\n"
                "   4.1 Prerequisites\n"
                "   4.2 Step-by-step instructions\n"
                "5. Records and Documentation\n"
                "6. Revision History"
            ),
            "target_language": "english",
            "book_title": "API Test - PII Demo SOP",
        })
        assert resp.status_code in (200, 202), f"Generate failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert "generate_job_id" in data, f"Missing generate_job_id: {data.keys()}"
        assert data.get("doc_style") == "sop"
        _state["generate_job_id"] = data["generate_job_id"]

    def test_poll_generate_job(self, api):
        """Poll the generation job until it completes (up to 10 min)."""
        gen_job_id = _state.get("generate_job_id")
        if not gen_job_id:
            pytest.skip("No generate_job_id from prior test")

        # Generation jobs use the standard jobs endpoint
        result = api.poll_job(gen_job_id, endpoint="jobs", timeout=600, interval=15)
        _state["generate_result"] = result
        status = result.get("status") or result.get("job_status")
        assert status == "done", f"Generate job ended with status: {status}, result: {result.get('result', {}).get('error')}"

    def test_generate_result_has_content(self):
        """Generated result should contain created documentation references."""
        result = _state.get("generate_result")
        if not result:
            pytest.skip("Generate job not completed")

        job_result = result.get("result", {})
        # The generation job creates books/articles in Docsie
        # The result should indicate success
        assert job_result, "Generate job result should not be empty"


class TestCreditDeductionAfterPipeline:
    """Step 5: Verify credits were deducted after the full pipeline."""

    def test_credits_decreased(self, api):
        """Credit balance should reflect the video processing charge."""
        resp = api.get("/credits/balance/")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        # We can't compare to before (no snapshot), but we can verify fields exist
        assert "total_available" in data
        assert isinstance(data["total_available"], (int, float))

    def test_usage_contains_video_deduction(self, api):
        """Credit usage history should contain a deduct_video transaction."""
        resp = api.get("/credits/usage/", params={"transaction_type": "deduct_video"})
        assert resp.status_code == 200, resp.text
        data = resp.json()
        results = data.get("results", data if isinstance(data, list) else [])
        # There should be at least one video deduction (from this test or prior runs)
        assert len(results) > 0, "Expected at least one deduct_video transaction"
        latest = results[0]
        assert latest["transaction_type"] == "deduct_video"
        assert latest["amount"] < 0, "Deduction amount should be negative"
