#!/bin/sh
# TILLU n8n Startup Script
# Starts n8n and auto-creates the owner account on first run

# Start n8n in background
n8n start &
N8N_PID=$!

# Wait for n8n to be ready
echo "Waiting for n8n to start..."
for i in $(seq 1 30); do
    if curl -sf http://localhost:7860/healthz > /dev/null 2>&1; then
        echo "n8n is ready"
        break
    fi
    sleep 3
done

# Auto-setup owner account (idempotent — fails silently if already exists)
echo "Setting up owner account..."
curl -sf -X POST http://localhost:7860/rest/owner/setup \
    -H "Content-Type: application/json" \
    -d '{"email":"tillu@tillu.ai","firstName":"Tillu","lastName":"AI","password":"A45Bab2410ce@Tillu"}' \
    > /dev/null 2>&1 || true

echo "Owner setup complete (or already exists)"

# Keep n8n running
wait $N8N_PID
