# Docsie Partner API Test Suite

## Overview

This is an integration test suite for the Docsie Partner API. Tests run against a live Docsie instance using pytest + requests. The suite covers the full API surface: content CRUD, video-to-docs pipeline, AI chat, credits, files, deployments, and auth.

## Code Examples

Ready-to-run examples in `examples/` that demonstrate the full video-to-docs pipeline:

| File | Language | Description |
|------|----------|-------------|
| [`examples/video_to_docs.py`](examples/video_to_docs.py) | Python | Full pipeline with file upload support. `pip install requests` |
| [`examples/video_to_docs.js`](examples/video_to_docs.js) | Node.js | Zero dependencies (uses built-in `http`/`https`) |
| [`examples/video_to_docs.sh`](examples/video_to_docs.sh) | Shell/curl | Bash script, requires `curl` and `python3` for JSON parsing |
| [`examples/video_to_docs.rb`](examples/video_to_docs.rb) | Ruby | Uses standard library only (`net/http`, `json`) |
| [`examples/video_to_docs.php`](examples/video_to_docs.php) | PHP | Uses `file_get_contents` with stream context |
| [`examples/video_to_docs.go`](examples/video_to_docs.go) | Go | Standard library only (`net/http`, `encoding/json`) |
| [`examples/video_to_docs.java`](examples/video_to_docs.java) | Java 11+ | Uses `java.net.http.HttpClient` + Gson for JSON |
| [`examples/video_to_docs.cs`](examples/video_to_docs.cs) | C# / .NET 6+ | Uses `HttpClient` + `System.Text.Json` |

**Quick start (any language):**
```bash
export DOCSIE_API_KEY="your_key"

# Python (also supports local file: python examples/video_to_docs.py ./video.mp4 sop)
python examples/video_to_docs.py https://example.com/video.mp4 sop

# Node.js
node examples/video_to_docs.js https://example.com/video.mp4 guide

# Shell
./examples/video_to_docs.sh https://example.com/video.mp4 tutorial

# Ruby
ruby examples/video_to_docs.rb https://example.com/video.mp4

# PHP
php examples/video_to_docs.php https://example.com/video.mp4

# Go
go run examples/video_to_docs.go https://example.com/video.mp4 sop

# Java (requires Gson jar)
javac -cp gson.jar examples/video_to_docs.java && java -cp examples:gson.jar video_to_docs https://example.com/video.mp4

# C# / .NET
dotnet script examples/video_to_docs.cs https://example.com/video.mp4
```

Each example outputs: `analysis_result.md`, `transcription.txt`, `generated.md`, plus `.docx` and `.pdf` files.

## Postman Collections

| Collection | Description |
|-----------|-------------|
| [`postman/Docsie_Partner_API.postman_collection.json`](postman/Docsie_Partner_API.postman_collection.json) | All endpoints, manual testing |
| [`postman/Video_to_Docs_E2E.postman_collection.json`](postman/Video_to_Docs_E2E.postman_collection.json) | Automated E2E pipeline with test scripts (8 steps) |

The E2E collection has test scripts that validate responses and chain job IDs between steps. Set `base_url`, `api_key`, `video_url` in collection variables, then run with Collection Runner.

## How to Run

```bash
cd external/docsie-api-test-suite
pip install -r requirements.txt
pytest tests/ -m "not slow"           # fast tests (~2 min)
pytest tests/                          # everything (~15 min)
pytest tests/test_31_deployment_chat.py -v  # just chat tests

# Against localhost
DOCSIE_BASE_URL=http://localhost:8003 pytest tests/test_30_video_e2e.py -v
```

## Configuration

Tests read from `.env` in this directory:
- `DOCSIE_API_KEY` — required, the `Api-Key` header value
- `DOCSIE_BASE_URL` — defaults to `https://staging.docsie.io`
- `TEST_WORKSPACE_ID` — optional, auto-detected from API key's org if not set
- `TEST_VIDEO_URL` — fallback video URL for URL-based tests (default: YouTube sample)

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
- `POST /video-to-docs/{id}/generate/` — trigger AI rewrite with output_formats (md, docx, pdf)
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

---

## Video-to-Docs Pipeline — Detailed Architecture

### How It Works

The video-to-docs pipeline converts a video file into polished documentation (markdown, DOCX, or PDF) through a multi-step process:

1. **Video → Dokuta** — Dokuta extracts frames, runs speech-to-text, generates AI image descriptions, and produces raw structured markdown with screenshots
2. **Dokuta → Docsie** — Docsie downloads the markdown, rehosts images from Dokuta's temporary storage to Docsie CDN, fetches the transcript
3. **Docsie → Claude** — The raw markdown is sent to Claude (Anthropic LLM) for rewriting into polished documentation matching the requested style (SOP, guide, tutorial, etc.)
4. **Claude → Export** — The rewritten markdown is optionally exported to DOCX and/or PDF via the export pipeline

### Internal Code Path

The API job (`video_to_docs_api`) uses the exact same code path as the enterprise chat agent:

