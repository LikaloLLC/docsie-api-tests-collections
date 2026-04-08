"""
Test suite for the Versions and Languages API endpoints.

Covers listing, retrieving, filtering versions and creating languages.
Depends on test_03_books having run first to populate book state.
"""
import pytest

from tests.test_03_books import _state as book_state

pytestmark = [pytest.mark.content]

# Module-level state shared across ordered tests
_state = {}


# -- Version tests -----------------------------------------------------------

class TestVersionsList:
    """Tests for GET /versions/."""

    def test_list_versions_returns_200(self, api):
        """List versions returns 200 with paginated response structure."""
        resp = api.get("/versions/")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "results" in data
        assert "count" in data
        assert isinstance(data["results"], list)

    def test_list_versions_filtered_by_book(self, api):
        """Filtering versions by book returns versions belonging to that book."""
        book_id = book_state.get("book_id")
        if not book_id:
            pytest.skip("No book was created in test_03")

        resp = api.get("/versions/", params={"book": book_id})
        assert resp.status_code == 200, resp.text
        results = resp.json()["results"]
        assert isinstance(results, list)
        # A newly created book should have at least one default version
        assert len(results) >= 1, "Expected at least one default version for the new book"
        _state["version_id"] = results[0]["id"]


class TestVersionsRetrieve:
    """Tests for GET /versions/{id}/."""

    def test_retrieve_default_version(self, api):
        """Retrieve the default version created with the book."""
        version_id = _state.get("version_id")
        if not version_id:
            pytest.skip("No version ID available from prior tests")

        resp = api.get(f"/versions/{version_id}/")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["id"] == version_id
        for key in ("id", "created", "modified"):
            assert key in data, f"Missing key '{key}' in version object"

    def test_version_has_expected_fields(self, api):
        """The version object includes active_languages_count."""
        version_id = _state.get("version_id")
        if not version_id:
            pytest.skip("No version ID available from prior tests")

        resp = api.get(f"/versions/{version_id}/")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "active_languages_count" in data
        assert isinstance(data["active_languages_count"], int)


# -- Language tests ----------------------------------------------------------

class TestLanguagesList:
    """Tests for GET /languages/."""

    def test_list_languages_returns_200(self, api):
        """List languages returns 200 with paginated response structure."""
        resp = api.get("/languages/")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "results" in data
        assert "count" in data

    def test_list_languages_filtered_by_version(self, api):
        """Filtering languages by version returns languages for that version."""
        version_id = _state.get("version_id")
        if not version_id:
            pytest.skip("No version ID available from prior tests")

        resp = api.get("/languages/", params={"version": version_id})
        assert resp.status_code == 200, resp.text
        results = resp.json()["results"]
        assert isinstance(results, list)
        # Default version should have at least one default language (en)
        assert len(results) >= 1, "Expected at least one default language"
        _state["default_language_id"] = results[0]["id"]


class TestLanguagesCreate:
    """Tests for POST /languages/."""

    @pytest.mark.xfail(reason="API bug: language_save returns dict, view calls .pk on it")
    def test_create_french_language(self, api):
        """Create a new French language variant on the default version."""
        version_id = _state.get("version_id")
        if not version_id:
            pytest.skip("No version ID available from prior tests")

        book_id = book_state.get("book_id")
        payload = {
            "language": "French",
            "abbreviation": "fr",
            "version": version_id,
        }
        if book_id:
            payload["book"] = book_id

        resp = api.post("/languages/", json=payload)
        assert resp.status_code in (200, 201), resp.text
        data = resp.json()
        assert "id" in data
        _state["fr_language_id"] = data["id"]

    @pytest.mark.negative
    def test_create_duplicate_language_fails(self, api):
        """Creating the same language again on the same version should fail."""
        version_id = _state.get("version_id")
        if not version_id:
            pytest.skip("No version ID available from prior tests")

        book_id = book_state.get("book_id")
        payload = {
            "language": "French",
            "abbreviation": "fr",
            "version": version_id,
        }
        if book_id:
            payload["book"] = book_id

        resp = api.post("/languages/", json=payload)
        # Should return an error — 400 or 409
        assert resp.status_code in (400, 409), (
            f"Expected 400 or 409 for duplicate language, got {resp.status_code}: {resp.text}"
        )
