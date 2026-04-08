<?php
/**
 * Video-to-Docs: Full pipeline example (PHP)
 *
 * Submits a video, polls for analysis, triggers AI rewrite,
 * and downloads the result as markdown, DOCX, and PDF.
 *
 * Usage:
 *   export DOCSIE_API_KEY="your_key"
 *   php video_to_docs.php https://example.com/video.mp4
 *   php video_to_docs.php https://example.com/video.mp4 sop
 */

$API_KEY = getenv('DOCSIE_API_KEY') ?: die("Error: Set DOCSIE_API_KEY\n");
$BASE_URL = getenv('DOCSIE_BASE_URL') ?: 'https://app.docsie.io';
$API = "{$BASE_URL}/api_v2/003";

function api_request(string $method, string $path, ?array $body = null): array {
    global $API, $API_KEY;

    $opts = [
        'http' => [
            'method' => strtoupper($method),
            'header' => implode("\r\n", [
                "Authorization: Api-Key {$API_KEY}",
                'Content-Type: application/json',
                'Accept: application/json',
            ]),
            'timeout' => 60,
            'ignore_errors' => true,
        ],
    ];

    if ($body !== null) {
        $opts['http']['content'] = json_encode($body);
    }

    $context = stream_context_create($opts);
    $response = file_get_contents("{$API}{$path}", false, $context);

    return json_decode($response, true) ?: [];
}

function poll(string $path, int $timeout = 900, int $interval = 15): array {
    $deadline = time() + $timeout;
    while (time() < $deadline) {
        $data = api_request('GET', $path);
        $status = $data['status'] ?? $data['job_status'] ?? '';
        if (in_array($status, ['done', 'failed', 'canceled'])) {
            return $data;
        }
        echo "  ... {$status}\n";
        sleep($interval);
    }
    throw new RuntimeException("Timed out after {$timeout}s");
}

// ── Main ─────────────────────────────────────────────────

$videoUrl = $argv[1] ?? die("Usage: php video_to_docs.php <video_url> [doc_style]\n");
$docStyle = $argv[2] ?? 'guide';

// 1. Submit
echo "==> Submitting video job (style={$docStyle})...\n";
$submit = api_request('POST', '/video-to-docs/submit/', [
    'video_url' => $videoUrl,
    'quality' => 'draft',
    'language' => 'english',
    'doc_style' => $docStyle,
    'auto_generate' => false,
]);
$jobId = $submit['job_id'];
echo "    Job ID: {$jobId}\n";

// 2. Poll analysis
echo "==> Polling analysis...\n";
poll("/video-to-docs/{$jobId}/status/");

// 3. Get result
echo "==> Fetching result...\n";
$result = api_request('GET', "/video-to-docs/{$jobId}/result/");
$md = $result['markdown'] ?? '';
$transcript = $result['transcription'] ?? '';
echo "    Markdown: " . strlen($md) . " chars\n";
echo "    Transcription: " . strlen($transcript) . " chars\n";
echo "    Sections: " . count($result['sections'] ?? []) . "\n";
echo "    Images: " . count($result['images'] ?? []) . "\n";

file_put_contents('analysis_result.md', $md);
file_put_contents('transcription.txt', $transcript);
echo "    Saved: analysis_result.md, transcription.txt\n";

// 4. Generate
echo "==> Triggering AI rewrite...\n";
$gen = api_request('POST', "/video-to-docs/{$jobId}/generate/", [
    'doc_style' => $docStyle,
    'output_formats' => ['md', 'docx', 'pdf'],
]);
$genJobId = $gen['generate_job_id'];
echo "    Generate job: {$genJobId}\n";

echo "==> Polling generate job...\n";
$genResult = poll("/jobs/{$genJobId}/", 300, 10);
$genData = $genResult['result'] ?? [];
echo "    Title: " . ($genData['title'] ?? '') . "\n";
echo "    Words: " . ($genData['input_word_count'] ?? 0) . " -> " . ($genData['output_word_count'] ?? 0) . "\n";

file_put_contents('generated.md', $genData['markdown'] ?? '');
echo "    Saved: generated.md\n";

// 5. Download exports
$exports = $genData['exports'] ?? [];
foreach (['docx', 'pdf'] as $fmt) {
    $exportJobId = $exports[$fmt]['job_id'] ?? null;
    if (!$exportJobId) continue;

    echo "==> Waiting for " . strtoupper($fmt) . " export...\n";
    $exportResult = poll("/jobs/{$exportJobId}/", 120, 5);
    $exportData = $exportResult['result'] ?? [];
    $url = $exportData['url'] ?? '';
    $filename = $exportData['filename'] ?? "output.{$fmt}";
    if ($url) {
        file_put_contents($filename, file_get_contents($url));
        echo "    Downloaded: {$filename} (" . round(filesize($filename) / 1024) . " KB)\n";
    }
}

echo "\n==> Complete!\n";