```
video_to_docs_api (Celery job)
  └── Creates ImportSession(source_type='video_dokuta')
  └── Calls universal_import_analysis() synchronously
       └── SourceExtractorFactory.create('video_dokuta')
            └── DokutaContentExtractor
                 ├── _send_to_dokuta()    — POST /generation/{endpoint}/
                 ├── _poll_dokuta_api()   — GET /generation/by-session/{session_id}
                 └── analyze_video()      — orchestrates send + poll + download
       └── ImportWorkflowEngine.execute_analysis_workflow()
            └── Stores results in session.structure_analysis
  └── Extracts markdown from analysis result
  └── Rehosts images via _rehost_markdown_images()
  └── Fetches transcript via _get_dokuta_transcript()
  └── Deducts credits via _deduct_video_credits() (idempotent)
  └── If auto_generate: spawns video_doc_generate_api job
```

The generate job (`video_doc_generate_api`) handles the AI rewrite:

```
video_doc_generate_api (Celery job)
  └── Loads ImportSession, fetches Dokuta markdown (with URL refresh)
  └── Rehosts any remaining external images
  └── Sends to Claude with style/language/template instructions
  └── Handles max_tokens continuation (up to 5 rounds)
  └── Returns rewritten markdown in job result
  └── Optionally spawns export_markdown_pdf jobs for DOCX/PDF
```

### Full API Flow Example

#### Step 1: Estimate cost (optional)

```bash
curl -X POST https://staging.docsie.io/api_v2/003/video-to-docs/estimate/ \
  -H "Authorization: Api-Key YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "quality": "standard",
    "duration_minutes": 5
  }'
```

Response:
```json
{
  "quality": "standard",
  "seconds_per_frame": 8,
  "credits_per_minute": 500,
  "duration_minutes": 5,
  "estimate": {"total_credits": 2500},
  "has_sufficient_credits": true,
  "balance": {"total_available": 15000000}
}
```

#### Step 2: Upload video file (optional — can use URL instead)

```bash
# Get presigned upload URL
curl -X POST https://staging.docsie.io/api_v2/003/files/generate_temp_url/ \
  -H "Authorization: Api-Key YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"key": "my-training-video.mp4", "content_type": "video/mp4", "public": true}'

# Upload to S3 using returned URL
curl -X PUT "RETURNED_PRESIGNED_URL" \
  -H "Content-Type: video/mp4" \
  --data-binary @my-training-video.mp4

# Register file in Docsie (type MUST be "file", not "video")
curl -X POST https://staging.docsie.io/api_v2/003/files/upload/ \
  -H "Authorization: Api-Key YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "temp_key": "my-training-video.mp4",
    "type": "file",
    "workspace": "workspace_XXXXX",
    "public": true
  }'
# Returns: {"id": "file_XXXXX", ...}
```

#### Step 3: Submit video-to-docs job

```bash
# With file_id (from upload):
curl -X POST https://staging.docsie.io/api_v2/003/video-to-docs/submit/ \
  -H "Authorization: Api-Key YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "file_XXXXX",
    "quality": "draft",
    "language": "english",
    "doc_style": "sop",
    "rewrite_instructions": "Write for a compliance officer audience. Use formal tone.",
    "auto_generate": false
  }'

# Or with video URL:
curl -X POST https://staging.docsie.io/api_v2/003/video-to-docs/submit/ \
  -H "Authorization: Api-Key YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "video_url": "https://example.com/video.mp4",
    "quality": "standard",
    "language": "english",
    "doc_style": "guide",
    "auto_generate": true
  }'
```

Response:
```json
{
  "job_id": "job_key_XXXXX",
  "status": "started",
  "quality": "draft",
  "source_type": "file",
  "source_file_id": "file_XXXXX",
  "workspace_id": "workspace_XXXXX",
  "credits_per_minute": 250
}
```

**Parameters:**
- `quality` — `draft` (20 spf, 250 credits/min), `standard` (10 spf, 500), `detailed` (5 spf, 1000), `ultra` (2 spf, 2000)
- `doc_style` — `guide`, `sop`, `tutorial`, `how-to`, `blog`, `training`, `knowledge-base`, `release-notes`, `reference`, `product`, `policy`
- `auto_generate` — when `true` (default), automatically runs LLM rewrite after Dokuta analysis
- `rewrite_instructions` — custom tone/audience/format instructions for the AI rewrite
- `template_instruction` — structural outline the output should follow

#### Step 4: Poll until analysis completes

```bash
curl https://staging.docsie.io/api_v2/003/video-to-docs/job_key_XXXXX/status/ \
  -H "Authorization: Api-Key YOUR_KEY"
```

Poll every 15 seconds. Status goes: `started` → `done` (or `failed`).

#### Step 5: Get analysis result

```bash
curl https://staging.docsie.io/api_v2/003/video-to-docs/job_key_XXXXX/result/ \
  -H "Authorization: Api-Key YOUR_KEY"
```

