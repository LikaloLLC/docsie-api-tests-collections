"""
Test suite for the Books API endpoints.

Covers listing, creating, retrieving, updating, filtering, and negative cases.
Depends on test_02_documentation having run first to populate _state.
"""
import time

import pytest

from tests.test_02_documentation import _state as doc_state

pytestmark = [pytest.mark.content]

# Module-level state shared across ordered tests
_state = {}


# -- Positive tests ----------------------------------------------------------

class TestBooksList:
    """Tests for GET /books/."""

    def test_list_books_returns_200(self, api):
        """List books returns 200 with paginated response structure."""
        resp = api.get("/books/")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "results" in data
        assert "count" in data
        assert isinstance(data["results"], list)


class TestBooksCreate:
    """Tests for POST /books/."""

    def test_create_book_in_shelf(self, api):
        """Create a new book inside the documentation shelf from test_02."""
        doc_id = doc_state.get("documentation_id")
        if not doc_id:
            pytest.skip("No documentation shelf was created in test_02")

        payload = {
            "name": f"API Test Book {int(time.time())}",
            "description": "Book created by automated integration tests.",
            "documentation": doc_id,
        }
        resp = api.post("/books/", json=payload)
        assert resp.status_code == 201, resp.text
        body = resp.json()
        # Response wraps the book under a "book" key
        data = body.get("book", body)
        assert "id" in data, f"Missing 'id' in response: {list(body.keys())}"
        assert data["name"] == payload["name"]
        _state["book_id"] = data["id"]
        _state["book_name"] = data["name"]
        # Also capture version/language IDs from the create response
        if "version" in data and isinstance(data["version"], dict):
            _state["version_id"] = data["version"]["id"]
        if "language" in data and isinstance(data["language"], dict):
            _state["language_id"] = data["language"]["id"]
        if "article" in data and isinstance(data["article"], dict):
            _state["article_id"] = data["article"]["id"]


class TestBooksRetrieve:
    """Tests for GET /books/{id}/."""

    def test_retrieve_created_book(self, api):
        """Retrieve the book created in the previous test."""
        book_id = _state.get("book_id")
        if not book_id:
            pytest.skip("No book was created in a prior test")

        resp = api.get(f"/books/{book_id}/")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["id"] == book_id
        assert data["name"] == _state["book_name"]
        for key in ("id", "name", "description", "created", "modified"):
            assert key in data, f"Missing key '{key}' in book object"

    def test_retrieve_book_with_expand_versions(self, api):
        """Retrieve a book with expand[]=versions includes versions data."""
        book_id = _state.get("book_id")
        if not book_id:
            pytest.skip("No book was created in a prior test")

        resp = api.get(f"/books/{book_id}/", params={"expand[]": "versions"})
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "versions" in data
        versions = data["versions"]
        # Expanded versions should have results list
        assert "results" in versions or isinstance(versions, list)


class TestBooksUpdate:
    """Tests for PATCH /books/{id}/."""

    def test_update_book_name(self, api):
        """Update the book name via PATCH."""
        book_id = _state.get("book_id")
        if not book_id:
            pytest.skip("No book was created in a prior test")

        new_name = f"Updated Book {int(time.time())}"
        resp = api.patch(f"/books/{book_id}/", json={"name": new_name})
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["name"] == new_name
        _state["book_name"] = new_name


class TestBooksFilter:
    """Tests for filtering books."""

    def test_filter_books_by_documentation(self, api):
        """Filtering books by documentation returns only books in that shelf."""
        doc_id = doc_state.get("documentation_id")
        if not doc_id:
            pytest.skip("No documentation shelf available")

        resp = api.get("/books/", params={"documentation": doc_id})
        assert resp.status_code == 200, resp.text
        results = resp.json()["results"]
        assert isinstance(results, list)
        book_id = _state.get("book_id")
        if book_id:
            ids = [b["id"] for b in results]
            assert book_id in ids, "Created book not found when filtering by documentation"


# -- Negative tests -----------------------------------------------------------

class TestBooksNegative:
    """Negative / error-path tests for book endpoints."""

    @pytest.mark.negative
    def test_create_book_without_documentation_returns_400(self, api):
        """Creating a book without the required 'documentation' field returns 400."""
        resp = api.post("/books/", json={
            "name": "Should Fail",
            "description": "Missing documentation field",
        })
        assert resp.status_code == 400, resp.text
