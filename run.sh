#!/bin/bash
# Script to run the server with environment variables loaded

set -e

cd "$(dirname "$0")"

# Activate virtual environment
if [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "❌ Virtual environment not found. Run ./setup.sh first"
    exit 1
fi

# Load environment variables from .env if it exists
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
    echo "✓ Environment variables loaded from .env"
else
    echo "⚠ .env file not found. Make sure to configure OPENAI_API_KEY"
fi

# Verify that OPENAI_API_KEY is configured
if [ -z "$OPENAI_API_KEY" ]; then
    echo "⚠ WARNING: OPENAI_API_KEY is not configured"
    echo "   Configure it with: export OPENAI_API_KEY=sk-..."
else
    echo "✓ OPENAI_API_KEY configured"
fi

# Run server
echo ""
echo "🚀 Starting server at http://localhost:8000"
echo "   Documentation: http://localhost:8000/docs"
echo ""
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000


