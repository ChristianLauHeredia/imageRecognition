#!/usr/bin/env python3
"""Test script to verify that the server can start"""

import sys

try:
    print("1. Importing modules...")
    from app.main import app
    print("✓ app.main imported successfully")
    
    from app.agent_def import vision_analyzer, run_vision
    print("✓ app.agent_def imported successfully")
    
    from app.schemas import VisionResult, BBox
    print("✓ app.schemas imported successfully")
    
    print("\n2. Verifying that vision_analyzer is defined...")
    if vision_analyzer:
        print("✓ vision_analyzer is defined")
    else:
        print("✗ vision_analyzer is not defined")
        sys.exit(1)
    
    print("\n3. Attempting to start server...")
    import uvicorn
    print("✓ uvicorn available")
    print("\n✓ Everything ready! You can run: uvicorn app.main:app --reload")
    
except ImportError as e:
    print(f"✗ Import error: {e}")
    print("\nMake sure to install dependencies:")
    print("pip install -r requirements.txt")
    sys.exit(1)
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)


