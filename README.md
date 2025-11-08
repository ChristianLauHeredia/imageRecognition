# Vision Agent Proxy API

FastAPI API that exposes an endpoint for image analysis using the `vision_analyzer` agent.

## Prerequisites

- Python 3.11 (or higher)
- Xcode Command Line Tools (installed automatically if not present)

## Setup

### Option 1: Automatic script (recommended)

```bash
./setup.sh
```

This script:
- Checks Python
- Creates the virtual environment
- Installs all dependencies

### Option 2: Manual

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

**Note:** If you don't have Python 3.11, you can use `python3` (the script will detect the available version).

**Note:** The `openai-agents` SDK is automatically installed from PyPI when running `pip install -r requirements.txt`. You don't need to clone the SDK repository manually.

## Configure OPENAI_API_KEY

The agents SDK automatically looks for the `OPENAI_API_KEY` environment variable. Configure it before running the server:

### Option 1: Environment variable (recommended)

```bash
export OPENAI_API_KEY=sk-your-api-key-here
```

### Option 2: .env file (with python-dotenv)

1. Copy the example file:
   ```bash
   cp env.example .env
   ```

2. Edit `.env` and add your API key:
   ```
   OPENAI_API_KEY=sk-your-api-key-here
   ```

3. Load variables before running:
   ```bash
   source .env  # or use python-dotenv
   ```

### Get your API Key

1. Go to https://platform.openai.com/api-keys
2. Create a new API key
3. Copy the key (starts with `sk-`)

**Note:** The server will show a warning on startup if the API key is not configured.

## Run

### Option 1: Automatic script (recommended)

The `run.sh` script automatically loads environment variables from `.env`:

```bash
./run.sh
```

### Option 2: Manual

```bash
# Activate virtual environment
source .venv/bin/activate

# Load environment variables from .env
source .env

# Run server
uvicorn app.main:app --reload
```

Or with the API key directly:

```bash
source .venv/bin/activate
OPENAI_API_KEY=sk-your-api-key-here uvicorn app.main:app --reload
```

## Usage Example

```bash
curl -X POST http://localhost:8000/analyze \
  -F "prompt=detect a stop sign" \
  -F "image=@samples/stop.jpg"
```

### Expected Response

```json
{
  "found": true,
  "confidence": 0.87,
  "boxes": [
    {
      "x": 0.12,
      "y": 0.34,
      "w": 0.22,
      "h": 0.19,
      "confidence": 0.83
    }
  ]
}
```

## Tests

```bash
pytest tests/
```

## Deploy

This project is ready to deploy on any platform that supports Python and FastAPI. See [DEPLOY.md](DEPLOY.md) for detailed instructions.

**Supported platforms:**
- **Vercel** ⭐ (Recommended for serverless)
- Railway
- Render
- Fly.io
- Heroku
- Google Cloud Run
- AWS Lambda (with additional configuration)
- Docker

## Structure

- `app/main.py` - FastAPI app and `/analyze` endpoint
- `app/agent_def.py` - Agent definition and helper functions
- `app/schemas.py` - Pydantic models for validation
- `tests/test_contract.py` - Contract tests
- `Dockerfile` - Configuration for Docker deploy
- `Procfile` - Configuration for platforms like Heroku
- `vercel.json` - Configuration for Vercel
- `api/index.py` - Entry point for Vercel Serverless Functions
- `DEPLOY.md` - Complete deploy guide
- `VERCEL.md` - Specific guide for Vercel deploy