Response contains:
```json
{
  "status": "done",
  "session_id": "2391",
  "markdown": "# How to Add a New Subscription...\n\n## Step 1...\n![screenshot](https://cdn.docsie.io/...)",
  "transcription": "so in this video we're just going to be adding a new subscription...",
  "sections": [
    {"title": "Video Documentation", "content": "...", "heading_level": 1, "timestamp_range": null},
    {"title": "How to Add a New Subscription", "content": "...", "heading_level": 2, "timestamp_range": null}
  ],
  "images": [
    {"url": "https://cdn.docsie.io/workspace_XXX/file_XXX/image.jpg", "description": "AI-generated description", "image_id": "img_2391_0"}
  ],
  "quality": "draft",
  "seconds_per_frame": 20,
  "credits_charged": 500,
  "rehosted_images": 4
}
```

At this point you have: **raw Dokuta markdown** (with screenshots), **full transcript**, **parsed sections**, and **CDN-hosted images**. If `auto_generate` was `true`, the AI rewrite is already running.

#### Step 6: Trigger AI rewrite (if auto_generate was false)

```bash
curl -X POST https://staging.docsie.io/api_v2/003/video-to-docs/job_key_XXXXX/generate/ \
  -H "Authorization: Api-Key YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "doc_style": "sop",
    "rewrite_instructions": "Write a formal Standard Operating Procedure.",
    "template_instruction": "1. Purpose\n2. Scope\n3. Procedure\n4. Records",
    "target_language": "english",
    "output_formats": ["md", "docx", "pdf"]
  }'
```

Response:
```json
{
  "job_id": "job_key_XXXXX",
  "generate_job_id": "job_key_YYYYY",
  "status": "started",
  "doc_style": "sop"
}
```

#### Step 7: Poll generate job

```bash
curl https://staging.docsie.io/api_v2/003/jobs/job_key_YYYYY/ \
  -H "Authorization: Api-Key YOUR_KEY"
```

When done, the result contains:
```json
{
  "status": "done",
  "result": {
    "status": "completed",
    "title": "Standard Operating Procedure: Adding a New Subscription for a Customer",
    "style": "sop",
    "input_word_count": 480,
    "output_word_count": 604,
    "elapsed_seconds": 18.0,
    "markdown": "# Standard Operating Procedure: Adding a New Subscription...",
    "exports": {
      "docx": {"job_id": "job_key_DOCX", "status": "started"},
      "pdf": {"job_id": "job_key_PDF", "status": "started"}
    }
  }
}
```

#### Step 8: Get export download URLs

```bash
# Poll DOCX export job
curl https://staging.docsie.io/api_v2/003/jobs/job_key_DOCX/ \
  -H "Authorization: Api-Key YOUR_KEY"

# When done:
# {"status": "done", "result": {"url": "https://s3.amazonaws.com/...", "filename": "...docx"}}

# Poll PDF export job
curl https://staging.docsie.io/api_v2/003/jobs/job_key_PDF/ \
  -H "Authorization: Api-Key YOUR_KEY"

# When done:
# {"status": "done", "result": {"url": "https://s3.amazonaws.com/...", "filename": "...pdf"}}
```

### What Each Output Contains

| Output | Content |
|--------|---------|
| **Analysis result** (step 5) | Raw Dokuta markdown with screenshots + AI image descriptions, full transcript, parsed sections with timestamps, CDN-hosted images |
| **Rewritten markdown** (step 7) | Polished documentation in requested style, all images preserved, structure matching template if provided |
| **DOCX** (step 8) | Word document with embedded images, proper headings, formatted tables |
| **PDF** (step 8) | PDF via DOCX→Lambda conversion, same content as DOCX |

### Quality Tiers

| Tier | Seconds Per Frame | Credits/Min | Use Case |
|------|-------------------|-------------|----------|
| `draft` | 20 | 250 | Quick preview, short videos |
| `standard` | 10 | 500 | Default, good balance |
| `detailed` | 5 | 1,000 | Training videos, step-by-step |
| `ultra` | 2 | 2,000 | Dense UI demos, compliance |

### File Upload Notes

- File type must be `"file"` (not `"video"`) — there is no dedicated video uploader type
- Files API supports both `Api-Key` and `Bearer` auth headers
- Upload is a 3-step process: generate_temp_url → PUT to S3 → register via /files/upload/
- All file operations are org-scoped when using API key auth

### Security

- All endpoints require `Api-Key` authentication via `RequireAPIKeyMixin`
- Jobs are org-scoped: you can only see/poll/cancel jobs belonging to your organization
- File uploads validate that workspace/book/documentation belong to your org
- The analysis `ImportSession` is scoped to the job's organization
- Export job URLs are presigned S3 URLs with expiration
- Credits are checked before job starts (402 if insufficient)

### Timing Expectations

| Step | Typical Duration |
|------|-----------------|
| File upload (17MB) | ~30 seconds |
| Dokuta analysis (draft, 2 min video) | 3-8 minutes |
| Dokuta analysis (standard, 5 min video) | 5-15 minutes |
| AI rewrite (Claude) | 15-30 seconds |
| DOCX export | 5-10 seconds |
| PDF export (DOCX → Lambda → PDF) | 15-30 seconds |
