# Deploy Guide

This project is ready to deploy on any platform that supports Python 3.9+ and FastAPI.

## Deploy Requirements

- Python 3.9 or higher
- Environment variables configured (especially `OPENAI_API_KEY`)

## Recommended Platforms

### 1. Railway

```bash
# Install Railway CLI
npm i -g @railway/cli

# Login and create project
railway login
railway init

# Configure environment variables
railway variables set OPENAI_API_KEY=sk-your-api-key

# Deploy
railway up
```

### 2. Render

1. Connect your repository at https://render.com
2. Create a new "Web Service"
3. Configuration:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Environment Variables**: Add `OPENAI_API_KEY`

### 3. Fly.io

```bash
# Install Fly CLI
curl -L https://fly.io/install.sh | sh

# Login
fly auth login

# Create app
fly launch

# Configure secrets
fly secrets set OPENAI_API_KEY=sk-your-api-key

# Deploy
fly deploy
```

### 4. Heroku

```bash
# Install Heroku CLI
# Login
heroku login

# Create app
heroku create your-app-name

# Configure variables
heroku config:set OPENAI_API_KEY=sk-your-api-key

# Deploy
git push heroku main
```

### 5. Google Cloud Run

```bash
# Install gcloud CLI
# Configure project
gcloud config set project YOUR-PROJECT-ID

# Build and deploy
gcloud builds submit --tag gcr.io/YOUR-PROJECT-ID/image-recognition
gcloud run deploy image-recognition \
  --image gcr.io/YOUR-PROJECT-ID/image-recognition \
  --platform managed \
  --region us-central1 \
  --set-env-vars OPENAI_API_KEY=sk-your-api-key
```

### 6. Vercel

Vercel has native support for FastAPI:

```bash
# Install Vercel CLI
npm install -g vercel

# Login
vercel login

# Deploy
vercel

# For production
vercel --prod
```

**Configuration:**
- Vercel automatically detects FastAPI if it's in `app/main.py` or `api/index.py`
- Configure `OPENAI_API_KEY` in Vercel dashboard: Settings > Environment Variables
- The `vercel.json` file is already configured in the project

**Note:** Vercel works with serverless functions, so there may be limitations with large files or long-running processes.

### 7. AWS Lambda (with Mangum)

If you want to use AWS Lambda, you'll need a wrapper like Mangum:

```bash
pip install mangum
```

And modify the code to use Mangum as handler.

## Required Environment Variables

- `OPENAI_API_KEY`: Your OpenAI API key (required)

## Files Needed for Deploy

Make sure to include these files in your repository:

- `requirements.txt` - Project dependencies
- `app/` - Application code
- `.gitignore` - To exclude sensitive files
- `README.md` - Documentation

**DO NOT include:**
- `.env` - It's in .gitignore, use platform environment variables
- `.venv/` - Created on the server
- `openai-agents-python/` - SDK is installed from PyPI

## Post-Deploy Verification

Once deployed, verify it works:

```bash
# Verify server responds
curl https://your-app.com/docs

# Test the endpoint
curl -X POST https://your-app.com/analyze \
  -F "prompt=detect a stop sign" \
  -F "image=@path/to/image.jpg"
```

## Important Notes

1. **API Key**: Never commit your API key to the repository. Always use platform environment variables.

2. **Port**: Some platforms (like Render, Railway) assign the port dynamically. The current code uses `--host 0.0.0.0 --port 8000`, but some platforms require reading `$PORT`:
   ```python
   import os
   port = int(os.getenv("PORT", 8000))
   ```

3. **Dependencies**: The `openai-agents` SDK is automatically installed from PyPI when running `pip install -r requirements.txt`.

4. **Logs**: Check platform logs if there are issues. The code shows warnings if the API key is missing.
