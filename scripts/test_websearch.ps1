$BASE = "https://tillu-ai-tillu-websearch.hf.space"

Write-Host ""
Write-Host "=== TILLU WebSearch Test Suite ===" -ForegroundColor Cyan

# 1. Health
Write-Host ""
Write-Host "[1] GET /health" -ForegroundColor Yellow
$r = Invoke-RestMethod -Uri "$BASE/health" -Method GET
$r | ConvertTo-Json

# 2. Status
Write-Host ""
Write-Host "[2] GET /status" -ForegroundColor Yellow
$r = Invoke-RestMethod -Uri "$BASE/status" -Method GET
$r | ConvertTo-Json

# 3. English search
Write-Host ""
Write-Host "[3] POST /search  (English)" -ForegroundColor Yellow
$body = @{ query = "latest AI news 2025"; lang = "en"; max_results = 3 } | ConvertTo-Json
$r = Invoke-RestMethod -Uri "$BASE/search" -Method POST -ContentType "application/json" -Body $body
Write-Host "Source: $($r.source)  |  Results: $($r.total)"
foreach ($item in $r.results) {
    Write-Host "  - $($item.title)"
    Write-Host "    $($item.url)"
}

# 4. Hindi search
Write-Host ""
Write-Host "[4] POST /search  (Hindi)" -ForegroundColor Yellow
$body = @{ query = "aaj ka mausam Delhi"; lang = "hi"; max_results = 3 } | ConvertTo-Json
$r = Invoke-RestMethod -Uri "$BASE/search" -Method POST -ContentType "application/json" -Body $body
Write-Host "Source: $($r.source)  |  Lang: $($r.lang)  |  Results: $($r.total)"
foreach ($item in $r.results) {
    Write-Host "  - $($item.title)"
}

# 5. Auto-detect language
Write-Host ""
Write-Host "[5] POST /search  (lang=auto)" -ForegroundColor Yellow
$body = @{ query = "Python FastAPI tutorial"; lang = "auto"; max_results = 3 } | ConvertTo-Json
$r = Invoke-RestMethod -Uri "$BASE/search" -Method POST -ContentType "application/json" -Body $body
Write-Host "Detected lang: $($r.lang)  |  Source: $($r.source)  |  Results: $($r.total)"
foreach ($item in $r.results) {
    Write-Host "  - $($item.title)"
}

# 6. Scrape
Write-Host ""
Write-Host "[6] POST /scrape  (example.com)" -ForegroundColor Yellow
$body = @{ url = "https://example.com"; extract_text = $true } | ConvertTo-Json
$r = Invoke-RestMethod -Uri "$BASE/scrape" -Method POST -ContentType "application/json" -Body $body
Write-Host "Success: $($r.success)  |  Title: $($r.title)  |  Text chars: $($r.text.Length)  |  Links: $($r.links.Count)"

# 7. Search-and-scrape
Write-Host ""
Write-Host "[7] POST /search-and-scrape" -ForegroundColor Yellow
$body = @{ query = "Supabase realtime features"; lang = "en"; max_results = 5; scrape_top = 2 } | ConvertTo-Json
$r = Invoke-RestMethod -Uri "$BASE/search-and-scrape" -Method POST -ContentType "application/json" -Body $body
Write-Host "Query: $($r.query)  |  Lang: $($r.lang)  |  Results: $($r.results.Count)"
foreach ($item in $r.results) {
    $scraped = if ($item.scraped) { "scraped" } else { "not scraped" }
    $chars   = if ($item.content) { "$($item.content.Length) chars" } else { "no content" }
    Write-Host "  [$scraped] $($item.title) -- $chars"
}

Write-Host ""
Write-Host "=== All tests complete ===" -ForegroundColor Green
