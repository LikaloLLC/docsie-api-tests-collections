// Video-to-Docs: Full pipeline example (C# / .NET 6+)
//
// Submits a video URL, polls for analysis, triggers AI rewrite,
// and downloads the result as markdown, DOCX, and PDF.
//
// Usage:
//   export DOCSIE_API_KEY="your_key"
//   dotnet script video_to_docs.cs https://example.com/video.mp4
//
// Or create a project:
//   dotnet new console -n VideoToDocs
//   cp video_to_docs.cs VideoToDocs/Program.cs
//   cd VideoToDocs && dotnet run -- https://example.com/video.mp4 sop

using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;

var apiKey = Environment.GetEnvironmentVariable("DOCSIE_API_KEY")
    ?? throw new Exception("Set DOCSIE_API_KEY environment variable");
var baseUrl = Environment.GetEnvironmentVariable("DOCSIE_BASE_URL") ?? "https://app.docsie.io";
var api = $"{baseUrl}/api_v2/003";

if (args.Length < 1) { Console.Error.WriteLine("Usage: dotnet run -- <video_url> [doc_style]"); return; }

var videoUrl = args[0];
var docStyle = args.Length > 1 ? args[1] : "guide";

using var client = new HttpClient { Timeout = TimeSpan.FromSeconds(60) };
client.DefaultRequestHeaders.Add("Authorization", $"Api-Key {apiKey}");
client.DefaultRequestHeaders.Accept.Add(new MediaTypeWithQualityHeaderValue("application/json"));

// ── Helpers ──────────────────────────────────────────────

async Task<JsonElement> ApiGet(string path)
{
    var resp = await client.GetStringAsync($"{api}{path}");
    return JsonDocument.Parse(resp).RootElement;
}

async Task<JsonElement> ApiPost(string path, object body)
{
    var json = JsonSerializer.Serialize(body);
    var content = new StringContent(json, Encoding.UTF8, "application/json");
    var resp = await client.PostAsync($"{api}{path}", content);
    var text = await resp.Content.ReadAsStringAsync();
    return JsonDocument.Parse(text).RootElement;
}

async Task<JsonElement> Poll(string path, int timeoutSec = 900, int intervalSec = 15)
{
    var deadline = DateTime.UtcNow.AddSeconds(timeoutSec);
    while (DateTime.UtcNow < deadline)
    {
        var data = await ApiGet(path);
        var status = Str(data, "status");
        if (string.IsNullOrEmpty(status)) status = Str(data, "job_status");
        if (status is "done" or "failed" or "canceled") return data;
        Console.WriteLine($"  ... {status}");
        await Task.Delay(intervalSec * 1000);
    }
    throw new TimeoutException($"Timed out after {timeoutSec}s");
}

string Str(JsonElement el, string key)
{
    if (el.TryGetProperty(key, out var val) && val.ValueKind != JsonValueKind.Null)
        return val.ToString();
    return "";
}

JsonElement Obj(JsonElement el, string key)
{
    if (el.TryGetProperty(key, out var val) && val.ValueKind == JsonValueKind.Object)
        return val;
    return JsonDocument.Parse("{}").RootElement;
}

int ArrLen(JsonElement el, string key)
{
    if (el.TryGetProperty(key, out var val) && val.ValueKind == JsonValueKind.Array)
        return val.GetArrayLength();
    return 0;
}

// ── Pipeline ─────────────────────────────────────────────

// 1. Submit
Console.WriteLine($"==> Submitting video job (style={docStyle})...");
var submitResp = await ApiPost("/video-to-docs/submit/", new
{
    video_url = videoUrl,
    quality = "draft",
    language = "english",
    doc_style = docStyle,
    auto_generate = false,
});
var jobId = Str(submitResp, "job_id");
Console.WriteLine($"    Job ID: {jobId}");

// 2. Poll analysis
Console.WriteLine("==> Polling analysis...");
await Poll($"/video-to-docs/{jobId}/status/");

// 3. Get result
Console.WriteLine("==> Fetching result...");
var result = await ApiGet($"/video-to-docs/{jobId}/result/");
var markdown = Str(result, "markdown");
var transcription = Str(result, "transcription");
Console.WriteLine($"    Markdown: {markdown.Length} chars");
Console.WriteLine($"    Transcription: {transcription.Length} chars");
Console.WriteLine($"    Sections: {ArrLen(result, "sections")}");
Console.WriteLine($"    Images: {ArrLen(result, "images")}");

await File.WriteAllTextAsync("analysis_result.md", markdown);
await File.WriteAllTextAsync("transcription.txt", transcription);
Console.WriteLine("    Saved: analysis_result.md, transcription.txt");

// 4. Generate
Console.WriteLine("==> Triggering AI rewrite...");
var genResp = await ApiPost($"/video-to-docs/{jobId}/generate/", new
{
    doc_style = docStyle,
    output_formats = new[] { "md", "docx", "pdf" },
});
var genJobId = Str(genResp, "generate_job_id");
Console.WriteLine($"    Generate job: {genJobId}");

Console.WriteLine("==> Polling generate job...");
var genResult = await Poll($"/jobs/{genJobId}/", 300, 10);
var gen = Obj(genResult, "result");
Console.WriteLine($"    Title: {Str(gen, "title")}");
Console.WriteLine($"    Words: {Str(gen, "input_word_count")} -> {Str(gen, "output_word_count")}");

await File.WriteAllTextAsync("generated.md", Str(gen, "markdown"));
Console.WriteLine("    Saved: generated.md");

// 5. Download exports
var exports = Obj(gen, "exports");
foreach (var fmt in new[] { "docx", "pdf" })
{
    var info = Obj(exports, fmt);
    var exportJobId = Str(info, "job_id");
    if (string.IsNullOrEmpty(exportJobId)) continue;

    Console.WriteLine($"==> Waiting for {fmt.ToUpper()} export...");
    var exportResult = await Poll($"/jobs/{exportJobId}/", 120, 5);
    var exportData = Obj(exportResult, "result");
    var url = Str(exportData, "url");
    var filename = Str(exportData, "filename");
    if (string.IsNullOrEmpty(filename)) filename = $"output.{fmt}";
    if (!string.IsNullOrEmpty(url))
    {
        var bytes = await client.GetByteArrayAsync(url);
        await File.WriteAllBytesAsync(filename, bytes);
        Console.WriteLine($"  Downloaded: {filename} ({bytes.Length / 1024} KB)");
    }
}

Console.WriteLine("\n==> Complete!");
