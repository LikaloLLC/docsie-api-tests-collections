"""
Tests for the AI Credits endpoints.

Verifies balance retrieval and usage history listing, including filtering.
"""
import pytest

pytestmark = [pytest.mark.credits]


class TestCreditsBalance:
    """GET /credits/balance/ — AI credit balance for the authenticated org."""

    def test_balance_returns_200(self, api):
        """Balance endpoint returns 200 with expected top-level fields."""
        resp = api.get("/credits/balance/")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_balance_has_required_fields(self, api):
        """Response contains all required CreditBalance fields from the schema."""
        resp = api.get("/credits/balance/")
        data = resp.json()

        required_fields = [
            "monthly_allocated",
            "monthly_remaining",
            "monthly_used",
            "purchased_balance",
            "total_available",
            "monthly_resets_at",
            "billing_mode",
            "video_quality_tiers",
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

    def test_balance_numeric_fields_are_integers(self, api):
        """Numeric credit fields are integers (or at least numeric)."""
        resp = api.get("/credits/balance/")
        data = resp.json()

        for field in ("monthly_allocated", "monthly_remaining", "monthly_used",
                      "purchased_balance", "total_available"):
            assert isinstance(data[field], int), (
                f"{field} should be int, got {type(data[field]).__name__}"
            )

    def test_balance_total_available_is_consistent(self, api):
        """total_available should equal monthly_remaining + purchased_balance."""
        data = api.get("/credits/balance/").json()
        expected = data["monthly_remaining"] + data["purchased_balance"]
        assert data["total_available"] == expected, (
            f"total_available={data['total_available']} != "
            f"monthly_remaining({data['monthly_remaining']}) + purchased_balance({data['purchased_balance']})"
        )

    def test_balance_video_quality_tiers_present(self, api):
        """video_quality_tiers is present and contains tier information."""
        data = api.get("/credits/balance/").json()
        tiers = data["video_quality_tiers"]
        assert tiers is not None, "video_quality_tiers should not be None"
        # Tiers should be a dict or list with quality tier info
        assert isinstance(tiers, (dict, list)), (
            f"video_quality_tiers should be dict or list, got {type(tiers).__name__}"
        )


class TestCreditsUsage:
    """GET /credits/usage/ — paginated AI credit transaction history."""

    def test_usage_returns_200(self, api):
        """Usage endpoint returns 200."""
        resp = api.get("/credits/usage/")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_usage_is_paginated(self, api):
        """Response has standard pagination fields: count and results."""
        data = api.get("/credits/usage/").json()
        assert "count" in data, "Missing 'count' in paginated response"
        assert "results" in data, "Missing 'results' in paginated response"
        assert isinstance(data["results"], list), "results should be a list"

    def test_usage_items_have_required_fields(self, api):
        """Each usage item has the required CreditUsageItem fields."""
        data = api.get("/credits/usage/", params={"limit": 5}).json()
        if not data["results"]:
            pytest.skip("No usage records available to validate item structure")

        required = [
            "id", "amount", "transaction_type", "credit_source",
            "balance_after_total", "created_at",
        ]
        item = data["results"][0]
        for field in required:
            assert field in item, f"Missing field '{field}' in usage item"

    def test_usage_filter_by_transaction_type(self, api):
        """Filtering by transaction_type=deduct_video returns 200."""
        resp = api.get("/credits/usage/", params={"transaction_type": "deduct_video"})
        assert resp.status_code == 200, (
            f"Expected 200 for transaction_type filter, got {resp.status_code}"
        )
        data = resp.json()
        assert "results" in data

    @pytest.mark.negative
    def test_usage_invalid_transaction_type_returns_200_empty(self, api):
        """An unrecognized transaction_type filter still returns 200 with empty or full results."""
        resp = api.get(
            "/credits/usage/",
            params={"transaction_type": "nonexistent_type_xyz"},
        )
        assert resp.status_code == 200, (
            f"Expected 200 for invalid transaction_type, got {resp.status_code}"
        )
        data = resp.json()
        assert "results" in data
