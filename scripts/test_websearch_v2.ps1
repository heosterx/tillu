Write-Host '=== TILLU WebSearch v2 Full Test ===' -ForegroundColor Cyan

Write-Host '[3] POST /search English (SearXNG primary)' -ForegroundColor Yellow
$body3 = @{query='latest AI developments 2025'; lang='en'; max_results=5} | ConvertTo-Json
$r3 = Invoke-RestMethod 'https://tillu-AI-tillu-websearch.hf.space/search' -Method POST -ContentType 'application/json' -Body $body3 -TimeoutSec 30
Write-Host ('Source: ' + $r3.source + ' | Results: ' + $r3.total + ' | Cached: ' + $r3.cached)
$r3.results | Select-Object -First 3 | ForEach-Object { Write-Host ('  - ' + $_.title + ' [' + $_.engine + ']') }

Write-Host '[4] POST /search Hindi' -ForegroundColor Yellow
$body4 = @{query='aaj ka mausam Delhi'; lang='hi'; max_results=3} | ConvertTo-Json
$r4 = Invoke-RestMethod 'https://tillu-AI-tillu-websearch.hf.space/search' -Method POST -ContentType 'application/json' -Body $body4 -TimeoutSec 30
Write-Host ('Source: ' + $r4.source + ' | Lang: ' + $r4.lang + ' | Results: ' + $r4.total)
$r4.results | Select-Object -First 2 | ForEach-Object { Write-Host ('  - ' + $_.title) }

Write-Host '[5] POST /scrape (Playwright)' -ForegroundColor Yellow
$body5 = @{url='https://example.com'; extract_text=$true} | ConvertTo-Json
$r5 = Invoke-RestMethod 'https://tillu-AI-tillu-websearch.hf.space/scrape' -Method POST -ContentType 'application/json' -Body $body5 -TimeoutSec 45
Write-Host ('Success: ' + $r5.success + ' | Title: ' + $r5.title + ' | Chars: ' + $r5.text.Length + ' | Links: ' + $r5.links.Count)

Write-Host '[6] POST /intelligence JARVIS mode' -ForegroundColor Yellow
$body6 = @{query='What is SearXNG and how does it work'; lang='en'; mode='balanced'; max_results=6; scrape_top=2} | ConvertTo-Json
$r6 = Invoke-RestMethod 'https://tillu-AI-tillu-websearch.hf.space/intelligence' -Method POST -ContentType 'application/json' -Body $body6 -TimeoutSec 90
Write-Host ('Model: ' + $r6.model_used + ' | Scraped: ' + $r6.scrape_count + ' | Sources: ' + $r6.sources.Count + ' | Search: ' + $r6.search_source)
$preview = $r6.summary.Substring(0, [Math]::Min(300, $r6.summary.Length))
Write-Host ('Summary: ' + $preview + '...')
Write-Host 'Key Points:'
$r6.key_points | ForEach-Object { Write-Host ('  * ' + $_) }

Write-Host '[7] POST /search-and-scrape' -ForegroundColor Yellow
$body7 = @{query='Python FastAPI tutorial 2025'; lang='en'; max_results=5; scrape_top=2} | ConvertTo-Json
$r7 = Invoke-RestMethod 'https://tillu-AI-tillu-websearch.hf.space/search-and-scrape' -Method POST -ContentType 'application/json' -Body $body7 -TimeoutSec 120
Write-Host ('Source: ' + $r7.source + ' | Results: ' + $r7.results.Count)
$r7.results | ForEach-Object {
    $sc = if ($_.scraped) { 'scraped' } else { 'snippet' }
    $ch = if ($_.content) { $_.content.Length.ToString() + ' chars' } else { 'no content' }
    Write-Host ('  [' + $sc + '] ' + $_.title + ' -- ' + $ch)
}

Write-Host '=== All tests complete ===' -ForegroundColor Green