#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "Setting up Nexus development environment..."

# Create virtual environment if missing
if [ ! -d ".venv" ]; then
	python3 -m venv .venv
	echo "Created .venv"
fi

source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]" --quiet
echo "Dependencies installed"

# Copy .env if missing
if [ ! -f ".env" ]; then
	cp .env.example .env
	echo "Created .env from .env.example — fill in your API keys"
else
	echo ".env already exists"
fi

echo ""
echo "Ready. Activate with: source .venv/bin/activate"
echo "Run tests with: pytest tests/ -v"
