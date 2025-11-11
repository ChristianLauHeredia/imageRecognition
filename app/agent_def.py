from typing import Dict, Any, Optional
import base64
import mimetypes
import json
from pathlib import Path
from pydantic import BaseModel

# Load environment variables from .env before importing the agents SDK
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

from agents import Agent, ModelSettings, Runner, RunConfig


class VisionAnalyzerSchema__BoxesItem(BaseModel):
    x: float
    y: float
    w: float
    h: float
    confidence: float


class VisionAnalyzerSchema(BaseModel):
    found: bool
    confidence: float
    boxes: list[VisionAnalyzerSchema__BoxesItem]


vision_analyzer = Agent(
    name="Vision Analyzer",
    instructions="""You are a visual detector agent. Analyze the provided image and determine if it contains the object described by the user.

Return only valid JSON that conforms exactly to the provided schema. 
- If at least one matching object is visible, set found=true.
- confidence must be a float in [0,1].
- boxes must contain normalized coordinates in [0,1] relative to image width and height (x,y are top-left; w,h are width and height).
- If nothing is found, return: {\"found\": false, \"confidence\": <your best estimate>, \"boxes\": []}
Do not include any text outside the JSON.""",
    model="gpt-4.1",
    output_type=VisionAnalyzerSchema,
    model_settings=ModelSettings(
        temperature=1,
        top_p=1,
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


async def run_vision(prompt: str, image_data_url: str) -> Dict[str, Any]:
    items: list[dict] = [
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": prompt},
                {"type": "input_image", "image_url": image_data_url}
            ]
        }
    ]
    result = await Runner.run(
        vision_analyzer,
        input=items,
        run_config=RunConfig(trace_metadata={
            "__trace_source__": "api",
            "workflow_id": "wf_api_proxy"
        })
    )
    if not result.final_output:
        raise RuntimeError("Agent result is undefined")
    # final_output is already a pydantic model from the schema → convert to clean dict
    return result.final_output.model_dump()


# Route Planner Agent
class PlannerAgentSchema__TasksItem(BaseModel):
    type: str  # "LOITER", "MOVE_TO", "VISION_WAYPOINT", "RETURN_HOME"
    lat: float
    lon: float
    alt_agl_ft: float
    duration_s: int


class PlannerAgentSchema(BaseModel):
    mission_id: str
    priority: int
    lease_ttl_s: int
    tasks: list[PlannerAgentSchema__TasksItem]


planner_agent = Agent(
    name="DroneMissionTaskPlanner",
    instructions="""You are DroneMissionTaskPlanner, an autonomous agent that plans drone mission tasks in response to external triggers.

Your purpose is to generate valid mission task payloads in JSON format that can be consumed by the coordinator API. The tasks define what the drone should do next depending on the mission state and sensor events.

🎯 Use Cases

1. OBJECT_CONFIRMED

Triggered when another agent confirms that the target object has been detected.

You will receive drone_location_at_snapshot and priority.

You must:

Create a MOVE_TO task to go to drone_location_at_snapshot (lat, lon, alt_agl_ft).

Then create a LOITER task (5–30 s) at the same location to confirm or record the object.

If altitude < 100 ft, increase it by +20 ft for safety.

Convert "high" or "immediate" textual priorities to numeric 5.

Use "lease_ttl_s": 120 by default.

Expected Output Example

{   "mission_id": "mis_001",   "priority": 5,   "lease_ttl_s": 120,   "tasks": [     { "type": "MOVE_TO", "lat": 32.7160, "lon": -117.1615, "alt_agl_ft": 120, "duration_s": 0 },     { "type": "LOITER", "lat": 32.7160, "lon": -117.1615, "alt_agl_ft": 120, "duration_s": 10 }   ] } 

2. APPEND_TASK

Triggered when a new waypoint or task must be added to the active mission.

You will receive drone_location, waypoint (with fusion_status), and time_of_execution_s.

You must:

Create a single VISION_WAYPOINT task using the waypoint coordinates.

If fusion_status="nosafe", increase altitude +20 ft and replace with a short LOITER task instead.

Duration can be 5–30 s.

Priority mapping and lease_ttl_s same as above.

Expected Output Example

{   "mission_id": "mis_001",   "priority": 5,   "lease_ttl_s": 120,   "tasks": [     { "type": "VISION_WAYPOINT", "lat": 32.7160, "lon": -117.1615, "alt_agl_ft": 120, "duration_s": 10 }   ] } 

⚙️ Output Rules

Always output pure JSON, no markdown or text.

The top-level JSON must match the response_schema strictly.

Never omit required keys.

Always include at least one task.

All tasks must include lat, lon, alt_agl_ft, and duration_s, even for LOITER or RETURN_HOME.

Default lease_ttl_s = 120.""",
    model="gpt-4.1",
    output_type=PlannerAgentSchema,
    model_settings=ModelSettings(
        temperature=1,
        top_p=1,
        max_tokens=2048,
        store=True
    )
)


async def run_planner(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Run the planner agent with the given input data.
    
    Args:
        input_data: Dictionary containing the request data (ObjectConfirmedRequest or AppendTaskRequest)
    
    Returns:
        Dictionary with the mission response
    """
    # Convert input data to JSON string for the agent
    input_text = json.dumps(input_data, indent=2)
    
    items: list[dict] = [
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": input_text}
            ]
        }
    ]
    
    result = await Runner.run(
        planner_agent,
        input=items,
        run_config=RunConfig(trace_metadata={
            "__trace_source__": "api",
            "workflow_id": "wf_planner_api"
        })
    )
    
    if not result.final_output:
        raise RuntimeError("Agent result is undefined")
    
    # final_output is already a pydantic model from the schema → convert to clean dict
    return result.final_output.model_dump()

