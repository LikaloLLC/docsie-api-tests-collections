/**
 * Video-to-Docs: Full pipeline example (Node.js)
 *
 * Submits a video, polls for analysis, triggers AI rewrite,
 * and downloads the result as markdown, DOCX, and PDF.
 *
 * Usage:
 *   export DOCSIE_API_KEY="your_key"
 *   node video_to_docs.js https://example.com/video.mp4
 *   node video_to_docs.js https://example.com/video.mp4 sop
 */

const fs = require("fs");
const https = require("https");
const http = require("http");

const API_KEY = process.env.DOCSIE_API_KEY;
const BASE_URL = process.env.DOCSIE_BASE_URL || "https://app.docsie.io";
const API = `${BASE_URL}/api_v2/003`;

if (!API_KEY) {
  console.error("Error: Set DOCSIE_API_KEY environment variable");
  process.exit(1);
}

// ── HTTP helpers ─────────────────────────────────────────

function request(method, path, body = null) {
  return new Promise((resolve, reject) => {
    const url = new URL(`${API}${path}`);
    const mod = url.protocol === "https:" ? https : http;
    const options = {
      method,
      hostname: url.hostname,
      port: url.port,
      path: url.pathname + url.search,
      headers: {
        Authorization: `Api-Key ${API_KEY}`,
        Accept: "application/json",
        "Content-Type": "application/json",
      },
    };

    const req = mod.request(options, (res) => {
      let data = "";
      res.on("data", (chunk) => (data += chunk));
      res.on("end", () => {
        try {
          resolve({ status: res.statusCode, data: JSON.parse(data) });
        } catch {
          resolve({ status: res.statusCode, data });
        }
      });
    });
    req.on("error", reject);
    if (body) req.write(JSON.stringify(body));
    req.end();
  });
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function poll(path, { timeout = 900000, interval = 15000 } = {}) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    const { data } = await request("GET", path);
    const status = data.status || data.job_status || "";
    if (["done", "failed", "canceled"].includes(status)) return data;
    process.stdout.write(`  ... ${status}\n`);
    await sleep(interval);
  }
  throw new Error(`Timed out after ${timeout / 1000}s`);
}

function downloadFile(url, outputPath) {
  return new Promise((resolve, reject) => {
    const mod = url.startsWith("https") ? https : http;
    mod.get(url, (res) => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        return downloadFile(res.headers.location, outputPath).then(resolve).catch(reject);
      }
      const ws = fs.createWriteStream(outputPath);
      res.pipe(ws);
      ws.on("finish", () => {
        ws.close();
        const size = fs.statSync(outputPath).size;
        console.log(`  Downloaded: ${outputPath} (${(size / 1024).toFixed(0)} KB)`);
        resolve();
      });
    }).on("error", reject);
  });
}

// ── Pipeline ─────────────────────────────────────────────

async function main() {
  const videoUrl = process.argv[2];
  const docStyle = process.argv[3] || "guide";

  if (!videoUrl) {
    console.error("Usage: node video_to_docs.js <video_url> [doc_style]");
    process.exit(1);
  }

  // 1. Submit
  console.log(`==> Submitting video job (style=${docStyle})...`);
  const { data: submitData } = await request("POST", "/video-to-docs/submit/", {
    video_url: videoUrl,
    quality: "draft",
    language: "english",
    doc_style: docStyle,
    auto_generate: false,
  });
  const jobId = submitData.job_id;
  console.log(`    Job ID: ${jobId}`);

  // 2. Poll analysis
  console.log("==> Polling analysis...");
  await poll(`/video-to-docs/${jobId}/status/`);

  // 3. Get result
  console.log("==> Fetching result...");
  const { data: result } = await request("GET", `/video-to-docs/${jobId}/result/`);
  console.log(`    Markdown: ${(result.markdown || "").length} chars`);
  console.log(`    Transcription: ${(result.transcription || "").length} chars`);
  console.log(`    Sections: ${(result.sections || []).length}`);
  console.log(`    Images: ${(result.images || []).length}`);

  fs.writeFileSync("analysis_result.md", result.markdown || "");
  if (result.transcription) fs.writeFileSync("transcription.txt", result.transcription);
  console.log("    Saved: analysis_result.md, transcription.txt");

  // 4. Generate
  console.log("==> Triggering AI rewrite...");
  const { data: genData } = await request("POST", `/video-to-docs/${jobId}/generate/`, {
    doc_style: docStyle,
    output_formats: ["md", "docx", "pdf"],
  });
  const genJobId = genData.generate_job_id;
  console.log(`    Generate job: ${genJobId}`);

  console.log("==> Polling generate job...");
  const genResult = await poll(`/jobs/${genJobId}/`, { timeout: 300000, interval: 10000 });
  const gen = genResult.result || {};

  console.log(`    Title: ${gen.title}`);
  console.log(`    Words: ${gen.input_word_count} -> ${gen.output_word_count}`);
  fs.writeFileSync("generated.md", gen.markdown || "");
  console.log("    Saved: generated.md");

  // 5. Download exports
  const exports = gen.exports || {};
  for (const fmt of ["docx", "pdf"]) {
    const exportJobId = (exports[fmt] || {}).job_id;
    if (!exportJobId) continue;

    console.log(`==> Waiting for ${fmt.toUpperCase()} export...`);
    const exportResult = await poll(`/jobs/${exportJobId}/`, {
      timeout: 120000,
      interval: 5000,
    });
    const exportData = exportResult.result || {};
    if (exportData.url) {
      await downloadFile(exportData.url, exportData.filename || `output.${fmt}`);
    }
  }

  console.log("\n==> Complete!");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
