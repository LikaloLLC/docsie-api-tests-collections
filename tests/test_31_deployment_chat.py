"""
End-to-end tests for the Deployment Chat API.

Tests sync responses, SSE streaming, multi-turn conversations,
credit deduction, and negative cases against a real deployment.
"""
import json

import pytest
import requests as raw_requests

pytestmark = [pytest.mark.deployments]

DEPLOYMENT_ID = "deployment_O7xRN1WOOUoCrtoER"

_state: dict = {}


class TestDeploymentChatSync:
    """POST /deployments/{id}/chat/ — synchronous JSON response."""

    def test_sync_chat_returns_200(self, api):
        """Ask a question and get a sync JSON response."""
        resp = api.post(f"/deployments/{DEPLOYMENT_ID}/chat/", json={
            "question": "What is this documentation about?",
            "stream": False,
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"
        data = resp.json()
        _state["sync_response"] = data

    def test_sync_response_has_answer(self):
        """Response contains a non-empty answer string."""
        data = _state.get("sync_response")
        if not data:
            pytest.skip("No sync response")
        assert "answer" in data
        assert isinstance(data["answer"], str)
        assert len(data["answer"]) > 20, f"Answer too short: {len(data['answer'])} chars"

    def test_sync_response_has_sources(self):
        """Response contains sources array with article references."""
        data = _state.get("sync_response")
        if not data:
            pytest.skip("No sync response")
        assert "sources" in data
        assert isinstance(data["sources"], list)
        assert len(data["sources"]) > 0, "Expected at least one source"
        src = data["sources"][0]
        assert "title" in src, f"Source missing 'title': {src.keys()}"

    def test_sync_response_has_conversation_id(self):
        """Response includes a conversation_id for follow-up turns."""
        data = _state.get("sync_response")
        if not data:
            pytest.skip("No sync response")
        assert "conversation_id" in data
        assert data["conversation_id"], "conversation_id should not be empty"
        _state["conversation_id"] = data["conversation_id"]

    def test_sync_response_has_model(self):
        """Response includes the model name used for generation."""
        data = _state.get("sync_response")
        if not data:
            pytest.skip("No sync response")
        assert "model" in data
        assert data["model"], "model should not be empty"


class TestDeploymentChatStreaming:
    """POST /deployments/{id}/chat/ with stream=true — SSE response."""

    def test_streaming_returns_event_stream(self, api):
        """Streaming response has content-type text/event-stream."""
        # Use raw requests for streaming (api fixture auto-retries which breaks streaming)
        from conftest import API_PREFIX, API_KEY
        headers = {
            "Authorization": f"Api-Key {API_KEY}",
            "Content-Type": "application/json",
        }
        resp = raw_requests.post(
            f"{API_PREFIX}/deployments/{DEPLOYMENT_ID}/chat/",
            headers=headers,
            json={"question": "How do I get started?", "stream": True},
            stream=True,
            timeout=60,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        assert "text/event-stream" in resp.headers.get("Content-Type", "")
        _state["stream_response"] = resp

    def test_streaming_has_sources_event(self):
        """First SSE event should be a sources event."""
        resp = _state.get("stream_response")
        if not resp:
            pytest.skip("No stream response")

        events = []
        for line in resp.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data: "):
                continue
            payload = json.loads(line[6:])
            events.append(payload)
            if payload.get("type") == "done":
                break
        _state["stream_events"] = events

        assert len(events) > 0, "No SSE events received"
        assert events[0]["type"] == "sources", f"First event should be 'sources', got {events[0]['type']}"
        assert isinstance(events[0].get("sources"), list)

    def test_streaming_has_content_events(self):
        """Stream should contain multiple content chunks."""
        events = _state.get("stream_events", [])
        if not events:
            pytest.skip("No stream events")

        content_events = [e for e in events if e.get("type") == "content"]
        assert len(content_events) > 1, f"Expected multiple content events, got {len(content_events)}"
        # Each content event should have a non-empty content string
        for ce in content_events:
            assert "content" in ce
            assert isinstance(ce["content"], str)

    def test_streaming_ends_with_done(self):
        """Stream should end with a done event containing conversation_id."""
        events = _state.get("stream_events", [])
        if not events:
            pytest.skip("No stream events")

        done_events = [e for e in events if e.get("type") == "done"]
        assert len(done_events) == 1, f"Expected exactly one done event, got {len(done_events)}"
        assert "conversation_id" in done_events[0]
        assert done_events[0]["conversation_id"], "conversation_id should not be empty"

    def test_streaming_full_answer_is_coherent(self):
        """Concatenated content chunks form a coherent answer."""
        events = _state.get("stream_events", [])
        if not events:
            pytest.skip("No stream events")

        full_answer = "".join(e["content"] for e in events if e.get("type") == "content")
        assert len(full_answer) > 50, f"Concatenated answer too short: {len(full_answer)} chars"


class TestDeploymentChatMultiTurn:
    """Multi-turn conversation via conversation_id."""

    def test_follow_up_uses_same_conversation(self, api):
        """Passing conversation_id from turn 1 continues the same conversation."""
        conv_id = _state.get("conversation_id")
        if not conv_id:
            pytest.skip("No conversation_id from prior test")

        resp = api.post(f"/deployments/{DEPLOYMENT_ID}/chat/", json={
            "question": "Can you give me more details on that?",
            "stream": False,
            "conversation_id": conv_id,
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"
        data = resp.json()
        assert data.get("conversation_id") == conv_id, "Should return the same conversation_id"
        assert len(data.get("answer", "")) > 20, "Follow-up answer should be non-trivial"


class TestDeploymentChatNegative:
    """Negative / error-path tests."""

    @pytest.mark.negative
    def test_missing_question_returns_400(self, api):
        """Sending no question returns 400."""
        resp = api.post(f"/deployments/{DEPLOYMENT_ID}/chat/", json={
            "stream": False,
        })
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text[:300]}"

    @pytest.mark.negative
    def test_empty_question_returns_400(self, api):
        """Sending an empty question returns 400."""
        resp = api.post(f"/deployments/{DEPLOYMENT_ID}/chat/", json={
            "question": "",
            "stream": False,
        })
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text[:300]}"

    @pytest.mark.negative
    def test_question_too_long_returns_400(self, api):
        """Sending a question > 500 chars returns 400."""
        resp = api.post(f"/deployments/{DEPLOYMENT_ID}/chat/", json={
            "question": "x" * 501,
            "stream": False,
        })
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text[:300]}"

    @pytest.mark.negative
    def test_nonexistent_deployment_returns_404(self, api):
        """Chatting with a non-existent deployment returns 404."""
        resp = api.post("/deployments/deployment_DOES_NOT_EXIST_999/chat/", json={
            "question": "Hello",
            "stream": False,
        })
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text[:300]}"

    @pytest.mark.negative
    def test_no_auth_returns_401_or_403(self):
        """Calling without API key returns 401 or 403."""
        from conftest import API_PREFIX
        resp = raw_requests.post(
            f"{API_PREFIX}/deployments/{DEPLOYMENT_ID}/chat/",
            json={"question": "Hello", "stream": False},
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"


class TestDeploymentChatCredits:
    """Verify credit deduction after chat usage."""

    def test_usage_contains_portal_chat_deduction(self, api):
        """Credit usage history should contain portal chat transactions from our tests."""
        resp = api.get("/credits/usage/", params={"transaction_type": "deduct_portal_chat"})
        assert resp.status_code == 200, resp.text
        data = resp.json()
        results = data.get("results", data if isinstance(data, list) else [])
        assert len(results) > 0, "Expected at least one deduct_portal_chat transaction"
        latest = results[0]
        assert latest["transaction_type"] == "deduct_portal_chat"
        assert latest["amount"] < 0, "Chat deduction should be negative"
