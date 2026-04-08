"""
Tests for the Deployments API endpoints.

Covers listing, retrieving, and refreshing deployments, plus negative cases.
"""
import pytest

pytestmark = pytest.mark.deployments

FAKE_DEPLOYMENT_ID = "deployment_00000000DOESNOTEXIST"


class TestListDeployments:
    """GET /deployments/ — list deployments."""

    def test_list_deployments_returns_200(self, api):
        """Listing deployments returns 200 with a paginated response."""
        resp = api.get("/deployments/")
        assert resp.status_code == 200
        data = resp.json()
        assert "count" in data
        assert "results" in data
        assert isinstance(data["results"], list)


class TestRetrieveDeployment:
    """GET /deployments/{id}/ — retrieve a single deployment."""

    def test_retrieve_existing_deployment(self, api):
        """If deployments exist, retrieve the first one by ID."""
        list_resp = api.get("/deployments/", params={"limit": 1})
        assert list_resp.status_code == 200
        deployments = list_resp.json().get("results", [])
        if not deployments:
            pytest.skip("No deployments available to retrieve")

        dep_id = deployments[0]["id"]
        resp = api.get(f"/deployments/{dep_id}/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == dep_id

    @pytest.mark.negative
    def test_retrieve_nonexistent_deployment(self, api):
        """Retrieving a non-existent deployment returns 404."""
        resp = api.get(f"/deployments/{FAKE_DEPLOYMENT_ID}/")
        assert resp.status_code == 404


class TestRefreshDeployment:
    """POST /deployments/{id}/refresh/ — refresh a deployment."""

    @pytest.mark.negative
    def test_refresh_nonexistent_deployment(self, api):
        """Refreshing a non-existent deployment returns 404."""
        resp = api.post(f"/deployments/{FAKE_DEPLOYMENT_ID}/refresh/", json={})
        assert resp.status_code == 404
