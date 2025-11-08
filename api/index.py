"""
Entry point for Vercel Serverless Functions
Vercel looks for files in the /api/ directory for serverless functions
"""
import sys
from pathlib import Path

# Add root directory to path to import app
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

# Import FastAPI app
from app.main import app

# Vercel automatically detects FastAPI and uses the app object directly
# We don't need an additional handler wrapper
