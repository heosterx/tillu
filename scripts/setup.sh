#!/bin/bash
# TILLU Backend Setup Script for Unix/Linux/Mac
# Run this script to set up the development environment

set -e

echo -e "\033[36mTILLU Backend Setup\033[0m"
echo -e "\033[36m===================\033[0m"
echo ""

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | grep -oP '\d+\.\d+' | head -1)
REQUIRED_VERSION="3.10"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then 
    echo -e "\033[31m✗ Python 3.10+ required. Found: $PYTHON_VERSION\033[0m"
    exit 1
else
    echo -e "\033[32m✓ Python version OK: $PYTHON_VERSION\033[0m"
fi

# Create virtual environment
if [ ! -d "venv" ]; then
    echo -e "\033[33mCreating virtual environment...\033[0m"
    python3 -m venv venv
fi

# Activate virtual environment
echo -e "\033[33mActivating virtual environment...\033[0m"
source venv/bin/activate

# Upgrade pip
echo -e "\033[33mUpgrading pip...\033[0m"
pip install --upgrade pip

# Install dependencies
echo -e "\033[33mInstalling dependencies...\033[0m"
pip install -r requirements.txt

# Check if .env exists
if [ ! -f ".env" ]; then
    echo -e "\033[33mCreating .env from template...\033[0m"
    cp .env.example .env
    echo -e "\033[33m⚠ Please edit .env with your API keys\033[0m"
fi

# Run tests
echo -e "\033[33mRunning tests...\033[0m"
pytest tests/ -v --tb=short || true

echo ""
echo -e "\033[32mSetup complete!\033[0m"
echo ""
echo -e "\033[36mNext steps:\033[0m"
echo -e "1. Edit .env with your API keys"
echo -e "2. Run: uvicorn app.main:app --reload"
echo -e "3. Open: http://localhost:8000/docs"
