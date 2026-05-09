# TILLU Backend Setup Script for Windows PowerShell
# Run this script to set up the development environment

Write-Host "TILLU Backend Setup" -ForegroundColor Cyan
Write-Host "===================" -ForegroundColor Cyan
Write-Host ""

# Check Python version
$pythonVersion = python --version 2>&1
if ($pythonVersion -match "Python 3\.(10|11|12)") {
    Write-Host "✓ Python version OK: $pythonVersion" -ForegroundColor Green
} else {
    Write-Host "✗ Python 3.10+ required. Found: $pythonVersion" -ForegroundColor Red
    exit 1
}

# Create virtual environment
if (-not (Test-Path "venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
}

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& .\venv\Scripts\Activate.ps1

# Upgrade pip
Write-Host "Upgrading pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip

# Install dependencies
Write-Host "Installing dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt

# Check if .env exists
if (-not (Test-Path ".env")) {
    Write-Host "Creating .env from template..." -ForegroundColor Yellow
    Copy-Item .env.example .env
    Write-Host "⚠ Please edit .env with your API keys" -ForegroundColor Yellow
}

# Run tests
Write-Host "Running tests..." -ForegroundColor Yellow
pytest tests/ -v --tb=short

Write-Host ""
Write-Host "Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Edit .env with your API keys" -ForegroundColor White
Write-Host "2. Run: uvicorn app.main:app --reload" -ForegroundColor White
Write-Host "3. Open: http://localhost:8000/docs" -ForegroundColor White
