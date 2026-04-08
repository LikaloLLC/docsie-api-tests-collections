# Docsie Partner API — SDK Examples & Test Suite

Turn videos into professional documentation (Markdown, DOCX, PDF) with the Docsie API. Upload a training video or screen recording, and get back polished SOPs, user guides, tutorials, and knowledge base articles — complete with AI-extracted screenshots, transcriptions, and step-by-step instructions.

## What You Can Build

- **Video to SOP** — Convert compliance training videos into Standard Operating Procedures
- **Screen recording to user guide** — Turn product walkthroughs into step-by-step guides with screenshots
- **Training video to knowledge base** — Auto-generate searchable documentation from onboarding videos
- **Video to multilingual docs** — Generate documentation in 100+ languages from any video
- **Automated doc pipeline** — Integrate video-to-docs into your CI/CD or content pipeline

## Quick Start

```bash
# 1. Get your API key from Docsie dashboard → Organization Settings → API Keys

# 2. Run the example in your language
export DOCSIE_API_KEY="your_key"
python examples/video_to_docs.py https://example.com/training-video.mp4 sop
```

Output files: `analysis_result.md` (raw analysis), `transcription.txt`, `generated.md` (AI-rewritten), plus `.docx` and `.pdf`.

## Code Examples

Ready-to-run examples in 8 languages — each one runs the full pipeline end to end:

| Language | File | Dependencies |
|----------|------|-------------|
| **Python** | [`examples/video_to_docs.py`](examples/video_to_docs.py) | `requests` |
| **Node.js** | [`examples/video_to_docs.js`](examples/video_to_docs.js) | None (built-in `http`) |
| **Shell/curl** | [`examples/video_to_docs.sh`](examples/video_to_docs.sh) | `curl`, `python3` |
| **Go** | [`examples/video_to_docs.go`](examples/video_to_docs.go) | None (standard library) |
| **Ruby** | [`examples/video_to_docs.rb`](examples/video_to_docs.rb) | None (standard library) |
| **PHP** | [`examples/video_to_docs.php`](examples/video_to_docs.php) | None (`file_get_contents`) |
| **Java** | [`examples/video_to_docs.java`](examples/video_to_docs.java) | Gson |
| **C# / .NET** | [`examples/video_to_docs.cs`](examples/video_to_docs.cs) | None (.NET 6+ built-in) |

The Python example also supports uploading local video files:
```bash
python examples/video_to_docs.py path/to/video.mp4 sop
```

## How It Works

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Your Video  │────▶│   Dokuta AI  │────▶│  Claude LLM  │────▶│   MD / DOCX  │
│  (MP4, URL)  │     │  Analysis    │     │  Rewrite     │     │   / PDF      │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
                      • Frame extraction   • Style matching     • Markdown
                      • Speech-to-text     • Template following • Word document
                      • AI image captions  • Tone/audience      • PDF with images
                      • Screenshot capture • Grounded output    • Transcription
```

**Step 1: Submit** → Upload a video or provide a URL. Choose quality tier and document style.

**Step 2: Analyze** → Dokuta AI extracts frames, transcribes speech, generates image descriptions, and produces structured markdown with screenshots.

**Step 3: Rewrite** → Claude rewrites the raw analysis into polished documentation matching your style (SOP, guide, tutorial, etc.) with custom instructions.

**Step 4: Export** → Get the result as Markdown, DOCX, and/or PDF with all images embedded.

## API Endpoints

All endpoints under `/api_v2/003/`. Authenticate with `Authorization: Api-Key <your_key>`.

### Video-to-Docs Pipeline

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/video-to-docs/submit/` | Submit video for processing |
| `GET` | `/video-to-docs/{id}/status/` | Poll job status |
| `GET` | `/video-to-docs/{id}/result/` | Get analysis result (markdown, transcription, images) |
| `POST` | `/video-to-docs/{id}/generate/` | Trigger AI rewrite → MD, DOCX, PDF |
| `POST` | `/video-to-docs/estimate/` | Estimate credit cost before submitting |
| `GET` | `/video-to-docs/` | List all video-to-docs jobs |
| `POST` | `/video-to-docs/{id}/cancel/` | Cancel a running job |

