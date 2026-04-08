#!/usr/bin/env ruby
#
# Video-to-Docs: Full pipeline example (Ruby)
#
# Submits a video, polls for analysis, triggers AI rewrite,
# and downloads the result as markdown, DOCX, and PDF.
#
# Usage:
#   export DOCSIE_API_KEY="your_key"
#   ruby video_to_docs.rb https://example.com/video.mp4
#   ruby video_to_docs.rb https://example.com/video.mp4 sop

require "net/http"
require "json"
require "uri"

API_KEY = ENV.fetch("DOCSIE_API_KEY") { abort "Error: Set DOCSIE_API_KEY" }
BASE_URL = ENV.fetch("DOCSIE_BASE_URL", "https://app.docsie.io")
API = "#{BASE_URL}/api_v2/003"

def api_request(method, path, body = nil)
  uri = URI("#{API}#{path}")
  http = Net::HTTP.new(uri.host, uri.port)
  http.use_ssl = uri.scheme == "https"
  http.open_timeout = 30
  http.read_timeout = 60

  req = case method
        when :get  then Net::HTTP::Get.new(uri)
        when :post then Net::HTTP::Post.new(uri)
        end

  req["Authorization"] = "Api-Key #{API_KEY}"
  req["Content-Type"] = "application/json"
  req["Accept"] = "application/json"
  req.body = body.to_json if body

  resp = http.request(req)
  JSON.parse(resp.body)
end

def poll(path, timeout: 900, interval: 15)
  deadline = Time.now + timeout
  while Time.now < deadline
    data = api_request(:get, path)
    status = data["status"] || data["job_status"] || ""
    return data if %w[done failed canceled].include?(status)
    puts "  ... #{status}"
    sleep interval
  end
  raise "Timed out after #{timeout}s"
end

def download(url, filename)
  uri = URI(url)
  resp = Net::HTTP.get_response(uri)
  # Follow redirects
  if resp.is_a?(Net::HTTPRedirection)
    resp = Net::HTTP.get_response(URI(resp["location"]))
  end
  File.binwrite(filename, resp.body)
  puts "  Downloaded: #{filename} (#{resp.body.size / 1024} KB)"
end

# ── Main ──────────────────────────────────────────────────

video_url = ARGV[0] || abort("Usage: ruby video_to_docs.rb <video_url> [doc_style]")
doc_style = ARGV[1] || "guide"

# 1. Submit
puts "==> Submitting video job (style=#{doc_style})..."
submit = api_request(:post, "/video-to-docs/submit/", {
  video_url: video_url,
  quality: "draft",
  language: "english",
  doc_style: doc_style,
  auto_generate: false,
})
job_id = submit["job_id"]
puts "    Job ID: #{job_id}"

# 2. Poll analysis
puts "==> Polling analysis..."
poll("/video-to-docs/#{job_id}/status/")

# 3. Get result
puts "==> Fetching result..."
result = api_request(:get, "/video-to-docs/#{job_id}/result/")
puts "    Markdown: #{(result["markdown"] || "").length} chars"
puts "    Transcription: #{(result["transcription"] || "").length} chars"
puts "    Sections: #{(result["sections"] || []).length}"
puts "    Images: #{(result["images"] || []).length}"

File.write("analysis_result.md", result["markdown"] || "")
File.write("transcription.txt", result["transcription"] || "")
puts "    Saved: analysis_result.md, transcription.txt"

# 4. Generate
puts "==> Triggering AI rewrite..."
gen = api_request(:post, "/video-to-docs/#{job_id}/generate/", {
  doc_style: doc_style,
  output_formats: %w[md docx pdf],
})
gen_job_id = gen["generate_job_id"]
puts "    Generate job: #{gen_job_id}"

puts "==> Polling generate job..."
gen_result = poll("/jobs/#{gen_job_id}/", timeout: 300, interval: 10)
gen_data = gen_result["result"] || {}
puts "    Title: #{gen_data["title"]}"
puts "    Words: #{gen_data["input_word_count"]} -> #{gen_data["output_word_count"]}"

File.write("generated.md", gen_data["markdown"] || "")
puts "    Saved: generated.md"

# 5. Download exports
exports = gen_data["exports"] || {}
%w[docx pdf].each do |fmt|
  export_job_id = (exports[fmt] || {})["job_id"]
  next unless export_job_id

  puts "==> Waiting for #{fmt.upcase} export..."
  export_result = poll("/jobs/#{export_job_id}/", timeout: 120, interval: 5)
  export_data = export_result["result"] || {}
  if export_data["url"]
    download(export_data["url"], export_data["filename"] || "output.#{fmt}")
  end
end

puts "\n==> Complete!"
