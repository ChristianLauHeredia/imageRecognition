#!/bin/bash
# Script to set up the project environment

set -e

echo "🚀 Setting up Vision Agent Proxy project environment..."
echo ""

# Check Python 3.11
echo "1. Checking Python 3.11..."
if command -v python3.11 &> /dev/null; then
    PYTHON_CMD=python3.11
    echo "   ✓ Python 3.11 found"
elif command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    PYTHON_CMD=python3
    echo "   ⚠ Using Python $PYTHON_VERSION (3.11 recommended)"
else
    echo "   ✗ Python not found. Please install Python 3.11"
    exit 1
fi

# Create virtual environment
echo ""
echo "2. Creating virtual environment..."
if [ -d ".venv" ]; then
    echo "   ⚠ Virtual environment already exists, skipping creation"
else
    $PYTHON_CMD -m venv .venv
    echo "   ✓ Virtual environment created"
fi

# Activate virtual environment
echo ""
echo "3. Activating virtual environment..."
source .venv/bin/activate

# Update pip
echo ""
echo "4. Updating pip..."
pip install --upgrade pip --quiet

# Install dependencies
echo ""
echo "5. Installing dependencies from requirements.txt..."
pip install -r requirements.txt

echo ""
echo "✅ Setup completed!"
echo ""
echo "To activate the virtual environment in the future, run:"
echo "   source .venv/bin/activate"
echo ""
echo "To run the server:"
echo "   uvicorn app.main:app --reload"
echo ""


