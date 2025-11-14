from typing import Dict, Any, Optional, Literal, Union, List
import base64
import mimetypes
import json
from pathlib import Path
from pydantic import BaseModel

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

from agents import Agent, ModelSettings, Runner, RunConfig, AgentOutputSchema, Workflow
from pydantic import ConfigDict


class VisionAnalyzerSchema(BaseModel):
    model_config = ConfigDict(strict=True)
    
    use_case: Literal["OBJECT_CONFIRMED", "OBJECT_NOT_FOUND"]
    mission_id: str
    priority: Union[int, str]  # Can be int or string (any)
    drone_location_at_snapshot: Dict[str, float]  # {lat, lon, alt_agl_ft}


# Wrap schema with AgentOutputSchema to disable strict JSON schema
vision_output_type = AgentOutputSchema(VisionAnalyzerSchema, strict_json_schema=False)

vision_analyzer = Agent(
    name="Vision Analyzer",
    instructions="""You are a strict visual detector agent. You receive:

an image of a drone snapshot,

a natural-language target_prompt describing the object to identify (e.g., "red pickup truck facing north"),

drone_location at capture time { lat, lon, alt_agl_ft },

optional mission_id and priority (default priority=3 if missing).

Task:

Carefully analyze the image and determine if at least one object CLEARLY and UNEQUIVOCALLY matches the target_prompt description.

CRITICAL: You must be very conservative. Only return OBJECT_CONFIRMED if you are HIGHLY CONFIDENT (≥0.85 confidence) that the object is present and matches the description.

If you have ANY doubt, uncertainty, or the object is partially obscured, ambiguous, or could be mistaken for something else, return OBJECT_NOT_FOUND.

Always return only valid JSON that conforms exactly to the provided JSON Schema (see Response Format).

Confidence threshold: ONLY treat as confirmed if your best-estimate confidence ≥ 0.85. Be strict - false positives are worse than false negatives.

drone_location_at_snapshot should equal the provided drone_location unless the user explicitly provides a corrected snapshot location in inputs.

Do not include detection internals (boxes, found, etc.) in the final JSON—only the operational fields in the schema.

No text outside JSON.

Edge cases - ALL of these should result in OBJECT_NOT_FOUND:

- Ambiguous object or partial occlusion → return OBJECT_NOT_FOUND
- Similar but not exact match → return OBJECT_NOT_FOUND  
- Low resolution or unclear image → return OBJECT_NOT_FOUND
- Object might be present but cannot be clearly identified → return OBJECT_NOT_FOUND
- Any uncertainty about whether the object matches the description → return OBJECT_NOT_FOUND

Only confirm if the object is CLEARLY visible and UNEQUIVOCALLY matches the target_prompt description.""",
    model="gpt-4.1",
    output_type=vision_output_type,
    model_settings=ModelSettings(
        temperature=0.3,  # Lower temperature for more conservative, deterministic responses
        top_p=0.9,  # Slightly lower top_p for more focused responses
        max_tokens=2048,
        store=True
    )
)


def to_data_url(data: bytes, filename: str, mime_type: Optional[str] = None) -> str:
    """Convert binary data to base64 data URL format.
    
    Args:
        data: Binary image data
        filename: File name (to detect MIME type if not provided)
        mime_type: Optional MIME type (if provided, used instead of detecting)
    
    Returns:
        Data URL in format: data:image/{format};base64,{base64_encoded_data}
    """
    if mime_type:
        mime = mime_type
    else:
        mime, _ = mimetypes.guess_type(filename)
        if not mime:
            mime = "application/octet-stream"
    
    base64_encoded = base64.b64encode(data).decode('utf-8')
    return f"data:{mime};base64,{base64_encoded}"


