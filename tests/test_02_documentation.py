"""
Test suite for the Documentation Shelves API endpoints.

Covers listing, creating, retrieving, updating, filtering, and negative cases.
"""
import time

import pytest

pytestmark = [pytest.mark.content]

from conftest import TEST_WORKSPACE_ID

# Module-level state shared across ordered tests
_state = {}


# -- Positive tests ----------------------------------------------------------

class TestDocumentationList:
    """Tests for GET /documentation/."""

    def test_list_documentation_returns_200(self, api):
        """List documentation shelves returns 200 with paginated response."""
        resp = api.get("/documentation/")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "results" in data
        assert "count" in data
        assert isinstance(data["results"], list)


class TestDocumentationCreate:
    """Tests for POST /documentation/."""

    def test_create_documentation_shelf(self, api):
        """Create a new documentation shelf in the test workspace."""
        payload = {
            "name": f"API Test Shelf {int(time.time())}",
            "description": "Created by automated integration tests.",
            "workspace": TEST_WORKSPACE_ID,
        }
        resp = api.post("/documentation/", json=payload)
        assert resp.status_code == 201, resp.text
        body = resp.json()
        # Response wraps the shelf under a "document" key
        data = body.get("document", body)
        assert "id" in data, f"Missing 'id' in response: {list(body.keys())}"
        assert data["name"] == payload["name"]
        _state["documentation_id"] = data["id"]
        _state["documentation_name"] = data["name"]


class TestDocumentationRetrieve:
    """Tests for GET /documentation/{id}/."""

    def test_retrieve_created_shelf(self, api):
        """Retrieve the shelf created in the previous test."""
        doc_id = _state.get("documentation_id")
        if not doc_id:
            pytest.skip("No documentation was created in a prior test")

        resp = api.get(f"/documentation/{doc_id}/")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["id"] == doc_id
        assert data["name"] == _state["documentation_name"]
        for key in ("id", "name", "description", "created", "modified"):
            assert key in data, f"Missing key '{key}' in documentation object"


class TestDocumentationUpdate:
    """Tests for PATCH /documentation/{id}/."""

    def test_update_shelf_name(self, api):
        """Update the documentation shelf name via PATCH."""
        doc_id = _state.get("documentation_id")
        if not doc_id:
            pytest.skip("No documentation was created in a prior test")

        new_name = f"Updated Shelf {int(time.time())}"
        resp = api.patch(f"/documentation/{doc_id}/", json={"name": new_name})
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["name"] == new_name
        _state["documentation_name"] = new_name


class TestDocumentationFilter:
    """Tests for filtering documentation shelves."""

    def test_filter_documentation_by_workspace(self, api):
        """Filtering documentation by workspace returns only shelves in that workspace."""
        resp = api.get("/documentation/", params={"workspace": TEST_WORKSPACE_ID})
        assert resp.status_code == 200, resp.text
        results = resp.json()["results"]
        assert isinstance(results, list)
        # The shelf we created should appear in filtered results
        doc_id = _state.get("documentation_id")
        if doc_id:
            ids = [d["id"] for d in results]
            assert doc_id in ids, "Created shelf not found when filtering by workspace"


# -- Negative tests -----------------------------------------------------------

class TestDocumentationNegative:
    """Negative / error-path tests for documentation endpoints."""

    @pytest.mark.negative
    def test_create_shelf_without_name_returns_400(self, api):
        """Creating a shelf without the required 'name' field returns 400."""
        resp = api.post("/documentation/", json={
            "description": "No name provided",
            "workspace": TEST_WORKSPACE_ID,
        })
        assert resp.status_code == 400, resp.text

    @pytest.mark.negative
    def test_create_shelf_in_nonexistent_workspace(self, api):
        """Creating a shelf in a non-existent workspace returns 404 or 403."""
        resp = api.post("/documentation/", json={
            "name": "Should Fail",
            "description": "Workspace does not exist",
            "workspace": "workspace_DOES_NOT_EXIST_999",
        })
        assert resp.status_code in (403, 404), (
            f"Expected 403 or 404, got {resp.status_code}: {resp.text}"
        )
