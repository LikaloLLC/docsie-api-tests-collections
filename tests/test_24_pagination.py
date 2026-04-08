"""
Tests for pagination behaviour across list endpoints.

Verifies limit, offset, limit=-1 (return all), and offset-beyond-total edge
cases.
"""
import pytest


class TestWorkspacesPagination:
    """Pagination on GET /workspaces/."""

    def test_limit_one_returns_single_result(self, api):
        """Requesting limit=1 returns at most 1 item with pagination wrapper."""
        resp = api.get("/workspaces/", params={"limit": 1})
        assert resp.status_code == 200
        data = resp.json()
        assert "count" in data
        assert "results" in data
        assert len(data["results"]) <= 1
        if data["count"] > 1:
            assert data["next"] is not None, "next should be set when more items exist"

    def test_limit_minus_one_returns_all(self, api):
        """Requesting limit=-1 bypasses pagination and returns all results."""
        resp = api.get("/workspaces/", params={"limit": -1})
        assert resp.status_code == 200
        data = resp.json()
        # When limit=-1 the API may return a flat list or still wrap in pagination.
        # Accept either shape.
        if isinstance(data, list):
            # Flat list — all results returned directly
            assert len(data) >= 1
        else:
            # Pagination wrapper with all results in one page
            assert "results" in data
            assert len(data["results"]) == data.get("count", len(data["results"]))

    def test_offset_beyond_total_returns_empty(self, api):
        """Requesting an offset larger than total count returns empty results."""
        resp = api.get("/workspaces/", params={"limit": 10, "offset": 999999})
        assert resp.status_code == 200
        data = resp.json()
        assert data["results"] == []


class TestArticlesPagination:
    """Pagination on GET /articles/."""

    def test_limit_one_offset_zero(self, api):
        """Requesting limit=1&offset=0 returns at most 1 article."""
        resp = api.get("/articles/", params={"limit": 1, "offset": 0})
        assert resp.status_code == 200
        data = resp.json()
        assert "count" in data
        assert "results" in data
        assert len(data["results"]) <= 1

    def test_offset_beyond_total_returns_empty(self, api):
        """Offset past the total article count yields an empty results list."""
        resp = api.get("/articles/", params={"limit": 10, "offset": 999999})
        assert resp.status_code == 200
        data = resp.json()
        assert data["results"] == []
