"""
Tests for the video-to-docs cost estimation endpoint.

POST /video-to-docs/estimate/ returns credit cost projections for a given
quality tier and optional video duration.
"""
import pytest

pytestmark = [pytest.mark.video]


class TestVideoEstimateBasic:
    """Happy-path estimation requests."""

    def test_estimate_standard_10min(self, api):
        """Standard quality, 10-minute video returns a valid estimate."""
        resp = api.post("/video-to-docs/estimate/", json={
            "quality": "standard",
            "duration_minutes": 10,
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()

        # Required fields per schema
        for field in ("quality", "seconds_per_frame", "credits_per_minute",
                      "video_quality_tiers", "balance"):
            assert field in data, f"Missing required field: {field}"

        assert data["quality"] == "standard"
        assert data["credits_per_minute"] > 0

        # With duration provided, estimate and has_sufficient_credits should appear
        assert "estimate" in data, "estimate should be present when duration given"
        assert "has_sufficient_credits" in data

    def test_estimate_draft_cheaper_than_standard(self, api):
        """Draft tier costs fewer credits per minute than standard."""
        draft = api.post("/video-to-docs/estimate/", json={
            "quality": "draft", "duration_minutes": 10,
        }).json()
        standard = api.post("/video-to-docs/estimate/", json={
            "quality": "standard", "duration_minutes": 10,
        }).json()

        assert draft["credits_per_minute"] < standard["credits_per_minute"], (
            f"Draft ({draft['credits_per_minute']}) should be cheaper than "
            f"standard ({standard['credits_per_minute']})"
        )

    def test_estimate_ultra_most_expensive(self, api):
        """Ultra tier is more expensive than all other tiers."""
        ultra = api.post("/video-to-docs/estimate/", json={
            "quality": "ultra", "duration_minutes": 10,
        }).json()
        detailed = api.post("/video-to-docs/estimate/", json={
            "quality": "detailed", "duration_minutes": 10,
        }).json()

        assert ultra["credits_per_minute"] > detailed["credits_per_minute"], (
            f"Ultra ({ultra['credits_per_minute']}) should be more expensive than "
            f"detailed ({detailed['credits_per_minute']})"
        )

    def test_estimate_without_duration_returns_tiers(self, api):
        """When no duration is provided, tiers are returned but no estimate."""
        resp = api.post("/video-to-docs/estimate/", json={
            "quality": "standard",
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()

        assert "video_quality_tiers" in data
        assert "credits_per_minute" in data
        # Without duration, estimate/has_sufficient_credits may be absent or null
        if "estimate" in data:
            assert data["estimate"] is None or data["estimate"] == 0 or isinstance(data["estimate"], dict)

    def test_estimate_duration_seconds_converted(self, api):
        """duration_seconds=300 should be treated as 5 minutes."""
        resp = api.post("/video-to-docs/estimate/", json={
            "quality": "standard",
            "duration_seconds": 300,
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()

        if "duration_minutes" in data and data["duration_minutes"] is not None:
            assert data["duration_minutes"] == 5, (
                f"Expected 5 minutes for 300 seconds, got {data['duration_minutes']}"
            )


class TestVideoEstimateCreditsCheck:
    """Verify has_sufficient_credits matches balance vs estimate."""

    def test_sufficient_credits_flag_matches_balance(self, api):
        """has_sufficient_credits should be True when balance >= estimate."""
        resp = api.post("/video-to-docs/estimate/", json={
            "quality": "draft",
            "duration_minutes": 1,
        })
        data = resp.json()

        if "has_sufficient_credits" not in data or "estimate" not in data:
            pytest.skip("Response does not include both has_sufficient_credits and estimate")

        balance = data.get("balance", {})
        total = balance.get("total_available", 0) if isinstance(balance, dict) else 0
        estimate_val = data["estimate"]
        if isinstance(estimate_val, dict):
            estimate_val = estimate_val.get("total", estimate_val.get("credits", 0))

        if total >= estimate_val:
            assert data["has_sufficient_credits"] is True
        else:
            assert data["has_sufficient_credits"] is False


class TestVideoEstimateNegative:
    """Negative / error cases for the estimate endpoint."""

    @pytest.mark.negative
    def test_estimate_invalid_quality_returns_400(self, api):
        """An unrecognized quality value returns 400."""
        resp = api.post("/video-to-docs/estimate/", json={
            "quality": "super_mega_ultra",
            "duration_minutes": 10,
        })
        assert resp.status_code == 400, (
            f"Expected 400 for invalid quality, got {resp.status_code}: {resp.text}"
        )
