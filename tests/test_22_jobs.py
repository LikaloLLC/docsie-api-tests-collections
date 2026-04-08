"""
Tests for the Jobs API endpoints.

Covers listing, retrieving, and filtering jobs, plus negative cases.
"""
import pytest

FAKE_JOB_ID = "job_00000000000000DOESNOTEXIST"


class TestListJobs:
    """GET /jobs/ — list jobs."""

    def test_list_jobs_returns_200(self, api):
        """Listing jobs returns 200 with a paginated response."""
        resp = api.get("/jobs/")
        assert resp.status_code == 200
        data = resp.json()
        assert "count" in data
        assert "results" in data
        assert isinstance(data["results"], list)


class TestRetrieveJob:
    """GET /jobs/{id}/ — retrieve a single job."""

    def test_retrieve_existing_job(self, api):
        """If jobs exist, retrieve the first one and verify key fields."""
        list_resp = api.get("/jobs/", params={"limit": 1})
        assert list_resp.status_code == 200
        jobs = list_resp.json().get("results", [])
        if not jobs:
            pytest.skip("No jobs available to retrieve")

        job_id = jobs[0]["id"]
        resp = api.get(f"/jobs/{job_id}/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == job_id
        for field in ("id", "job_name", "status"):
            assert field in data, f"Job response missing '{field}'"
        # result may be null for pending jobs but the key should exist
        assert "result" in data

    @pytest.mark.negative
    def test_retrieve_nonexistent_job(self, api):
        """Retrieving a non-existent job returns 404."""
        resp = api.get(f"/jobs/{FAKE_JOB_ID}/")
        assert resp.status_code == 404


class TestFilterJobs:
    """GET /jobs/?status=... — filter jobs by status."""

    def test_filter_jobs_by_status_done(self, api):
        """Filtering jobs by status=done returns only done jobs (or empty)."""
        resp = api.get("/jobs/", params={"status": "done"})
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        for job in data["results"]:
            assert job["status"] == "done", (
                f"Expected status 'done', got '{job['status']}'"
            )
