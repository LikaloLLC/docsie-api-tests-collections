#!/usr/bin/env bash
#
# Video-to-Docs: Full pipeline example (Shell/curl)
#
# Submits a video URL, polls for analysis, triggers AI rewrite,
# and downloads the result as markdown, DOCX, and PDF.
#
# Usage:
#   export DOCSIE_API_KEY="your_key"
#   ./video_to_docs.sh "https://example.com/video.mp4"
#   ./video_to_docs.sh "https://example.com/video.mp4" sop
#
set -euo pipefail

API_KEY="${DOCSIE_API_KEY:?Set DOCSIE_API_KEY}"
BASE="${DOCSIE_BASE_URL:-https://app.docsie.io}/api_v2/003"
VIDEO_URL="${1:?Usage: $0 <video_url> [doc_style]}"
DOC_STYLE="${2:-guide}"

auth=(-H "Authorization: Api-Key $API_KEY" -H "Content-Type: application/json" -H "Accept: application/json")

# ── 1. Submit ──────────────────────────────────────────────
echo "==> Submitting video job (style=$DOC_STYLE)..."
submit=$(curl -s -X POST "${auth[@]}" "$BASE/video-to-docs/submit/" -d "{
  \"video_url\": \"$VIDEO_URL\",
  \"quality\": \"draft\",
  \"language\": \"english\",
  \"doc_style\": \"$DOC_STYLE\",
  \"auto_generate\": false
}")
job_id=$(echo "$submit" | python3 -c "import sys,json; print(json.load(sys.stdin)['job_id'])")
echo "    Job ID: $job_id"

# ── 2. Poll analysis ──────────────────────────────────────
echo "==> Polling analysis (up to 15 min)..."
for i in $(seq 1 60); do
  status_resp=$(curl -s "${auth[@]}" "$BASE/video-to-docs/$job_id/status/")
  job_status=$(echo "$status_resp" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','?'))")
  echo "    [$i] $job_status"
  [ "$job_status" = "done" ] && break
  [ "$job_status" = "failed" ] && echo "FAILED" && exit 1
  sleep 15
done

# ── 3. Get result ─────────────────────────────────────────
echo "==> Fetching result..."
result=$(curl -s "${auth[@]}" "$BASE/video-to-docs/$job_id/result/")
echo "$result" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f\"    Markdown: {len(d.get('markdown',''))} chars\")
print(f\"    Transcription: {len(d.get('transcription','') or '')} chars\")
print(f\"    Sections: {len(d.get('sections',[]))}\")
print(f\"    Images: {len(d.get('images',[]))}\")
"

# Save raw outputs
echo "$result" | python3 -c "import sys,json; print(json.load(sys.stdin).get('markdown',''))" > analysis_result.md
echo "$result" | python3 -c "import sys,json; print(json.load(sys.stdin).get('transcription','') or '')" > transcription.txt
echo "    Saved: analysis_result.md, transcription.txt"

# ── 4. Generate (MD + DOCX + PDF) ────────────────────────
echo "==> Triggering AI rewrite..."
gen=$(curl -s -X POST "${auth[@]}" "$BASE/video-to-docs/$job_id/generate/" -d "{
  \"doc_style\": \"$DOC_STYLE\",
  \"output_formats\": [\"md\", \"docx\", \"pdf\"]
}")
gen_job_id=$(echo "$gen" | python3 -c "import sys,json; print(json.load(sys.stdin)['generate_job_id'])")
echo "    Generate job: $gen_job_id"

echo "==> Polling generate job (up to 5 min)..."
for i in $(seq 1 20); do
  gen_resp=$(curl -s "${auth[@]}" "$BASE/jobs/$gen_job_id/")
  gen_status=$(echo "$gen_resp" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','?'))")
  echo "    [$i] $gen_status"
  [ "$gen_status" = "done" ] && break
  [ "$gen_status" = "failed" ] && echo "FAILED" && exit 1
  sleep 15
done

# Save rewritten markdown
echo "$gen_resp" | python3 -c "import sys,json; print(json.load(sys.stdin).get('result',{}).get('markdown',''))" > generated.md
echo "    Saved: generated.md"

# Extract export job IDs
docx_job=$(echo "$gen_resp" | python3 -c "import sys,json; print(json.load(sys.stdin).get('result',{}).get('exports',{}).get('docx',{}).get('job_id',''))" 2>/dev/null || true)
pdf_job=$(echo "$gen_resp" | python3 -c "import sys,json; print(json.load(sys.stdin).get('result',{}).get('exports',{}).get('pdf',{}).get('job_id',''))" 2>/dev/null || true)

# ── 5. Download exports ───────────────────────────────────
download_export() {
  local fmt=$1 jid=$2
  [ -z "$jid" ] && return
  echo "==> Waiting for $fmt export..."
  for i in $(seq 1 12); do
    resp=$(curl -s "${auth[@]}" "$BASE/jobs/$jid/")
    st=$(echo "$resp" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','?'))")
    [ "$st" = "done" ] && break
    sleep 10
  done
  url=$(echo "$resp" | python3 -c "import sys,json; print(json.load(sys.stdin).get('result',{}).get('url',''))")
  fname=$(echo "$resp" | python3 -c "import sys,json; print(json.load(sys.stdin).get('result',{}).get('filename','output.$fmt'))")
  if [ -n "$url" ]; then
    curl -s -o "$fname" "$url"
    echo "    Downloaded: $fname ($(du -h "$fname" | cut -f1))"
  fi
}

download_export "docx" "$docx_job"
download_export "pdf" "$pdf_job"

echo ""
echo "==> Complete! Files:"
ls -lh analysis_result.md transcription.txt generated.md *.docx *.pdf 2>/dev/null || true
