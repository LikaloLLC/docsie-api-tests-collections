"""
Negative authentication tests.

Verifies that requests without an API key or with an invalid key are rejected
with 401 or 403 across multiple endpoints.
"""
import pytest
import requests

pytestmark = pytest.mark.negative

BASE_URL = "https://staging.docsie.io/api_v2/003"

ENDPOINTS = [
    ("GET", "/workspaces/"),
    ("GET", "/articles/"),
    ("GET", "/credits/balance/"),
    ("GET", "/files/"),
    ("GET", "/video-to-docs/"),
]


def _make_session(api_key=None):
    """Create a plain requests session with optional (bad) API key."""
    s = requests.Session()
    s.headers.update({
        "Content-Type": "application/json",
        "Accept": "application/json",
    })
    if api_key:
        s.headers["Authorization"] = f"Api-Key {api_key}"
    return s


class TestNoApiKey:
    """Requests without any API key should be rejected."""

    @pytest.mark.parametrize("method,path", ENDPOINTS, ids=[p for _, p in ENDPOINTS])
    def test_no_key_returns_401_or_403(self, method, path):
        """Endpoint {path} rejects requests that have no API key."""
        session = _make_session()
        resp = session.request(method, f"{BASE_URL}{path}")
        assert resp.status_code in (401, 403), (
            f"{method} {path} returned {resp.status_code}, expected 401 or 403"
        )
        # Response should be valid JSON with some kind of error indicator
        data = resp.json()
        assert isinstance(data, dict)


class TestInvalidApiKey:
    """Requests with an invalid API key should be rejected."""

    @pytest.mark.parametrize("method,path", ENDPOINTS, ids=[p for _, p in ENDPOINTS])
    def test_bad_key_returns_401_or_403(self, method, path):
        """Endpoint {path} rejects requests with a bogus API key."""
        session = _make_session(api_key="INVALID_KEY_000000000000")
        resp = session.request(method, f"{BASE_URL}{path}")
        assert resp.status_code in (401, 403), (
            f"{method} {path} returned {resp.status_code}, expected 401 or 403"
        )
        data = resp.json()
        assert isinstance(data, dict)
