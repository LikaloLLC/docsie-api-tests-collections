# Docsie Partner API Test Suite

## Overview

This is an integration test suite for the Docsie Partner API. Tests run against a live Docsie instance using pytest + requests. The suite covers the full API surface: content CRUD, video-to-docs pipeline, AI chat, credits, files, deployments, and auth.

## How to Run

```bash
cd external/docsie-api-test-suite
pip install -r requirements.txt
pytest tests/ -m "not slow"           # fast tests (~2 min)
pytest tests/                          # everything (~15 min)
pytest tests/test_31_deployment_chat.py -v  # just chat tests
```

## Configuration

Tests read from `.env` in this directory:
- `DOCSIE_API_KEY` — required, the `Api-Key` header value
- `DOCSIE_BASE_URL` — defaults to `https://staging.docsie.io`
- `TEST_WORKSPACE_ID` — optional, auto-detected from API key's org if not set

## Architecture

- `conftest.py` — `DocsieClient` class with auto-retry on 429, `api` fixture, `test_workspace_id` fixture
- `tests/test_01-06` — Content hierarchy CRUD (workspaces → shelves → books → versions → languages → articles → snippets)
- `tests/test_10-15` — Credits + Video-to-docs pipeline (estimate, submit, poll, result, cancel, generate)
- `tests/test_20-25` — Files, deployments, jobs, auth negative, pagination, smoke
- `tests/test_30` — Full video E2E (upload → submit → Dokuta analysis → validate result → AI rewrite)
- `tests/test_31` — Deployment chat (sync, SSE streaming, multi-turn, negative)
- `assets/test_video.mp4` — 17MB test video for E2E tests

## Key Patterns

- **Cross-test state:** Module-level `_state = {}` dicts share IDs between ordered tests. Import from prior modules: `from tests.test_02_documentation import _state as doc_state`
- **API responses:** Some create endpoints wrap results (e.g., `{"document": {...}}` instead of `{...}`). Tests handle this via `body.get("document", body)`.
- **Rate limiting:** `DocsieClient._request()` auto-retries up to 3 times on 429 with Retry-After header.
- **xfail markers:** Known API bugs are marked `@pytest.mark.xfail(reason="...")` so the suite stays green.

## Adding Tests

1. Create `tests/test_XX_name.py`
2. Use `pytestmark = [pytest.mark.your_marker]`
3. Use the `api` fixture for all HTTP calls: `api.get()`, `api.post()`, etc.
4. For streaming tests, use raw `requests` with `stream=True` (the `api` fixture's retry logic interferes with streaming)
5. Share state via module-level `_state` dict
6. Mark slow tests (>30s) with `@pytest.mark.slow`
7. Mark negative tests with `@pytest.mark.negative`

## API Endpoints Under Test

All endpoints are under `/api_v2/003/`:

### Content
- `GET/POST /workspaces/`, `GET/PUT/PATCH/DELETE /workspaces/{id}/`
- `GET/POST /documentation/`, `GET/PUT/PATCH/DELETE /documentation/{id}/`
- `GET/POST /books/`, `GET/PUT/PATCH/DELETE /books/{id}/`
- `GET/POST /versions/`, `GET/PUT/PATCH/DELETE /versions/{id}/`
- `GET/POST /languages/`, `GET/PUT/PATCH/DELETE /languages/{id}/`
- `GET/POST /articles/`, `GET/PUT/PATCH/DELETE /articles/{id}/`
- `GET/POST /snippets/`, `GET/PUT/PATCH/DELETE /snippets/{id}/`

### Video-to-Docs
- `POST /video-to-docs/submit/` — submit job (URL or file_id, quality, doc_style, rewrite_instructions, template_instruction, auto_generate)
- `GET /video-to-docs/` — list jobs
- `GET /video-to-docs/{id}/status/` — poll status
- `GET /video-to-docs/{id}/result/` — get full result (markdown, transcription, sections, images)
- `POST /video-to-docs/{id}/generate/` — trigger AI rewrite on completed analysis
- `POST /video-to-docs/{id}/cancel/` — cancel running job
- `POST /video-to-docs/estimate/` — estimate credit cost

### Deployment Chat
- `POST /deployments/{id}/chat/` — ask AI questions against deployment's indexed content (sync or SSE streaming)

### Credits
- `GET /credits/balance/` — current credit balance + video quality tiers
- `GET /credits/usage/` — transaction history (filterable by type)

### Files, Deployments, Jobs
- `POST /files/generate_temp_url/`, `POST /files/upload/`, `GET /files/{id}/presigned_url/`
- `GET/POST /deployments/`, `POST /deployments/{id}/refresh/`
- `GET /jobs/`, `GET /jobs/{id}/`
