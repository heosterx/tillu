# TILLU HuggingFace Spaces Deployment Script
# Run this after git push to deploy all spaces
# 
# IMPORTANT: Set HF_TOKEN environment variable before running:
#   Windows PowerShell: $env:HF_TOKEN="your_token_here"
#   Windows CMD: set HF_TOKEN=your_token_here
#   Linux/Mac: export HF_TOKEN=your_token_here
#
# Get your token from: https://huggingface.co/settings/tokens

$HF_TOKEN = $env:HF_TOKEN

if (-not $HF_TOKEN) {
    Write-Error "HF_TOKEN environment variable not set!"
    Write-Host "Please set it with: `$env:HF_TOKEN='your_token_here'"
    exit 1
}

# Colors for output
function Write-Success($msg) { Write-Host "✅ $msg" -ForegroundColor Green }
function Write-Info($msg) { Write-Host "ℹ️  $msg" -ForegroundColor Cyan }
function Write-Error($msg) { Write-Host "❌ $msg" -ForegroundColor Red }

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "TILLU HF Spaces Deployment" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Check if huggingface_hub is installed
Write-Info "Checking huggingface-cli..."
try {
    $version = huggingface-cli --version 2>&1
    Write-Success "huggingface-cli found: $version"
} catch {
    Write-Error "huggingface-cli not found. Install with: pip install huggingface_hub"
    exit 1
}

# Login to HuggingFace
Write-Host ""
Write-Info "Logging in to HuggingFace..."
huggingface-cli login --token $HF_TOKEN
Write-Success "Logged in"

# Deploy SearXNG Space
Write-Host ""
Write-Info "Deploying SearXNG Space..."
try {
    Set-Location "..\deployments\huggingface\searxng-space"
    git init 2>$null
    git add -A
    git commit -m "Update SearXNG space" 2>$null
    huggingface-cli repo create tillu-ai-tillu-searxng --type space --sdk docker --private 2>$null
    git remote add origin https://huggingface.co/spaces/tillu-ai/tillu-searxng 2>$null
    git push -u origin main --force
    Write-Success "SearXNG space deployed"
} catch {
    Write-Error "Failed to deploy SearXNG: $_"
}

# Deploy WebSearch Space
Write-Host ""
Write-Info "Deploying WebSearch Space..."
try {
    Set-Location "..\websearch-space"
    git init 2>$null
    git add -A
    git commit -m "Update WebSearch space with Crawl4AI" 2>$null
    huggingface-cli repo create tillu-ai-tillu-websearch --type space --sdk docker --private 2>$null
    git remote add origin https://huggingface.co/spaces/tillu-ai/tillu-websearch 2>$null
    git push -u origin main --force
    Write-Success "WebSearch space deployed"
} catch {
    Write-Error "Failed to deploy WebSearch: $_"
}

# Deploy Daemon Space (if exists)
if (Test-Path "..\daemon-space") {
    Write-Host ""
    Write-Info "Deploying Daemon Space..."
    try {
        Set-Location "..\daemon-space"
        git init 2>$null
        git add -A
        git commit -m "Update Daemon space" 2>$null
        huggingface-cli repo create tillu-ai-tillu-daemon --type space --sdk docker --private 2>$null
        git remote add origin https://huggingface.co/spaces/tillu-ai/tillu-daemon 2>$null
        git push -u origin main --force
        Write-Success "Daemon space deployed"
    } catch {
        Write-Error "Failed to deploy Daemon: $_"
    }
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Success "Deployment complete!"
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Info "Space URLs:"
Write-Host "  • SearXNG: https://tillu-ai-tillu-searxng.hf.space"
Write-Host "  • WebSearch: https://tillu-ai-tillu-websearch.hf.space"
if (Test-Path "..\daemon-space") {
    Write-Host "  • Daemon: https://tillu-ai-tillu-daemon.hf.space"
}
Write-Host ""
Write-Info "Next steps:"
Write-Host "  1. Go to HuggingFace Spaces settings"
Write-Host "  2. Add secrets to WebSearch space:"
Write-Host "     • SEARXNG_URL = https://tillu-ai-tillu-searxng.hf.space"
Write-Host "     • GROQ_API_KEY = (your Groq key)"
Write-Host ""