async def run_vision(
    prompt: str, 
    image_data_url: str, 
    drone_location: Dict[str, float],
    mission_id: Optional[str] = None,
    priority: Optional[Union[int, str]] = None
) -> Dict[str, Any]:
    """Run the vision analyzer agent with image and location data.
    
    Args:
        prompt: Description of the object to identify
        image_data_url: Base64 data URL of the image
        drone_location: Dictionary with lat, lon, alt_agl_ft
        mission_id: Optional mission ID (defaults to "default" if not provided)
        priority: Optional priority (defaults to 3 if not provided)
    
    Returns:
        Dictionary with the vision analysis result
    """
    # Build input text with all context
    input_parts = [
        f"target_prompt: {prompt}",
        f"drone_location: {json.dumps(drone_location)}"
    ]
    
    if mission_id:
        input_parts.append(f"mission_id: {mission_id}")
    
    if priority is not None:
        input_parts.append(f"priority: {priority}")
    
    input_text = "\n".join(input_parts)
    
    items: list[dict] = [
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": input_text},
                {"type": "input_image", "image_url": image_data_url}
            ]
        }
    ]
    
    result = await Runner.run(
        vision_analyzer,
        input=items,
        run_config=RunConfig(trace_metadata={
            "__trace_source__": "api",
            "workflow_id": "wf_vision_api"
        })
    )
    
    if not result.final_output:
        raise RuntimeError("Agent result is undefined")
    
    # final_output is already a pydantic model from the schema → convert to clean dict
    output_dict = result.final_output.model_dump()
    
    # Ensure mission_id exists (use provided or default)
    if "mission_id" not in output_dict or not output_dict["mission_id"]:
        output_dict["mission_id"] = mission_id or "default_mission"
    
    # Ensure priority exists (use provided or default)
    if "priority" not in output_dict or output_dict["priority"] is None:
        output_dict["priority"] = priority if priority is not None else 3
    
    # Ensure drone_location_at_snapshot is properly formatted as Location object
    if "drone_location_at_snapshot" in output_dict:
        loc_dict = output_dict["drone_location_at_snapshot"]
        if isinstance(loc_dict, dict):
            # Convert dict to Location format for response schema
            output_dict["drone_location_at_snapshot"] = {
                "lat": loc_dict.get("lat", drone_location.get("lat", 0.0)),
                "lon": loc_dict.get("lon", drone_location.get("lon", 0.0)),
                "alt_agl_ft": loc_dict.get("alt_agl_ft", drone_location.get("alt_agl_ft", 0.0))
            }
        else:
            # Fallback to provided location
            output_dict["drone_location_at_snapshot"] = drone_location
    else:
        # Use provided location if not in output
        output_dict["drone_location_at_snapshot"] = drone_location
    
    return output_dict


# Data Validator Agent Schema
class DataValidatorSchema__Payload(BaseModel):
    model_config = ConfigDict(strict=True)
    
    drone_location_at_snapshot: Optional[Dict[str, float]] = None
    drone_location: Optional[Dict[str, float]] = None
    waypoint: Optional[Dict[str, Any]] = None


class DataValidatorSchema(BaseModel):
    model_config = ConfigDict(strict=True)
    
    status: Literal["OK", "ERROR"]
    use_case: Literal["OBJECT_CONFIRMED", "APPEND_TASK"]
    mission_id: str
    priority: int
    payload: DataValidatorSchema__Payload
    errors: list[str]


# Route Planner Agent Schema
class PlannerAgentSchema__TasksItem(BaseModel):
    model_config = ConfigDict(strict=True)
    
    type: Literal["MOVE_TO", "LOITER", "VISION_WAYPOINT"]
    lat: float
    lon: float
    alt_agl_ft: float
    duration_s: int
    speed_mps: float


class PlannerAgentSchema(BaseModel):
    model_config = ConfigDict(strict=True)
    
    mission_id: str
    priority: int
    tasks: list[PlannerAgentSchema__TasksItem]


