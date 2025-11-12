from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from PIL import Image
import io
import os
import mimetypes
from pathlib import Path
from typing import Optional

# Load environment variables from .env before importing the agents SDK
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

from app.schemas import (
    VisionResult,
    RoutePlannerRequest,
    ObjectConfirmedRequest,
    AppendTaskRequest,
    MissionResponse,
    Task,
    Location
)
from app.agent_def import to_data_url, run_vision, run_planner


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
async def analyze(
    prompt: str = Form(...),
    image: UploadFile = File(...),
    lat: Optional[float] = Form(None),
    lon: Optional[float] = Form(None),
    alt_agl_ft: Optional[float] = Form(None),
    mission_id: Optional[str] = Form(None),
    priority: Optional[str] = Form(None)
):
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
    
    # Validate drone location (all three coordinates must be provided together, or none)
    if (lat is not None or lon is not None or alt_agl_ft is not None):
        if lat is None or lon is None or alt_agl_ft is None:
            raise HTTPException(
                status_code=400,
                detail="If providing drone location, all three coordinates (lat, lon, alt_agl_ft) must be provided."
            )
        drone_location = {"lat": lat, "lon": lon, "alt_agl_ft": alt_agl_ft}
    else:
        # Default location if not provided (0, 0, 0)
        drone_location = {"lat": 0.0, "lon": 0.0, "alt_agl_ft": 0.0}
    
    # Parse priority if provided (can be int or string)
    parsed_priority = None
    if priority:
        try:
            # Try to parse as int first
            parsed_priority = int(priority)
        except ValueError:
            # If not a number, keep as string
            parsed_priority = priority
    
    data_url = to_data_url(raw, image.filename, mime_type=mime_type)
    
    try:
        result_dict = await run_vision(
            prompt=prompt,
            image_data_url=data_url,
            drone_location=drone_location,
            mission_id=mission_id,
            priority=parsed_priority
        )
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


@app.post("/plan", response_model=MissionResponse)
async def plan_route(request: RoutePlannerRequest):
    """
    Route planner endpoint that handles two use cases:
    - OBJECT_CONFIRMED: Creates a mission to return to a location where an object was detected
    - APPEND_TASK: Appends a vision waypoint task to an existing mission
    
    Uses the DroneMissionTaskPlanner agent to generate mission tasks.
    """
    try:
        # Convert request to dict for the agent
        input_data = request.model_dump()
        
        # Run the planner agent
        result_dict = await run_planner(input_data)
        
        # Validate and return the response
        result = MissionResponse.model_validate(result_dict)
        return JSONResponse(content=result.model_dump())
    
    except HTTPException:
        raise
    except ValueError as e:
        # Validation errors from data validator or Pydantic
        error_msg = str(e)
        if "Data validation failed" in error_msg:
            raise HTTPException(
                status_code=400,
                detail=error_msg
            )
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
            detail=f"Error planning route: {str(e)}"
        )

