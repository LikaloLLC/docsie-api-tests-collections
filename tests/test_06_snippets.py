"""
Test suite for the Snippets API endpoints.

Covers listing, creating, retrieving, updating, deleting snippets and negative cases.
Depends on test_02_documentation and test_05_articles for documentation/article IDs.
"""
import pytest

from tests.test_02_documentation import _state as doc_state
from tests.test_05_articles import _state as article_state

pytestmark = [pytest.mark.content]

TEST_WORKSPACE_ID = "workspace_lWoSrrFMPMOgP2og5"

# Module-level state shared across ordered tests
_state = {}


def _get_article_id(api):
    """Return an article ID from prior tests, or find one from the API."""
    article_id = article_state.get("created_article_id") or article_state.get("default_article_id")
    if article_id:
        return article_id
    # Fallback: fetch any article from the API
    resp = api.get("/articles/", params={"limit": 1})
    if resp.status_code == 200:
        results = resp.json().get("results", [])
        if results:
            return results[0]["id"]
    return None


def _get_documentation_id(api):
    """Return a documentation ID from prior tests, or find one from the API."""
    doc_id = doc_state.get("documentation_id")
    if doc_id:
        return doc_id
    resp = api.get("/documentation/", params={"limit": 1})
    if resp.status_code == 200:
        results = resp.json().get("results", [])
        if results:
            return results[0]["id"]
    return None


# -- Positive tests ----------------------------------------------------------

class TestSnippetsList:
    """Tests for GET /snippets/."""

    def test_list_snippets_returns_200(self, api):
        """List snippets returns 200 with paginated response structure."""
        resp = api.get("/snippets/")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "results" in data
        assert "count" in data
        assert isinstance(data["results"], list)


class TestSnippetsCreate:
    """Tests for POST /snippets/."""

    def test_create_snippet(self, api):
        """Create a new snippet attached to an article."""
        article_id = _get_article_id(api)
        doc_id = _get_documentation_id(api)
        if not article_id or not doc_id:
            pytest.skip("No article or documentation ID available")

        payload = {
            "article": article_id,
            "documentation": doc_id,
            "workspace": TEST_WORKSPACE_ID,
            "type": "callout",
            "tags": ["api-test", "integration"],
            "used_in": [article_id],
            "blocks": [
                {
                    "type": "paragraph",
                    "children": [
                        {"text": "This is a test snippet created by the integration test suite."}
                    ],
                }
            ],
        }
        resp = api.post("/snippets/", json=payload)
        # Schema says 204 for create, but could also be 200 or 201
        assert resp.status_code in (200, 201, 204), resp.text
        data = resp.json()
        assert "id" in data
        _state["snippet_id"] = data["id"]


class TestSnippetsRetrieve:
    """Tests for GET /snippets/{id}/."""

    def test_retrieve_created_snippet(self, api):
        """Retrieve the snippet created in the previous test."""
        snippet_id = _state.get("snippet_id")
        if not snippet_id:
            pytest.skip("No snippet was created in a prior test")

        resp = api.get(f"/snippets/{snippet_id}/")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["id"] == snippet_id
        for key in ("id", "article", "documentation", "workspace"):
            assert key in data, f"Missing key '{key}' in snippet object"


class TestSnippetsUpdate:
    """Tests for PATCH /snippets/{id}/."""

    def test_update_snippet_tags(self, api):
        """Update snippet tags via PATCH."""
        snippet_id = _state.get("snippet_id")
        if not snippet_id:
            pytest.skip("No snippet was created in a prior test")

        new_tags = ["api-test", "updated"]
        resp = api.patch(f"/snippets/{snippet_id}/", json={"tags": new_tags})
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["tags"] == new_tags

    def test_update_snippet_blocks(self, api):
        """Update snippet block content via PATCH."""
        snippet_id = _state.get("snippet_id")
        if not snippet_id:
            pytest.skip("No snippet was created in a prior test")

        new_blocks = [
            {
                "type": "paragraph",
                "children": [
                    {"text": "Updated snippet content from the integration test suite."}
                ],
            }
        ]
        resp = api.patch(f"/snippets/{snippet_id}/", json={"blocks": new_blocks})
        assert resp.status_code == 200, resp.text


class TestSnippetsDelete:
    """Tests for DELETE /snippets/{id}/."""

    def test_delete_snippet(self, api):
        """Delete the previously created snippet."""
        snippet_id = _state.get("snippet_id")
        if not snippet_id:
            pytest.skip("No snippet was created in a prior test")

        resp = api.delete(f"/snippets/{snippet_id}/")
        # Schema says 200 for delete
        assert resp.status_code in (200, 204), resp.text
        _state["deleted_snippet_id"] = snippet_id


# -- Negative tests -----------------------------------------------------------

class TestSnippetsNegative:
    """Negative / error-path tests for snippet endpoints."""

    @pytest.mark.negative
    def test_retrieve_deleted_snippet_returns_404(self, api):
        """Retrieving a deleted snippet returns 404."""
        snippet_id = _state.get("deleted_snippet_id")
        if not snippet_id:
            pytest.skip("No snippet was deleted in a prior test")

        resp = api.get(f"/snippets/{snippet_id}/")
        assert resp.status_code == 404, (
            f"Expected 404 for deleted snippet, got {resp.status_code}: {resp.text}"
        )

    @pytest.mark.negative
    def test_retrieve_nonexistent_snippet_returns_404(self, api):
        """Requesting a snippet that never existed returns 404."""
        resp = api.get("/snippets/snippet_DOES_NOT_EXIST_999/")
        assert resp.status_code == 404, resp.text
