/**
 * Video-to-Docs: Full pipeline example (Java 11+)
 *
 * Submits a video URL, polls for analysis, triggers AI rewrite,
 * and downloads the result as markdown, DOCX, and PDF.
 *
 * Dependencies: com.google.code.gson:gson:2.11.0
 *
 * Compile & run:
 *   # Download gson jar (or use Maven/Gradle)
 *   curl -sL -o gson.jar https://repo1.maven.org/maven2/com/google/code/gson/gson/2.11.0/gson-2.11.0.jar
 *   export DOCSIE_API_KEY="your_key"
 *   javac -cp gson.jar video_to_docs.java
 *   java -cp .:gson.jar video_to_docs https://example.com/video.mp4
 *   java -cp .:gson.jar video_to_docs https://example.com/video.mp4 sop
 *
 * Or with Maven:
 *   <dependency>
 *     <groupId>com.google.code.gson</groupId>
 *     <artifactId>gson</artifactId>
 *     <version>2.11.0</version>
 *   </dependency>
 */

import com.google.gson.Gson;
import com.google.gson.JsonObject;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;

import java.io.*;
import java.net.URI;
import java.net.http.*;
import java.nio.file.*;
import java.time.Duration;
import java.util.*;

public class video_to_docs {

    static final String API_KEY = System.getenv("DOCSIE_API_KEY");
    static final String BASE_URL = Optional.ofNullable(System.getenv("DOCSIE_BASE_URL"))
            .orElse("https://app.docsie.io");
    static final String API = BASE_URL + "/api_v2/003";
    static final HttpClient client = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(30))
            .build();
    static final Gson gson = new Gson();

    public static void main(String[] args) throws Exception {
        if (API_KEY == null || API_KEY.isEmpty()) {
            System.err.println("Error: Set DOCSIE_API_KEY environment variable");
            System.exit(1);
        }
        if (args.length < 1) {
            System.err.println("Usage: java video_to_docs <video_url> [doc_style]");
            System.exit(1);
        }

        String videoUrl = args[0];
        String docStyle = args.length > 1 ? args[1] : "guide";

        // 1. Submit
        System.out.printf("==> Submitting video job (style=%s)...%n", docStyle);
        JsonObject submitBody = new JsonObject();
        submitBody.addProperty("video_url", videoUrl);
        submitBody.addProperty("quality", "draft");
        submitBody.addProperty("language", "english");
        submitBody.addProperty("doc_style", docStyle);
        submitBody.addProperty("auto_generate", false);

        JsonObject submitResp = apiPost("/video-to-docs/submit/", submitBody);
        String jobId = submitResp.get("job_id").getAsString();
        System.out.printf("    Job ID: %s%n", jobId);

        // 2. Poll analysis
        System.out.println("==> Polling analysis...");
        poll("/video-to-docs/" + jobId + "/status/", 900, 15);

        // 3. Get result
        System.out.println("==> Fetching result...");
        JsonObject result = apiGet("/video-to-docs/" + jobId + "/result/");
        String markdown = getStr(result, "markdown");
        String transcription = getStr(result, "transcription");
        int sectionCount = result.has("sections") ? result.getAsJsonArray("sections").size() : 0;
        int imageCount = result.has("images") ? result.getAsJsonArray("images").size() : 0;

        System.out.printf("    Markdown: %d chars%n", markdown.length());
        System.out.printf("    Transcription: %d chars%n", transcription.length());
        System.out.printf("    Sections: %d%n", sectionCount);
        System.out.printf("    Images: %d%n", imageCount);

        Files.writeString(Path.of("analysis_result.md"), markdown);
        Files.writeString(Path.of("transcription.txt"), transcription);
        System.out.println("    Saved: analysis_result.md, transcription.txt");

        // 4. Generate
        System.out.println("==> Triggering AI rewrite...");
        JsonObject genBody = new JsonObject();
        genBody.addProperty("doc_style", docStyle);
        JsonArray formats = new JsonArray();
        formats.add("md"); formats.add("docx"); formats.add("pdf");
        genBody.add("output_formats", formats);

        JsonObject genResp = apiPost("/video-to-docs/" + jobId + "/generate/", genBody);
        String genJobId = genResp.get("generate_job_id").getAsString();
        System.out.printf("    Generate job: %s%n", genJobId);

        System.out.println("==> Polling generate job...");
        JsonObject genResult = poll("/jobs/" + genJobId + "/", 300, 10);
        JsonObject gen = genResult.has("result") ? genResult.getAsJsonObject("result") : new JsonObject();

        System.out.printf("    Title: %s%n", getStr(gen, "title"));
        System.out.printf("    Words: %s -> %s%n",
                gen.has("input_word_count") ? gen.get("input_word_count").getAsString() : "?",
                gen.has("output_word_count") ? gen.get("output_word_count").getAsString() : "?");

        Files.writeString(Path.of("generated.md"), getStr(gen, "markdown"));
        System.out.println("    Saved: generated.md");

        // 5. Download exports
        JsonObject exports = gen.has("exports") ? gen.getAsJsonObject("exports") : new JsonObject();
        for (String fmt : List.of("docx", "pdf")) {
            if (!exports.has(fmt)) continue;
            JsonObject info = exports.getAsJsonObject(fmt);
            String exportJobId = getStr(info, "job_id");
            if (exportJobId.isEmpty()) continue;

            System.out.printf("==> Waiting for %s export...%n", fmt.toUpperCase());
            JsonObject exportResult = poll("/jobs/" + exportJobId + "/", 120, 5);
            JsonObject exportData = exportResult.has("result")
                    ? exportResult.getAsJsonObject("result") : new JsonObject();
            String url = getStr(exportData, "url");
            String filename = getStr(exportData, "filename");
            if (filename.isEmpty()) filename = "output." + fmt;
            if (!url.isEmpty()) {
                downloadFile(url, filename);
            }
        }

        System.out.println("\n==> Complete!");
    }

    // ── HTTP helpers ─────────────────────────────────────

    static JsonObject apiGet(String path) throws Exception {
        HttpRequest req = HttpRequest.newBuilder()
                .uri(URI.create(API + path))
                .header("Authorization", "Api-Key " + API_KEY)
                .header("Accept", "application/json")
                .timeout(Duration.ofSeconds(60))
                .GET().build();
        String body = client.send(req, HttpResponse.BodyHandlers.ofString()).body();
        return gson.fromJson(body, JsonObject.class);
    }

    static JsonObject apiPost(String path, JsonObject body) throws Exception {
        HttpRequest req = HttpRequest.newBuilder()
                .uri(URI.create(API + path))
                .header("Authorization", "Api-Key " + API_KEY)
                .header("Content-Type", "application/json")
                .header("Accept", "application/json")
                .timeout(Duration.ofSeconds(60))
                .POST(HttpRequest.BodyPublishers.ofString(gson.toJson(body))).build();
        String resp = client.send(req, HttpResponse.BodyHandlers.ofString()).body();
        return gson.fromJson(resp, JsonObject.class);
    }

    static JsonObject poll(String path, int timeoutSec, int intervalSec) throws Exception {
        long deadline = System.currentTimeMillis() + timeoutSec * 1000L;
        while (System.currentTimeMillis() < deadline) {
            JsonObject data = apiGet(path);
            String status = getStr(data, "status");
            if (status.isEmpty()) status = getStr(data, "job_status");
            if (List.of("done", "failed", "canceled").contains(status)) return data;
            System.out.printf("  ... %s%n", status);
            Thread.sleep(intervalSec * 1000L);
        }
        throw new RuntimeException("Timed out after " + timeoutSec + "s");
    }

    static void downloadFile(String url, String filename) throws Exception {
        HttpRequest req = HttpRequest.newBuilder().uri(URI.create(url))
                .timeout(Duration.ofSeconds(60)).GET().build();
        byte[] bytes = client.send(req, HttpResponse.BodyHandlers.ofByteArray()).body();
        Files.write(Path.of(filename), bytes);
        System.out.printf("  Downloaded: %s (%d KB)%n", filename, bytes.length / 1024);
    }

    static String getStr(JsonObject obj, String key) {
        JsonElement el = obj.get(key);
        if (el == null || el.isJsonNull()) return "";
        return el.isJsonPrimitive() ? el.getAsString() : el.toString();
    }
}
