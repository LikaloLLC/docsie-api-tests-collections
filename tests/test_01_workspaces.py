"""
Test suite for the Workspaces API endpoints.

Covers listing, retrieving, filtering, and negative cases for workspace CRUD.
"""
import pytest

pytestmark = [pytest.mark.content]


# -- Positive tests ----------------------------------------------------------

class TestWorkspacesList:
    """Tests for GET /workspaces/."""

    def test_list_workspaces_returns_200(self, api):
        """List workspaces returns 200 with paginated response structure."""
        resp = api.get("/workspaces/")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "results" in data
        assert isinstance(data["results"], list)
        assert "count" in data
        assert isinstance(data["count"], int)

    def test_list_workspaces_contains_test_workspace(self, api, test_workspace_id):
        """The known test workspace appears in the workspace list."""
        resp = api.get("/workspaces/?limit=-1")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        results = body if isinstance(body, list) else body.get("results", [])
        ids = [ws["id"] for ws in results]
        assert test_workspace_id in ids

    def test_list_workspaces_result_structure(self, api):
        """Each workspace in the list has the expected top-level keys."""
        resp = api.get("/workspaces/")
        assert resp.status_code == 200, resp.text
        results = resp.json()["results"]
        assert len(results) > 0, "Expected at least one workspace"
        ws = results[0]
        for key in ("id", "name", "slug", "created", "modified"):
            assert key in ws, f"Missing key '{key}' in workspace object"


class TestWorkspacesRetrieve:
    """Tests for GET /workspaces/{id}/."""

    def test_retrieve_workspace_by_id(self, api, test_workspace_id):
        """Retrieve the test workspace by its known ID."""
        resp = api.get(f"/workspaces/{test_workspace_id}/")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["id"] == test_workspace_id
        assert "name" in data
        assert "slug" in data

    def test_retrieve_workspace_has_shelves_count(self, api, test_workspace_id):
        """Retrieved workspace includes the shelves_count field."""
        resp = api.get(f"/workspaces/{test_workspace_id}/")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "shelves_count" in data
        assert isinstance(data["shelves_count"], int)


class TestWorkspacesFilter:
    """Tests for filtering workspaces."""

    def test_filter_workspaces_by_name(self, api, test_workspace_id):
        """Filtering by name returns only matching workspaces."""
        detail = api.get(f"/workspaces/{test_workspace_id}/").json()
        ws_name = detail["name"]

        resp = api.get("/workspaces/", params={"name": ws_name})
        assert resp.status_code == 200, resp.text
        results = resp.json()["results"]
        assert len(results) >= 1
        assert any(ws["id"] == test_workspace_id for ws in results)


# -- Negative tests -----------------------------------------------------------

class TestWorkspacesNegative:
    """Negative / error-path tests for workspace endpoints."""

    @pytest.mark.negative
    def test_retrieve_nonexistent_workspace_returns_404(self, api):
        """Requesting a workspace that does not exist returns 404."""
        resp = api.get("/workspaces/workspace_DOES_NOT_EXIST_999/")
        assert resp.status_code == 404, resp.text

    @pytest.mark.negative
    def test_create_workspace_missing_name_returns_400(self, api):
        """Creating a workspace without the required 'name' field returns 400."""
        resp = api.post("/workspaces/", json={})
        assert resp.status_code == 400, resp.text
