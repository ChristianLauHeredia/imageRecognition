from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from PIL import Image
import io
import os
import mimetypes
from pathlib import Path

# Load environment variables from .env before importing the agents SDK
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

from app.schemas import VisionResult
from app.agent_def import to_data_url, run_vision


app = FastAPI(title="Vision Agent Proxy", version="1.0.0")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors and return clear messages"""
    errors = exc.errors()
    error_messages = []
    
    for error in errors:
        field = ".".join(str(loc) for loc in error.get("loc", []))
        error_type = error.get("type")
        msg = error.get("msg")
        
        # Custom messages based on field
        if "image" in field.lower() or "file" in field.lower():
            error_messages.append("Image is required")
        elif "prompt" in field.lower():
            error_messages.append("Prompt is required")
        elif error_type == "missing":
            error_messages.append(f"Field '{field}' is required")
        else:
            error_messages.append(f"{field}: {msg}")
    
    detail = ". ".join(error_messages) if error_messages else "Validation error in the submitted data"
    return JSONResponse(
        status_code=400,
        content={"detail": detail}
    )


@app.on_event("startup")
async def startup_event():
    """Verify that OPENAI_API_KEY is configured on startup"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        import warnings
        warnings.warn(
            "OPENAI_API_KEY is not configured. "
            "Set it as an environment variable before running the server.",
            UserWarning
        )


@app.post("/analyze")
async def analyze(prompt: str = Form(...), image: UploadFile = File(...)):
    # Validate that an image was provided
    if not image or not image.filename:
        raise HTTPException(
            status_code=400, 
            detail="Image is required. Please send an image file."
        )
    
    # Validate that the file is not empty
    raw = await image.read()
    if not raw or len(raw) == 0:
        raise HTTPException(
            status_code=400,
            detail="The image file is empty. Please send a valid image."
        )
    
    # Validate that it opens as an image
    try:
        img = Image.open(io.BytesIO(raw))
        img.verify()
        # Get the actual image format
        img_format = img.format.lower() if img.format else None
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail="The provided image is invalid or corrupted. Please send an image in PNG, JPEG, or similar format."
        )
    
    # Use content_type from UploadFile or detect from image format
    mime_type = image.content_type
    if not mime_type and img_format:
        mime_type = f"image/{img_format}"
    if not mime_type:
        mime_type, _ = mimetypes.guess_type(image.filename or "image")
    
    # Validate that prompt is not empty
    if not prompt or not prompt.strip():
        raise HTTPException(
            status_code=400,
            detail="Prompt is required. Please provide a description of the object to search for in the image."
        )
    
    data_url = to_data_url(raw, image.filename, mime_type=mime_type)
    
    try:
        result_dict = await run_vision(prompt, data_url)
        result = VisionResult.model_validate(result_dict)
        return JSONResponse(content=result.model_dump())
    except HTTPException:
        raise
    except ValueError as e:
        # Pydantic validation errors
        raise HTTPException(
            status_code=500,
            detail=f"Error processing agent response: {str(e)}"
        )
    except Exception as e:
        # Other errors - generic but useful message
        error_msg = str(e)
        if "api_key" in error_msg.lower() or "OPENAI_API_KEY" in error_msg:
            raise HTTPException(
                status_code=500,
                detail="Configuration error: OpenAI API key is not configured correctly."
            )
        raise HTTPException(
            status_code=500,
            detail="Internal server error while processing the image. Please try again."
        )

