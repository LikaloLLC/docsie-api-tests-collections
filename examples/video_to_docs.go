// Video-to-Docs: Full pipeline example (Go)
//
// Submits a video URL, polls for analysis, triggers AI rewrite,
// and downloads the result as markdown, DOCX, and PDF.
//
// Usage:
//
//	export DOCSIE_API_KEY="your_key"
//	go run video_to_docs.go https://example.com/video.mp4
//	go run video_to_docs.go https://example.com/video.mp4 sop
package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"time"
)

var (
	apiKey  = os.Getenv("DOCSIE_API_KEY")
	baseURL = envOrDefault("DOCSIE_BASE_URL", "https://app.docsie.io")
	api     = baseURL + "/api_v2/003"
	client  = &http.Client{Timeout: 60 * time.Second}
)

func envOrDefault(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

// ── HTTP helpers ─────────────────────────────────────────

func apiRequest(method, path string, body interface{}) (map[string]interface{}, error) {
	var reqBody io.Reader
	if body != nil {
		b, _ := json.Marshal(body)
		reqBody = bytes.NewReader(b)
	}
	req, err := http.NewRequest(method, api+path, reqBody)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Authorization", "Api-Key "+apiKey)
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")

	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	var result map[string]interface{}
	json.NewDecoder(resp.Body).Decode(&result)
	return result, nil
}

func apiGet(path string) (map[string]interface{}, error) {
	return apiRequest("GET", path, nil)
}

func apiPost(path string, body map[string]interface{}) (map[string]interface{}, error) {
	return apiRequest("POST", path, body)
}

func poll(path string, timeoutSec, intervalSec int) (map[string]interface{}, error) {
	deadline := time.Now().Add(time.Duration(timeoutSec) * time.Second)
	for time.Now().Before(deadline) {
		data, err := apiGet(path)
		if err != nil {
			return nil, err
		}
		status := str(data, "status")
		if status == "" {
			status = str(data, "job_status")
		}
		switch status {
		case "done", "failed", "canceled":
			return data, nil
		}
		fmt.Printf("  ... %s\n", status)
		time.Sleep(time.Duration(intervalSec) * time.Second)
	}
	return nil, fmt.Errorf("timed out after %ds", timeoutSec)
}

func downloadFile(url, filename string) error {
	resp, err := http.Get(url)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	f, err := os.Create(filename)
	if err != nil {
		return err
	}
	defer f.Close()

	n, _ := io.Copy(f, resp.Body)
	fmt.Printf("  Downloaded: %s (%d KB)\n", filename, n/1024)
	return nil
}

func str(m map[string]interface{}, key string) string {
	if v, ok := m[key]; ok && v != nil {
		return fmt.Sprintf("%v", v)
	}
	return ""
}

func objMap(m map[string]interface{}, key string) map[string]interface{} {
	if v, ok := m[key].(map[string]interface{}); ok {
		return v
	}
	return map[string]interface{}{}
}

func arrLen(m map[string]interface{}, key string) int {
	if v, ok := m[key].([]interface{}); ok {
		return len(v)
	}
	return 0
}

// ── Main ─────────────────────────────────────────────────

func main() {
	if apiKey == "" {
		fmt.Fprintln(os.Stderr, "Error: Set DOCSIE_API_KEY environment variable")
		os.Exit(1)
	}
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "Usage: go run video_to_docs.go <video_url> [doc_style]")
		os.Exit(1)
	}

	videoURL := os.Args[1]
	docStyle := "guide"
	if len(os.Args) > 2 {
		docStyle = os.Args[2]
	}

	// 1. Submit
	fmt.Printf("==> Submitting video job (style=%s)...\n", docStyle)
	submitResp, err := apiPost("/video-to-docs/submit/", map[string]interface{}{
		"video_url":     videoURL,
		"quality":       "draft",
		"language":      "english",
		"doc_style":     docStyle,
		"auto_generate": false,
	})
	check(err)
	jobID := str(submitResp, "job_id")
	fmt.Printf("    Job ID: %s\n", jobID)

	// 2. Poll analysis
	fmt.Println("==> Polling analysis...")
	_, err = poll("/video-to-docs/"+jobID+"/status/", 900, 15)
	check(err)

	// 3. Get result
	fmt.Println("==> Fetching result...")
	result, err := apiGet("/video-to-docs/" + jobID + "/result/")
	check(err)
	markdown := str(result, "markdown")
	transcription := str(result, "transcription")
	fmt.Printf("    Markdown: %d chars\n", len(markdown))
	fmt.Printf("    Transcription: %d chars\n", len(transcription))
	fmt.Printf("    Sections: %d\n", arrLen(result, "sections"))
	fmt.Printf("    Images: %d\n", arrLen(result, "images"))

	os.WriteFile("analysis_result.md", []byte(markdown), 0644)
	os.WriteFile("transcription.txt", []byte(transcription), 0644)
	fmt.Println("    Saved: analysis_result.md, transcription.txt")

	// 4. Generate
	fmt.Println("==> Triggering AI rewrite...")
	genResp, err := apiPost("/video-to-docs/"+jobID+"/generate/", map[string]interface{}{
		"doc_style":      docStyle,
		"output_formats": []string{"md", "docx", "pdf"},
	})
	check(err)
	genJobID := str(genResp, "generate_job_id")
	fmt.Printf("    Generate job: %s\n", genJobID)

	fmt.Println("==> Polling generate job...")
	genResult, err := poll("/jobs/"+genJobID+"/", 300, 10)
	check(err)
	gen := objMap(genResult, "result")
	fmt.Printf("    Title: %s\n", str(gen, "title"))
	fmt.Printf("    Words: %s -> %s\n", str(gen, "input_word_count"), str(gen, "output_word_count"))

	os.WriteFile("generated.md", []byte(str(gen, "markdown")), 0644)
	fmt.Println("    Saved: generated.md")

	// 5. Download exports
	exports := objMap(gen, "exports")
	for _, fmt_ := range []string{"docx", "pdf"} {
		info := objMap(exports, fmt_)
		exportJobID := str(info, "job_id")
		if exportJobID == "" {
			continue
		}
		fmt.Printf("==> Waiting for %s export...\n", fmt_)
		exportResult, err := poll("/jobs/"+exportJobID+"/", 120, 5)
		check(err)
		exportData := objMap(exportResult, "result")
		url := str(exportData, "url")
		filename := str(exportData, "filename")
		if filename == "" {
			filename = "output." + fmt_
		}
		if url != "" {
			downloadFile(url, filename)
		}
	}

	fmt.Println("\n==> Complete!")
}

func check(err error) {
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}
}
