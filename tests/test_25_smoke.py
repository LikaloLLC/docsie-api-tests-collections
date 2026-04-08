"""
Smoke tests — hit every major GET endpoint and verify 200 + valid JSON.

These tests are intentionally lightweight: they confirm reachability and basic
response shape without inspecting business logic.
"""
import pytest

pytestmark = pytest.mark.smoke

SMOKE_ENDPOINTS = [
    "/workspaces/",
    "/documentation/",
    "/books/",
    "/versions/",
    "/languages/",
    "/articles/",
    pytest.param("/files/", marks=pytest.mark.xfail(reason="FileViewSet uses session auth, not API key auth")),
    "/deployments/",
    "/jobs/",
    "/snippets/",
    "/templates/",
    "/credits/balance/",
    "/credits/usage/",
    "/video-to-docs/",
]


@pytest.mark.parametrize("path", SMOKE_ENDPOINTS)
def test_get_endpoint_returns_200(api, path):
    """GET {path} returns 200 with valid JSON."""
    resp = api.get(path)
    assert resp.status_code == 200, (
        f"GET {path} returned {resp.status_code}: {resp.text[:300]}"
    )
    # Must be parseable JSON
    data = resp.json()
    assert data is not None