# Data Validator Agent
data_validator_agent = Agent(
    name="Data validator",
    instructions="""You validate and normalize incoming drone-mission inputs before any planning. Your job: ensure presence, types, and ranges are correct; return either a normalized payload or a clear error list. Always return pure JSON according to the tool's response schema. No prose or markdown.

What you receive (typical fields)

use_case: OBJECT_CONFIRMED or APPEND_TASK

mission_id: string

priority: string (low|normal|high|immediate) or number (1–5)

Optional coordinates depending on use case

Normalization & validation rules

Coerce numeric strings to numbers for lat, lon, alt_agl_ft, priority.

Priority mapping: low→1, normal→3, high|immediate→5.

If use_case == OBJECT_CONFIRMED, force priority = 5.

Coordinate ranges: -90 ≤ lat ≤ 90, -180 ≤ lon ≤ 180, alt_agl_ft ≥ 0.

Required by use case (validation only, no planning decisions):

OBJECT_CONFIRMED: must include a valid drone_location_at_snapshot {lat, lon, alt_agl_ft}.

APPEND_TASK: must include valid drone_location {lat, lon, alt_agl_ft} and waypoint {lat, lon, alt_agl_ft, fusion_status(safe|nosafe)}.

Remove unknown fields from output; keep only validated/normalized ones.

On any missing/invalid data, mark status = ERROR and list every problem in errors. Do not attempt recovery beyond type coercion and bounds clamping.

What you must return

status: "OK" or "ERROR"

use_case, mission_id, numeric priority (after normalization)

payload:

For OBJECT_CONFIRMED: include only drone_location_at_snapshot {lat, lon, alt_agl_ft} (normalized).

For APPEND_TASK: include drone_location {…} and waypoint {…} (normalized).

errors: empty list when OK; otherwise a list of human-readable validation messages.

Formatting rules

Single JSON object, no comments, no trailing commas.

All numbers must be numeric (not strings).

Do not invent defaults that change semantics; if a required field is absent or invalid, return ERROR.""",
    model="gpt-4.1",
    output_type=AgentOutputSchema(DataValidatorSchema, strict_json_schema=False),
    model_settings=ModelSettings(
        temperature=1,
        top_p=1,
        max_tokens=2048,
        store=True
    )
)


# Route Planner Agent
planner_agent = Agent(
    name="DroneMissionTaskPlanner",
    instructions="""You are DroneMissionTaskPlanner. Your role is to generate pure JSON mission task plans for an autonomous drone, based on mission context events. Each output must comply strictly with the provided schema.

Use Cases

1) OBJECT_CONFIRMED

Triggered when the vision system confirms that a detected object is valid.

Rules:

Always set "priority": 5 (ignore input priority).

Generate two tasks in order:

MOVE_TO → go to drone_location_at_snapshot at the provided or default speed.

LOITER → hold position for observation.

If alt_agl_ft < 100, increase by +20 ft for safety.

Each task must include speed_mps (for LOITER use 0).

Default speeds:

MOVE_TO: 3.0 m/s

LOITER: 0 m/s

2) APPEND_TASK

Triggered when a new waypoint is added to the ongoing mission.

Rules:

Always first MOVE_TO the provided waypoint coordinates.

Then:

If "fusion_status": "safe", add a VISION_WAYPOINT task.

If "fusion_status": "nosafe", replace it with a LOITER task and increase altitude by +20 ft.

Maintain numeric priority from input.

Each task defines its own speed_mps:

MOVE_TO: 3.0–5.0 m/s typical.

VISION_WAYPOINT or LOITER: 0–1.0 m/s typical (hover or slow scan).

Output rules

Output only valid JSON.

Must comply exactly with the Response Schema.

Each task must include lat, lon, alt_agl_ft, duration_s, and speed_mps.

No markdown, no explanation, only structured JSON.""",
    model="gpt-4.1",
    output_type=AgentOutputSchema(PlannerAgentSchema, strict_json_schema=False),
    model_settings=ModelSettings(
        temperature=1,
        top_p=1,
        max_tokens=2048,
        store=True
    )
)


