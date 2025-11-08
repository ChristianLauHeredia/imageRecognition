# Installation Guide

## Current Status

✅ **Complete code**: All project files are created and ready
✅ **Agent integrated**: The `vision_analyzer` agent code is integrated
⏳ **Waiting**: Xcode Command Line Tools installation

## Steps to Complete Installation

### 1. Complete Xcode Command Line Tools Installation

Automatic installation has been initiated. You should see a dialog in macOS asking for confirmation.

**If the dialog doesn't appear**, run manually:
```bash
xcode-select --install
```

**Wait for it to finish** (may take several minutes, ~1-2 GB download).

### 2. Verify Python Works

Once installation is complete, verify:
```bash
python3 --version
```

You should see something like: `Python 3.x.x`

### 3. Run Setup Script

```bash
cd /Users/arkus/Documents/Projects/imageRecognition
./setup.sh
```

This script automatically:
- Detects available Python
- Creates the `.venv` virtual environment
- Installs all dependencies from `requirements.txt`

### 4. Activate Virtual Environment (if not activated automatically)

```bash
source .venv/bin/activate
```

### 5. Run the Server

```bash
uvicorn app.main:app --reload
```

The server will be available at: `http://localhost:8000`

## Verification

Once the server is running, you can:

1. **View interactive documentation**: http://localhost:8000/docs
2. **Test the endpoint**:
   ```bash
   curl -X POST http://localhost:8000/analyze \
     -F "prompt=detect a stop sign" \
     -F "image=@path/to/your/image.jpg"
   ```

## Troubleshooting

### Python doesn't work after installing Xcode
- Close and reopen the terminal
- Verify: `which python3`

### Error installing dependencies
- Make sure you have internet connection
- Verify: `pip --version`
- If it fails, try: `pip install --upgrade pip` first

### Error "agents module not found"
- The `agents` SDK must be installed in your environment
- Verify it's in `requirements.txt` or install it manually

## Next Steps

Once everything is working:
1. Run tests: `pytest tests/`
2. Review documentation at `/docs`
3. Test with real images
