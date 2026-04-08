"""
Test suite for the Articles API endpoints.

Covers listing, retrieving, creating, updating articles and negative cases.
Depends on test_03_books and test_04_versions_languages for book/language IDs.
"""
import time

import pytest

from tests.test_03_books import _state as book_state
from tests.test_04_versions_languages import _state as version_state

pytestmark = [pytest.mark.content]

# Module-level state shared across ordered tests
_state = {}


# -- Positive tests ----------------------------------------------------------

class TestArticlesList:
    """Tests for GET /articles/."""

    def test_list_articles_returns_200(self, api):
        """List articles returns 200 with paginated response structure."""
        resp = api.get("/articles/")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "results" in data
        assert "count" in data
        assert isinstance(data["results"], list)

    def test_list_articles_filtered_by_book(self, api):
        """Filtering articles by book returns articles in that book."""
        book_id = book_state.get("book_id")
        if not book_id:
            pytest.skip("No book was created in test_03")

        resp = api.get("/articles/", params={"book": book_id})
        assert resp.status_code == 200, resp.text
        results = resp.json()["results"]
        assert isinstance(results, list)
        # A newly created book should have at least one default article
        if len(results) >= 1:
            _state["default_article_id"] = results[0]["id"]


class TestArticlesRetrieve:
    """Tests for GET /articles/{id}/."""

    def test_retrieve_default_article(self, api):
        """Retrieve the default article created with the book."""
        article_id = _state.get("default_article_id")
        if not article_id:
            pytest.skip("No default article ID available from prior tests")

        resp = api.get(f"/articles/{article_id}/")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["id"] == article_id
        for key in ("id", "name", "description"):
            assert key in data, f"Missing key '{key}' in article object"


class TestArticlesCreate:
    """Tests for POST /articles/."""

    @pytest.mark.xfail(reason="API bug: article_save returns dict, view calls .pk on it")
    def test_create_article_with_content_blocks(self, api):
        """Create a new article with structured doc content blocks."""
        language_id = version_state.get("default_language_id")
        book_id = book_state.get("book_id")
        version_id = version_state.get("version_id")

        if not language_id:
            pytest.skip("No language ID available from prior tests")

        payload = {
            "name": f"Test Article {int(time.time())}",
            "description": "Article created by automated integration tests.",
            "doc": {
                "type": "doc",
                "content": [
                    {
                        "type": "heading",
                        "attrs": {"level": 2},
                        "content": [
                            {"type": "text", "text": "Test Heading"}
                        ],
                    },
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "type": "text",
                                "text": "This is a test paragraph created via the Partner API.",
                            }
                        ],
                    },
                ],
            },
            "language": language_id,
        }
        if book_id:
            payload["book"] = book_id
        if version_id:
            payload["version"] = version_id

        resp = api.post("/articles/", json=payload)
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert "id" in data
        assert data["name"] == payload["name"]
        _state["created_article_id"] = data["id"]
        _state["created_article_name"] = data["name"]


class TestArticlesUpdate:
    """Tests for PATCH /articles/{id}/."""

    def test_update_article_content(self, api):
        """Update article content via PATCH."""
        article_id = _state.get("created_article_id")
        if not article_id:
            pytest.skip("No article was created in a prior test")

        updated_doc = {
            "type": "doc",
            "content": [
                {
                    "type": "heading",
                    "attrs": {"level": 2},
                    "content": [
                        {"type": "text", "text": "Updated Heading"}
                    ],
                },
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "type": "text",
                            "text": "This content was updated by the integration test suite.",
                        }
                    ],
                },
            ],
        }
        resp = api.patch(f"/articles/{article_id}/", json={"doc": updated_doc})
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["id"] == article_id

    def test_update_article_name(self, api):
        """Update article name via PATCH."""
        article_id = _state.get("created_article_id")
        if not article_id:
            pytest.skip("No article was created in a prior test")

        new_name = f"Renamed Article {int(time.time())}"
        resp = api.patch(f"/articles/{article_id}/", json={"name": new_name})
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["name"] == new_name


# -- Negative tests -----------------------------------------------------------

class TestArticlesNegative:
    """Negative / error-path tests for article endpoints."""

    @pytest.mark.negative
    def test_create_article_without_language_returns_400(self, api):
        """Creating an article without a language reference returns 400."""
        resp = api.post("/articles/", json={
            "name": "Should Fail",
            "description": "No language specified.",
        })
        assert resp.status_code == 400, resp.text

    @pytest.mark.negative
    def test_retrieve_nonexistent_article_returns_404(self, api):
        """Requesting an article that does not exist returns 404."""
        resp = api.get("/articles/article_DOES_NOT_EXIST_999/")
        assert resp.status_code == 404, resp.text
