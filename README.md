# Docsie Partner API Test Suite

Integration test suite for the [Docsie Partner API](https://app.docsie.io/schema/redoc/). Tests run against a live Docsie instance (staging or production) using a real API key.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Edit .env with your API key and base URL

# 3. Run fast tests (~2 min)
pytest tests/ -m "not slow"

# 4. Run everything including video processing (~15 min)
pytest tests/
```

## What's Tested

| File | Area | Tests | Marker |
|------|------|-------|--------|
| test_01 | Workspaces | 8 | `content` |
| test_02 | Documentation shelves | 7 | `content` |
| test_03 | Books | 7 | `content` |
| test_04 | Versions & Languages | 8 | `content` |
| test_05 | Articles | 8 | `content` |
| test_06 | Snippets | 8 | `content` |
| test_10 | Credits balance & usage | 10 | `credits` |
| test_11 | Video cost estimation | 7 | `video` |
| test_12 | Video job submission | 8 | `video` |
| test_13 | Video poll & result | 5 | `video`, `slow` |
| test_14 | Video job cancellation | 5 | `video` |
| test_15 | Video AI generation | 3 | `video` |
| test_20 | Files | 6 | `files` |
| test_21 | Deployments | 4 | `deployments` |
| test_22 | Jobs | 4 | — |
| test_23 | Auth negative cases | 10 | `negative` |
| test_24 | Pagination | 5 | — |
| test_25 | Smoke (all GETs) | 14 | `smoke` |
| test_30 | Video E2E pipeline | 18 | `video`, `slow` |
| test_31 | Deployment chat | 17 | `deployments` |

**~145 total tests** covering positive flows, negative paths, auth, pagination, streaming, and the full video-to-docs + AI rewrite pipeline.

## Running Specific Test Groups

```bash
# Smoke tests only
pytest -m smoke

# Content hierarchy CRUD
pytest -m content

# Video-to-docs pipeline (fast tests)
pytest -m "video and not slow"

# Deployment chat (sync + streaming + multi-turn)
pytest -m deployments

# Credits
pytest -m credits

# All negative / error path tests
pytest -m negative

# Full video E2E (uploads video, polls Dokuta, validates result, triggers AI rewrite)
pytest tests/test_30_video_e2e.py -v
```

## Configuration

Copy `.env.example` to `.env` and set:

| Variable | Required | Description |
|----------|----------|-------------|
| `DOCSIE_API_KEY` | Yes | Partner API key (`Api-Key` header) |
| `DOCSIE_BASE_URL` | Yes | Base URL (e.g., `https://staging.docsie.io`) |
| `TEST_WORKSPACE_ID` | No | Workspace to use. Auto-detects if not set. |
| `TEST_VIDEO_URL` | No | Video URL for URL-based tests. Falls back to YouTube sample. |

## Assets

`assets/test_video.mp4` — 17MB PII demo video used by the E2E video pipeline test. This file is committed to the repo via Git LFS.

## API Reference

The full OpenAPI schema is at `schema.json` (exported from `/schema/`). Live docs: `https://app.docsie.io/schema/redoc/`

## Authentication

All requests use the `Api-Key` header:

```
Authorization: Api-Key <your_key>
```

Get your API key from **Organization Settings > API Keys** in the Docsie dashboard.

## Content Model

```
Organization
  └── Workspace
       └── Documentation Shelf
            └── Book
                 └── Version
                      └── Language
                           └── Article
```

## Rate Limiting

The API enforces plan-based rate limits. The test client automatically retries on 429 responses with the server's `Retry-After` header. If you see many 429s, wait a minute and re-run.

## Known Issues

Tests marked `xfail` represent known API bugs that have been reported:

- **Language create via API** — returns serialized dict, view tries to call `.pk` on it
- **Article create via API** — same pattern
- **Files API** — uses session auth instead of API key auth

## Postman

Import `postman/Docsie_Partner_API.postman_collection.json` into Postman for manual testing. Set the `api_key` and `base_url` collection variables.
