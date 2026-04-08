"""
Docsie Partner API — Test Suite Configuration

Shared fixtures for all test modules. Loads .env, provides an authenticated
API client, and manages test resource lifecycle (create once, clean up after).
"""
import os
import time

import pytest
import requests
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_URL = os.environ.get("DOCSIE_BASE_URL", "https://staging.docsie.io").rstrip("/")
API_KEY = os.environ.get("DOCSIE_API_KEY", "")
API_PREFIX = f"{BASE_URL}/api_v2/003"

TEST_VIDEO_URL = os.environ.get(
    "TEST_VIDEO_URL",
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
)
TEST_WORKSPACE_ID = os.environ.get("TEST_WORKSPACE_ID", "")


# ---------------------------------------------------------------------------
# API Client
# ---------------------------------------------------------------------------
class DocsieClient:
    """Thin wrapper around requests that handles auth and base URL."""

    def __init__(self, base: str, api_key: str):
        self.base = base
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Api-Key {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

    # Convenience methods with automatic 429 retry --------------------------
    def _request(self, method, path, **kw):
        """Send a request with automatic retry on 429 (rate limited)."""
        for attempt in range(4):
            resp = getattr(self.session, method)(f"{self.base}{path}", **kw)
            if resp.status_code != 429:
                return resp
            retry_after = int(resp.headers.get("Retry-After", 10))
            time.sleep(min(retry_after + 1, 30))
        return resp  # return last 429 if all retries exhausted

    def get(self, path, **kw):
        return self._request("get", path, **kw)

    def post(self, path, **kw):
        return self._request("post", path, **kw)

    def put(self, path, **kw):
        return self._request("put", path, **kw)

    def patch(self, path, **kw):
        return self._request("patch", path, **kw)

    def delete(self, path, **kw):
        return self._request("delete", path, **kw)

    # Polling helper -------------------------------------------------------
    def poll_job(self, job_id, *, endpoint="jobs", timeout=300, interval=10):
        """Poll a job until it reaches a terminal state or times out."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            resp = self.get(f"/{endpoint}/{job_id}/")
            data = resp.json()
            status = data.get("status") or data.get("job_status", "")
            if status in ("done", "failed", "canceled"):
                return data
            time.sleep(interval)
        raise TimeoutError(f"Job {job_id} did not complete within {timeout}s")

    def poll_video_job(self, job_id, **kw):
        """Poll a video-to-docs job via its dedicated status endpoint."""
        kw.setdefault("timeout", 600)
        kw.setdefault("interval", 15)
        deadline = time.time() + kw["timeout"]
        while time.time() < deadline:
            resp = self.get(f"/video-to-docs/{job_id}/status/")
            data = resp.json()
            st = data.get("status", "")
            if st in ("done", "failed", "canceled"):
                return data
            time.sleep(kw["interval"])
        raise TimeoutError(f"Video job {job_id} did not complete within {kw['timeout']}s")


@pytest.fixture(scope="session")
def api():
    """Session-scoped authenticated API client."""
    if not API_KEY:
        pytest.skip("DOCSIE_API_KEY not set — cannot run API tests")
    return DocsieClient(API_PREFIX, API_KEY)


# ---------------------------------------------------------------------------
# Shared test resources — created once per session, cleaned up at the end
# ---------------------------------------------------------------------------
class TestResources:
    """Accumulates IDs of resources created during the test run."""

    def __init__(self):
        self.workspace_id = os.environ.get("TEST_WORKSPACE_ID", "")
        self.documentation_id = os.environ.get("TEST_DOCUMENTATION_ID", "")
        self.book_id = os.environ.get("TEST_BOOK_ID", "")
        self.version_id = ""
        self.language_id = ""
        self.article_id = ""
        self.deployment_id = ""
        self.snippet_id = ""
        self.file_id = ""
        self.video_job_id = ""
        self.generate_job_id = ""

        # Track IDs for cleanup
        self._created_ids: dict[str, list[str]] = {
            "workspaces": [],
            "documentation": [],
            "books": [],
            "versions": [],
            "languages": [],
            "articles": [],
            "deployments": [],
            "snippets": [],
        }

    def track(self, resource_type: str, resource_id: str):
        if resource_type in self._created_ids:
            self._created_ids[resource_type].append(resource_id)


@pytest.fixture(scope="session")
def resources():
    return TestResources()


@pytest.fixture(scope="session")
def test_workspace_id(api):
    """Resolve the test workspace ID — from env or auto-detect the first workspace."""
    if TEST_WORKSPACE_ID:
        return TEST_WORKSPACE_ID
    resp = api.get("/workspaces/?limit=1")
    results = resp.json().get("results", [])
    if results:
        return results[0]["id"]
    pytest.skip("No workspaces found for this API key")


@pytest.fixture(scope="session")
def video_url():
    return TEST_VIDEO_URL
