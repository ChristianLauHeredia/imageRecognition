from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
import io
import os
import json
import logging
import mimetypes
from pathlib import Path
from typing import Optional

# Load environment variables from .env before importing the agents SDK
# Only load .env if it exists (for local development)
# In Vercel/production, use environment variables directly
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    # In production (Vercel), environment variables are set directly
    load_dotenv(override=False)

from app.schemas import (
    VisionResult,
    VisionAnalyzeResponse,
    RoutePlannerRequest,
    ObjectConfirmedRequest,
    AppendTaskRequest,
    MissionResponse,
    Task,
    Location,
    ChatRequest,
    ChatResponse
)
from app.agent_def import to_data_url, run_vision, run_planner, run_chat_workflow


app = FastAPI(title="Vision Agent Proxy", version="1.0.0")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    else:
        # Log that API key is configured (without exposing the key)
        logging.info("✓ OPENAI_API_KEY is configured")


@app.post("/analyze")
async def analyze(
    prompt: str = Form(...),
    image: UploadFile = File(...),
    mission_id: str = Form(...)
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
    
    # Validate that mission_id is not empty
    if not mission_id or not mission_id.strip():
        raise HTTPException(
            status_code=400,
            detail="Mission ID is required."
        )
    
    data_url = to_data_url(raw, image.filename, mime_type=mime_type)
    
    try:
        # Step 1: Run vision analyzer
        # lat, lon, alt_agl_ft, and priority will be extracted from the prompt by the agent
        result_dict = await run_vision(
            prompt=prompt,
            image_data_url=data_url,
            mission_id=mission_id.strip()
        )
        
        # Validate and convert result
        try:
            vision_result = VisionResult.model_validate(result_dict)
        except Exception as validation_error:
            import traceback
            logging.error(f"Validation error for vision result: {validation_error}")
            logging.debug(f"Result dict: {result_dict}")
            logging.debug(traceback.format_exc())
            raise HTTPException(
                status_code=500,
                detail=f"Invalid response from vision agent: {str(validation_error)}"
            )
        
        # Step 2: If OBJECT_CONFIRMED, automatically call planner
        mission_plan = None
        if vision_result.use_case == "OBJECT_CONFIRMED":
            try:
                # Convert priority (1-5) to string format for planner
                # Priority mapping: 1-2 = low, 3 = medium, 4-5 = high
                if vision_result.priority >= 4:
                    priority_str = "high"
                elif vision_result.priority >= 2:
                    priority_str = "medium"
                else:
                    priority_str = "low"
                
                # Prepare planner request
                planner_request_data = {
                    "use_case": "OBJECT_CONFIRMED",
                    "mission_id": vision_result.mission_id,
                    "priority": priority_str,
                    "drone_location_at_snapshot": vision_result.drone_location_at_snapshot.model_dump()
                }
                
                # Call planner
                planner_result_dict = await run_planner(planner_request_data)
                mission_plan = MissionResponse.model_validate(planner_result_dict)
            except Exception as planner_error:
                # Log planner error but don't fail the vision result
                # The vision result is still valid even if planner fails
                import logging
                logging.warning(f"Planner failed after OBJECT_CONFIRMED: {str(planner_error)}", exc_info=True)
                # Continue without mission_plan
        
        # Return combined response
        response = VisionAnalyzeResponse(
            vision_result=vision_result,
            mission_plan=mission_plan
        )
        return JSONResponse(content=response.model_dump(exclude_none=True))
    
    except HTTPException:
        raise
    except ValueError as e:
        # Pydantic validation errors
        import traceback
        error_detail = str(e)
        traceback_str = traceback.format_exc()
        logging.error(f"ValueError in /analyze: {error_detail}")
        logging.debug(traceback_str)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing agent response: {error_detail}"
        )
    except Exception as e:
        # Other errors - log full traceback for debugging
        import traceback
        error_msg = str(e)
        traceback_str = traceback.format_exc()
        logging.error(f"Exception in /analyze: {error_msg}")
        logging.debug(traceback_str)
        
        if "api_key" in error_msg.lower() or "OPENAI_API_KEY" in error_msg:
            raise HTTPException(
                status_code=500,
                detail="Configuration error: OpenAI API key is not configured correctly."
            )
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {error_msg}"
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


@app.post("/chat", response_model=ChatResponse)
async def chat(
    message: str = Form(...),
    conversation_history: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None)
):
    """
    Chat endpoint that uses the SARA workflow via agentsdk.
    This endpoint handles conversational interactions with the SARA agent.
    Supports optional image uploads.
    """
    try:
        # Parse conversation history if provided
        parsed_history = None
        if conversation_history:
            try:
                history_data = json.loads(conversation_history)
                parsed_history = [
                    {"role": msg.get("role", "user"), "content": msg.get("content", "")}
                    for msg in history_data
                ]
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid conversation_history format. Expected JSON array."
                )
        
        # Handle image if provided
        image_data_url = None
        if image and image.filename:
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
                img_format = img.format.lower() if img.format else None
            except Exception:
                raise HTTPException(
                    status_code=400,
                    detail="The provided image is invalid or corrupted. Please send an image in PNG, JPEG, or similar format."
                )
            
            # Get MIME type
            mime_type = image.content_type
            if not mime_type and img_format:
                mime_type = f"image/{img_format}"
            if not mime_type:
                mime_type, _ = mimetypes.guess_type(image.filename or "image")
            
            # Convert to data URL
            image_data_url = to_data_url(raw, image.filename or "image", mime_type)
        
        # Run the chat workflow
        result = await run_chat_workflow(
            message=message,
            conversation_history=parsed_history,
            image_data_url=image_data_url
        )
        
        # Validate and return the response
        response = ChatResponse(
            response=result.get("response", ""),
            conversation_id=result.get("conversation_id"),
            console_message=result.get("console_message")
        )
        return JSONResponse(content=response.model_dump(exclude_none=True))
    
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid request: {str(e)}"
        )
    except Exception as e:
        error_msg = str(e)
        if "api_key" in error_msg.lower() or "OPENAI_API_KEY" in error_msg:
            raise HTTPException(
                status_code=500,
                detail="Configuration error: OpenAI API key is not configured correctly."
            )
        raise HTTPException(
            status_code=500,
            detail=f"Error processing chat request: {error_msg}"
        )

