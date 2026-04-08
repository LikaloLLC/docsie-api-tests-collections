"""
Video-to-Docs: Full pipeline example (Python)

Uploads a video, runs Dokuta analysis, triggers AI rewrite,
and downloads the result as markdown, DOCX, and PDF.

Usage:
    pip install requests
    export DOCSIE_API_KEY="your_key"
    python video_to_docs.py path/to/video.mp4
    python video_to_docs.py https://example.com/video.mp4
"""
import os
import sys
import time
import requests

API_KEY = os.environ.get("DOCSIE_API_KEY", "")
BASE_URL = os.environ.get("DOCSIE_BASE_URL", "https://app.docsie.io")
API = f"{BASE_URL}/api_v2/003"

HEADERS = {
    "Authorization": f"Api-Key {API_KEY}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}


def api_get(path):
    return requests.get(f"{API}{path}", headers=HEADERS)


def api_post(path, json=None):
    return requests.post(f"{API}{path}", headers=HEADERS, json=json)


def poll(path, timeout=900, interval=15):
    """Poll an endpoint until status is terminal."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        data = api_get(path).json()
        status = data.get("status") or data.get("job_status", "")
        if status in ("done", "failed", "canceled"):
            return data
        print(f"  ... {status} (polling again in {interval}s)")
        time.sleep(interval)
    raise TimeoutError(f"Timed out after {timeout}s")


def upload_file(filepath, workspace_id=None):
    """Upload a local file to Docsie and return the file_id."""
    filename = os.path.basename(filepath)
    print(f"[1/3] Getting presigned upload URL for {filename}...")
    resp = api_post("/files/generate_temp_url/", json={
        "key": f"api-upload-{int(time.time())}-{filename}",
        "content_type": "video/mp4",
        "public": True,
    })
    resp.raise_for_status()
    upload_url = resp.json()["url"]
    temp_key = resp.json().get("key", "")

    print(f"[2/3] Uploading {os.path.getsize(filepath) / 1e6:.1f} MB to S3...")
    with open(filepath, "rb") as f:
        put_resp = requests.put(upload_url, data=f, headers={"Content-Type": "video/mp4"}, timeout=300)
    put_resp.raise_for_status()

    print(f"[3/3] Registering file in Docsie...")
    body = {"temp_key": temp_key, "type": "file", "public": True}
    if workspace_id:
        body["workspace"] = workspace_id
    resp = api_post("/files/upload/", json=body)
    resp.raise_for_status()
    file_id = resp.json()["id"]
    print(f"  File registered: {file_id}")
    return file_id


def submit_video(video_url=None, file_id=None, quality="draft", doc_style="guide",
                 rewrite_instructions="", auto_generate=False):
    """Submit a video-to-docs job. Returns the job_id."""
    body = {
        "quality": quality,
        "language": "english",
        "doc_style": doc_style,
        "auto_generate": auto_generate,
    }
    if rewrite_instructions:
        body["rewrite_instructions"] = rewrite_instructions
    if file_id:
        body["file_id"] = file_id
    elif video_url:
        body["video_url"] = video_url
    else:
        raise ValueError("Provide video_url or file_id")

    print(f"Submitting video-to-docs job (quality={quality}, style={doc_style})...")
    resp = api_post("/video-to-docs/submit/", json=body)
    resp.raise_for_status()
    data = resp.json()
    job_id = data["job_id"]
    print(f"  Job started: {job_id} ({data['credits_per_minute']} credits/min)")
    return job_id


def wait_for_analysis(job_id):
    """Poll until analysis completes. Returns the full result."""
    print(f"Waiting for Dokuta analysis...")
    poll(f"/video-to-docs/{job_id}/status/")

    print(f"Fetching result...")
    resp = api_get(f"/video-to-docs/{job_id}/result/")
    resp.raise_for_status()
    result = resp.json()
    print(f"  Markdown: {len(result.get('markdown', ''))} chars")
    print(f"  Transcription: {len(result.get('transcription', '') or '')} chars")
    print(f"  Sections: {len(result.get('sections', []))}")
    print(f"  Images: {len(result.get('images', []))}")
    print(f"  Credits charged: {result.get('credits_charged')}")
    return result


def generate_docs(job_id, doc_style="guide", rewrite_instructions="",
                  template_instruction="", output_formats=None):
    """Trigger AI rewrite and optional DOCX/PDF export. Returns generate result."""
    if output_formats is None:
        output_formats = ["md", "docx", "pdf"]

    print(f"Triggering AI rewrite (style={doc_style}, formats={output_formats})...")
    resp = api_post(f"/video-to-docs/{job_id}/generate/", json={
        "doc_style": doc_style,
        "rewrite_instructions": rewrite_instructions,
        "template_instruction": template_instruction,
        "output_formats": output_formats,
    })
    resp.raise_for_status()
    gen_job_id = resp.json()["generate_job_id"]
    print(f"  Generate job: {gen_job_id}")

    print(f"Waiting for LLM rewrite...")
    result = poll(f"/jobs/{gen_job_id}/", timeout=300, interval=10)

    if result.get("status") == "failed":
        print(f"  ERROR: {result.get('result', {}).get('error')}")
        return result

    gen_result = result.get("result", {})
    print(f"  Title: {gen_result.get('title')}")
    print(f"  Words: {gen_result.get('input_word_count')} → {gen_result.get('output_word_count')}")
    print(f"  Elapsed: {gen_result.get('elapsed_seconds')}s")

    # Wait for exports
    exports = gen_result.get("exports", {})
    for fmt, info in exports.items():
        export_job_id = info.get("job_id")
        if not export_job_id:
            continue
        print(f"Waiting for {fmt.upper()} export...")
        export_result = poll(f"/jobs/{export_job_id}/", timeout=120, interval=5)
        export_data = export_result.get("result", {})
        if export_data.get("url"):
            exports[fmt]["url"] = export_data["url"]
            exports[fmt]["filename"] = export_data.get("filename", "")
            print(f"  {fmt.upper()}: {export_data.get('filename')}")
        else:
            print(f"  {fmt.upper()} export failed: {export_data.get('error', 'unknown')}")

    gen_result["exports"] = exports
    return gen_result


def download_file(url, output_path):
    """Download a file from a presigned URL."""
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    with open(output_path, "wb") as f:
        f.write(resp.content)
    print(f"  Downloaded: {output_path} ({len(resp.content) / 1024:.0f} KB)")


def main():
    if not API_KEY:
        print("Error: Set DOCSIE_API_KEY environment variable")
        sys.exit(1)

    if len(sys.argv) < 2:
        print("Usage: python video_to_docs.py <video_file_or_url>")
        sys.exit(1)

    source = sys.argv[1]
    doc_style = sys.argv[2] if len(sys.argv) > 2 else "guide"

    # Determine if source is a file or URL
    if os.path.isfile(source):
        file_id = upload_file(source)
        job_id = submit_video(file_id=file_id, doc_style=doc_style)
    else:
        job_id = submit_video(video_url=source, doc_style=doc_style)

    # Wait for analysis
    analysis = wait_for_analysis(job_id)

    # Save raw analysis
    with open("analysis_result.md", "w") as f:
        f.write(analysis.get("markdown", ""))
    print(f"Saved raw analysis to analysis_result.md")

    if analysis.get("transcription"):
        with open("transcription.txt", "w") as f:
            f.write(analysis["transcription"])
        print(f"Saved transcription to transcription.txt")

    # Generate polished docs
    gen_result = generate_docs(
        job_id,
        doc_style=doc_style,
        output_formats=["md", "docx", "pdf"],
    )

    # Save rewritten markdown
    if gen_result.get("markdown"):
        with open("generated.md", "w") as f:
            f.write(gen_result["markdown"])
        print(f"Saved rewritten markdown to generated.md")

    # Download exports
    exports = gen_result.get("exports", {})
    for fmt in ("docx", "pdf"):
        url = exports.get(fmt, {}).get("url")
        filename = exports.get(fmt, {}).get("filename", f"output.{fmt}")
        if url:
            download_file(url, filename)

    print("\nDone!")


if __name__ == "__main__":
    main()
