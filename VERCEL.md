# Deploy on Vercel

Vercel has native support for FastAPI. This project is configured to work on Vercel.

## Quick Setup

### Option 1: From Vercel Dashboard (Recommended)

1. Go to [vercel.com](https://vercel.com) and login
2. Click "Add New Project"
3. Connect your GitHub repository: `ChristianLauHeredia/imageRecognition`
4. Vercel will automatically detect it's a FastAPI project
5. Configure environment variables:
   - Go to Settings > Environment Variables
   - Add: `OPENAI_API_KEY` = `your-api-key`
6. Click "Deploy"

### Option 2: From CLI

```bash
# Install Vercel CLI
npm install -g vercel

# Login
vercel login

# From the project directory
cd /Users/arkus/Documents/Projects/imageRecognition

# Deploy (preview)
vercel

# Deploy to production
vercel --prod
```

## Environment Variables Configuration

In the Vercel dashboard:
1. Go to your project
2. Settings > Environment Variables
3. Add:
   - **Name**: `OPENAI_API_KEY`
   - **Value**: `sk-your-api-key-here`
   - **Environment**: Production, Preview, Development (select all)

## Structure for Vercel

Vercel automatically detects FastAPI if it finds:
- `app/main.py` with a `FastAPI` instance named `app`
- Or `api/index.py` with a `FastAPI` instance

This project has both:
- `app/main.py` - Main application
- `api/index.py` - Wrapper for Vercel (optional, Vercel can use `app/main.py` directly)

## Vercel Limitations

- **Execution time**: Maximum 10 seconds on free plan, 60 seconds on Pro plan
- **Function size**: 250 MB maximum
- **Large files**: There may be limitations with very large images
- **Cold starts**: The first call may be slower

## Post-Deploy Verification

Once deployed, Vercel will give you a URL like:
```
https://your-project.vercel.app
```

Test the endpoint:
```bash
curl -X POST https://your-project.vercel.app/analyze \
  -F "prompt=detect a stop sign" \
  -F "image=@path/to/image.jpg"
```

Or visit the interactive documentation:
```
https://your-project.vercel.app/docs
```

## Troubleshooting

### Error: "Module not found"
- Make sure all dependencies are in `requirements.txt`
- Vercel automatically installs dependencies during build

### Error: "OPENAI_API_KEY not found"
- Verify that the environment variable is configured in the dashboard
- Make sure to select all environments (Production, Preview, Development)

### Timeout on long requests
- Vercel has execution time limits
- Consider using Railway or Render for longer processes

## Recommended Alternatives

If you encounter limitations with Vercel, consider:
- **Railway** - Excellent for FastAPI, easy configuration
- **Render** - Similar to Heroku, very easy to use
- **Fly.io** - Good option with good performance
