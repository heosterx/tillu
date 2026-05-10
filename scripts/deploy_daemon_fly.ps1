# Deploy TILLU Daemon to Fly.io
# ================================
# Run from: d:\TILLU\tillu-backend
# Requires: flyctl installed (https://fly.io/docs/hands-on/install-flyctl/)

param(
    [switch]$FirstTime  # Use -FirstTime on first deploy
)

$ErrorActionPreference = "Stop"
$DAEMON_DIR = "deployments\fly\daemon"

Write-Host "TILLU Daemon — Fly.io Deploy" -ForegroundColor Cyan
Write-Host "Working dir: $DAEMON_DIR" -ForegroundColor Gray
Write-Host ""

# Copy app code into the daemon deploy directory
Write-Host "Copying app code..." -ForegroundColor Yellow
Copy-Item -Recurse -Force "app"        "$DAEMON_DIR\app"
Copy-Item -Recurse -Force "daemon"     "$DAEMON_DIR\daemon"
Copy-Item -Force          "requirements.txt" "$DAEMON_DIR\requirements.txt"

Write-Host "Code copied." -ForegroundColor Green

# First-time setup
if ($FirstTime) {
    Write-Host ""
    Write-Host "First-time setup — launching app..." -ForegroundColor Yellow
    Set-Location $DAEMON_DIR
    fly launch --name tillu-daemon --region bom --no-deploy --copy-config
    Set-Location ..\..\..\

    Write-Host ""
    Write-Host "Setting secrets..." -ForegroundColor Yellow

    # Load from .env.production
    $envFile = ".env.production"
    $secrets = @{}
    Get-Content $envFile | ForEach-Object {
        if ($_ -match "^([A-Z_]+)=(.+)$" -and $_ -notmatch "^#") {
            $secrets[$Matches[1]] = $Matches[2]
        }
    }

    $requiredSecrets = @(
        "SUPABASE_URL", "SUPABASE_KEY", "SUPABASE_SERVICE_KEY",
        "REDIS_URL", "GROQ_API_KEY", "HF_TOKEN", "SECRET_KEY",
        "SUPABASE_JWT_SECRET"
    )

    $secretArgs = $requiredSecrets | ForEach-Object {
        if ($secrets.ContainsKey($_)) {
            "$_=$($secrets[$_])"
        }
    }

    Set-Location $DAEMON_DIR
    fly secrets set @secretArgs
    Set-Location ..\..\..\
}

# Deploy
Write-Host ""
Write-Host "Deploying to Fly.io (region: bom / Mumbai)..." -ForegroundColor Yellow
Set-Location $DAEMON_DIR
fly deploy --config fly.toml
Set-Location ..\..\..\

Write-Host ""
Write-Host "Deploy complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Useful commands:" -ForegroundColor Cyan
Write-Host "  fly logs --app tillu-daemon          # Live logs"
Write-Host "  fly status --app tillu-daemon         # Status"
Write-Host "  fly ssh console --app tillu-daemon    # SSH into machine"
Write-Host "  fly scale count 1 --app tillu-daemon  # Ensure 1 instance"