async def run_chat_workflow(message: str, conversation_history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Run the SARA chat workflow using ChatKit.
    
    Args:
        message: User's message
        conversation_history: Optional list of previous messages in the conversation
    
    Returns:
        Dictionary with the chat response
    """
    # Workflow ID for SARA chat
    workflow_id = "wf_691793d924ec81908711804df04c5c8707e036ccde1385d1"
    
    # Build conversation items
    items: list[dict] = []
    
    # Add conversation history if provided
    if conversation_history:
        for msg in conversation_history:
            items.append({
                "role": msg.get("role", "user"),
                "content": [{"type": "input_text", "text": msg.get("content", "")}]
            })
    
    # Add current user message
    items.append({
        "role": "user",
        "content": [{"type": "input_text", "text": message}]
    })
    
    # Run the workflow using ChatKit
    # Try to load the workflow by ID, or run directly if supported
    try:
        # Attempt to run workflow by ID
        result = await Runner.run(
            workflow_id=workflow_id,
            input=items,
            run_config=RunConfig(trace_metadata={
                "__trace_source__": "api",
                "workflow_id": workflow_id,
                "workflow_name": "SARA"
            })
        )
    except (TypeError, AttributeError) as e:
        # If Runner.run doesn't support workflow_id directly, try loading workflow first
        # This is a fallback - adjust based on actual SDK API
        workflow = Workflow.from_id(workflow_id)
        result = await Runner.run(
            workflow,
            input=items,
            run_config=RunConfig(trace_metadata={
                "__trace_source__": "api",
                "workflow_id": workflow_id,
                "workflow_name": "SARA"
            })
        )
    
    if not result.final_output:
        raise RuntimeError("Chat workflow result is undefined")
    
    # Extract response text from the result
    # The response format may vary, so we'll handle different possible structures
    response_text = ""
    if hasattr(result.final_output, 'text'):
        response_text = result.final_output.text
    elif hasattr(result.final_output, 'content'):
        response_text = result.final_output.content
    elif isinstance(result.final_output, str):
        response_text = result.final_output
    elif isinstance(result.final_output, dict):
        # Try common keys
        response_text = result.final_output.get('response') or result.final_output.get('text') or result.final_output.get('content') or str(result.final_output)
    else:
        response_text = str(result.final_output)
    
    return {
        "response": response_text,
        "conversation_id": getattr(result, 'conversation_id', None)
    }


async def run_planner(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Run the planner workflow with data validator and planner agents.
    
    Args:
        input_data: Dictionary containing the request data (ObjectConfirmedRequest or AppendTaskRequest)
    
    Returns:
        Dictionary with the mission response
    
    Raises:
        RuntimeError: If validation fails or agent result is undefined
        ValueError: If validation returns errors
    """
    # Convert input data to JSON string for the validator
    input_text = json.dumps(input_data, indent=2)
    
    conversation_history: list[dict] = [
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": input_text}
            ]
        }
    ]
    
    run_config = RunConfig(trace_metadata={
        "__trace_source__": "api",
        "workflow_id": "wf_planner_api"
    })
    
    # Step 1: Run data validator
    validator_result = await Runner.run(
        data_validator_agent,
        input=conversation_history,
        run_config=run_config
    )
    
    if not validator_result.final_output:
        raise RuntimeError("Data validator result is undefined")
    
    validator_output = validator_result.final_output
    
    # Add validator result to conversation history
    # The new_items from Runner contain the agent's response items
    if hasattr(validator_result, 'new_items') and validator_result.new_items:
        for item in validator_result.new_items:
            # Access raw_item if available, otherwise use the item directly
            raw_item = getattr(item, 'raw_item', item)
            if isinstance(raw_item, dict):
                conversation_history.append(raw_item)
    
    # Step 2: Check validation status
    if validator_output.status == "ERROR":
        error_messages = ". ".join(validator_output.errors) if validator_output.errors else "Validation failed"
        raise ValueError(f"Data validation failed: {error_messages}")
    
    # Step 3: Run planner agent with validated data
    planner_result = await Runner.run(
        planner_agent,
        input=conversation_history,
        run_config=run_config
    )
    
    if not planner_result.final_output:
        raise RuntimeError("Planner agent result is undefined")
    
    # final_output is already a pydantic model from the schema → convert to clean dict
    return planner_result.final_output.model_dump()

