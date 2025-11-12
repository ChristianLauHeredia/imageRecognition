"""
Entry point for Vercel Serverless Functions
Vercel looks for files in the /api/ directory for serverless functions
"""
import sys
import os
from pathlib import Path

# Add root directory to path to import app
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

# Ensure environment variables are available
# Vercel sets them directly, but we check here for debugging
if not os.getenv("OPENAI_API_KEY"):
    print("⚠️  WARNING: OPENAI_API_KEY not found in environment variables")
    print("   Make sure to configure it in Vercel dashboard: Settings > Environment Variables")

try:
    # Import FastAPI app
    from app.main import app
    print("✓ FastAPI app imported successfully")
except Exception as e:
    print(f"❌ Error importing app: {e}")
    import traceback
    traceback.print_exc()
    raise

# Vercel automatically detects FastAPI and uses the app object directly
# We don't need an additional handler wrapper