### Content Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET/POST` | `/workspaces/` | List / create workspaces |
| `GET/POST` | `/documentation/` | List / create documentation shelves |
| `GET/POST` | `/books/` | List / create books |
| `GET/POST` | `/articles/` | List / create articles |
| `GET/POST` | `/versions/` | List / create versions |
| `GET/POST` | `/languages/` | List / create languages |

### Other

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/deployments/{id}/chat/` | AI Q&A against published docs (sync or SSE) |
| `GET` | `/credits/balance/` | Credit balance and quality tiers |
| `GET` | `/credits/usage/` | Transaction history |
| `GET` | `/jobs/{id}/` | Poll any background job |
| `POST` | `/files/upload/` | Register uploaded files |

## Document Styles

| Style | Use Case |
|-------|----------|
| `guide` | User guides, product documentation |
| `sop` | Standard Operating Procedures, compliance docs |
| `tutorial` | Step-by-step learning tutorials |
| `how-to` | Task-oriented how-to articles |
| `training` | Training manuals, onboarding docs |
| `knowledge-base` | Searchable KB articles |
| `blog` | Blog posts, announcements |
| `policy` | Policy documents, governance |
| `product` | Product documentation, release notes |
| `reference` | API references, technical specs |
| `release-notes` | Changelog, release announcements |

## Quality Tiers & Pricing

| Tier | Frames/sec | Credits/Min | Best For |
|------|-----------|-------------|----------|
| `draft` | 1 per 20s | 250 | Quick previews, short videos |
| `standard` | 1 per 10s | 500 | General documentation |
| `detailed` | 1 per 5s | 1,000 | Training videos, step-by-step |
| `ultra` | 1 per 2s | 2,000 | Dense UI demos, compliance |

## Running the Test Suite

```bash
# Install
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API key

# Fast tests (~2 min)
pytest tests/ -m "not slow"

# Full suite including video processing (~15 min)
pytest tests/

# Just video pipeline
pytest tests/test_30_video_e2e.py -v

# Against local dev server
DOCSIE_BASE_URL=http://localhost:8003 pytest tests/ -v
```

### Test Coverage

| Tests | Area |
|-------|------|
| `test_01-06` | Content CRUD (workspaces, shelves, books, articles, etc.) |
| `test_10-15` | Credits, video estimation, submission, polling, generation |
| `test_20-25` | Files, deployments, jobs, auth, pagination, smoke |
| `test_30` | Full video E2E pipeline (upload → analysis → rewrite → validate) |
| `test_31` | Deployment AI chat (sync, streaming, multi-turn) |

**~145 total tests** covering positive flows, error paths, auth, pagination, streaming, and the complete video-to-docs pipeline.

## Postman Collections

| Collection | Description |
|-----------|-------------|
| [`Docsie_Partner_API.postman_collection.json`](postman/Docsie_Partner_API.postman_collection.json) | All endpoints for manual testing |
| [`Video_to_Docs_E2E.postman_collection.json`](postman/Video_to_Docs_E2E.postman_collection.json) | Automated 8-step E2E pipeline with test scripts |

Import into Postman, set `base_url` and `api_key` collection variables, and run.

## API Reference

- **Live docs**: [app.docsie.io/schema/redoc/](https://app.docsie.io/schema/redoc/)
- **OpenAPI spec**: [`schema.json`](schema.json)

## Authentication

```
Authorization: Api-Key <your_partner_api_key>
```

Get your API key from **Organization Settings > API Keys** in the [Docsie dashboard](https://app.docsie.io).

## Links

- [Docsie Platform](https://www.docsie.io) — AI-powered documentation platform
- [API Documentation](https://app.docsie.io/schema/redoc/) — Interactive API reference
- [Docsie Blog](https://www.docsie.io/blog/) — Product updates and guides
