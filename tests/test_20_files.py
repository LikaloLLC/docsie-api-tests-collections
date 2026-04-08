"""
Tests for the Files API endpoints.

Covers listing files, generating presigned upload URLs, registering uploaded
files, downloading via presigned URL, and negative cases.
"""
import pytest

pytestmark = pytest.mark.files

FAKE_FILE_ID = "file_00000000000000DOESNOTEXIST"


class TestListFiles:
    """GET /files/ — list files."""

    def test_list_files_returns_200(self, api):
        """Listing files returns 200 with paginated response."""
        resp = api.get("/files/")
        assert resp.status_code == 200
        data = resp.json()
        assert "count" in data
        assert "results" in data
        assert isinstance(data["results"], list)

    def test_list_files_pagination_keys(self, api):
        """Paginated response contains count, next, previous, and results."""
        resp = api.get("/files/", params={"limit": 5})
        assert resp.status_code == 200
        data = resp.json()
        for key in ("count", "next", "previous", "results"):
            assert key in data, f"Missing pagination key: {key}"


class TestGenerateTempUrl:
    """POST /files/generate_temp_url/ — get a presigned upload URL."""

    def test_generate_temp_url_success(self, api):
        """Generating a temp URL with valid key and content_type returns 200."""
        resp = api.post("/files/generate_temp_url/", json={
            "key": "test-uploads/api-test-file.png",
            "content_type": "image/png",
            "public": True,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "url" in data, "Response must contain 'url'"
        assert "key" in data, "Response must contain 'key'"
        assert data["url"].startswith("http"), "url should be a valid URL"

    @pytest.mark.negative
    def test_generate_temp_url_missing_fields(self, api):
        """Omitting required fields returns 400."""
        resp = api.post("/files/generate_temp_url/", json={})
        assert resp.status_code == 400


class TestUploadFile:
    """POST /files/upload/ — register an uploaded file."""

    def test_upload_without_real_s3_object(self, api, resources):
        """Registering a file with a bogus temp_key should fail gracefully.

        Without an actual S3 upload the backend cannot find the object, so we
        expect a 4xx error (400 or 404) rather than a 500.
        """
        resp = api.post("/files/upload/", json={
            "workspace": resources.workspace_id or "workspace_lWoSrrFMPMOgP2og5",
            "public": True,
            "temp_key": "uploads/tmp/DOES_NOT_EXIST_12345",
            "type": "image",
        })
        assert resp.status_code in (400, 404, 422), (
            f"Expected a client error, got {resp.status_code}"
        )


class TestPresignedDownloadUrl:
    """GET /files/{id}/presigned_url/ — get a download URL for a file."""

    def test_presigned_url_for_existing_file(self, api):
        """If files exist, get a presigned download URL for the first one."""
        list_resp = api.get("/files/", params={"limit": 1})
        assert list_resp.status_code == 200
        files = list_resp.json().get("results", [])
        if not files:
            pytest.skip("No files in workspace; cannot test presigned download")

        file_id = files[0]["id"]
        resp = api.get(f"/files/{file_id}/presigned_url/")
        assert resp.status_code == 200
        data = resp.json()
        assert "url" in data, "Presigned download response must contain 'url'"

    @pytest.mark.negative
    def test_presigned_url_for_nonexistent_file(self, api):
        """Requesting a presigned URL for a non-existent file returns 404."""
        resp = api.get(f"/files/{FAKE_FILE_ID}/presigned_url/")
        assert resp.status_code == 404
