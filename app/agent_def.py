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

from agents import Agent, ModelSettings, Runner, RunConfig, AgentOutputSchema
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


# SARA Agent Schema
class SaraSchema(BaseModel):
    model_config = ConfigDict(strict=True)
    
    status: Literal["ERROR", "MISSION_DATA_MISSING", "MISSION_READY", "VISION_VALIDATION"]
    messageForConsole: Optional[Any] = None
    missionType: Optional[Any] = None
    missingFields: List[str]
    plannerPayload: Optional[Any] = None


# INSIGHT Agent Schema (same as VisionAnalyzerSchema but with different name for clarity)
class InsightSchema(BaseModel):
    model_config = ConfigDict(strict=True)
    
    use_case: Literal["OBJECT_CONFIRMED", "OBJECT_NOT_FOUND"]
    mission_id: str
    priority: Union[int, str]
    drone_location_at_snapshot: Dict[str, float]  # {lat, lon, alt_agl_ft}


# SARA Agent
sara_agent = Agent(
    name="SARA",
    instructions="""You are SARA, the first decision agent in the workflow. 

You MUST NOT speak like a normal assistant. 

You MUST respond ONLY with a JSON object that matches the "response_schema" definition. 

No explanations, no extra text, no natural language outside the JSON.

YOUR PURPOSE:

1. Analyze the user query and attached content.

2. Determine whether:

   - The request is a visual validation (image provided) → status = "VISION_VALIDATION"

   - Required information is missing for a search mission → status = "MISSION_DATA_MISSING"

   - The mission is ready to be created → status = "MISSION_READY"

   - The request cannot be understood → status = "ERROR"

3. NEVER ask for unnecessary information.

4. NEVER include properties outside the JSON schema.

5. NEVER output anything except the JSON object.

PRIORITY LOGIC (IMPORTANT):

1. If the input includes ANY image (from user or drone):

   - You MUST classify the request as a visual validation.

   - status MUST be "VISION_VALIDATION".

   - missionType MUST be "VISION_CONFIRMATION".

   - You MUST NOT return "MISSION_READY" when an image is present.

   - Even if lat, lon, and objectType exist, visual validation has priority.

2. ONLY when there is NO image:

   - Check required fields for search mission.

   - If any required field is missing → MISSION_DATA_MISSING.

   - If all required fields are present → MISSION_READY.

REQUIRED DATA FOR "SEARCH_OBJECT" MISSIONS:

- lat

- lon

- objectType (example: "dog")

If any of these are missing → status = "MISSION_DATA_MISSING".

When missing, include ONLY these missing field names inside "missingFields".

Example: ["lat","lon"]

STRICT RULES:

- Always return ALL properties defined in the schema, even if their value is null.

- "plannerPayload" MUST exist in every response. If not applicable → null.

- "missingFields" MUST always exist. If none are missing → [].

- Do NOT generate text outside the JSON.

- Do NOT ask for additional information beyond what is strictly needed 

  (lat, lon, objectType).

- Responses must be short, functional, and strictly structured.

FINAL REMINDER:

Respond with EXACTLY one JSON object.

No natural language.

No explanations.

Nothing outside the schema.""",
    model="gpt-4.1",
    output_type=AgentOutputSchema(SaraSchema, strict_json_schema=False),
    model_settings=ModelSettings(
        temperature=1,
        top_p=1,
        max_tokens=2048,
        store=True
    )
)


# INSIGHT Agent (for vision validation)
insight_agent = Agent(
    name="INSIGHT",
    instructions="""You are a visual detector agent. You receive:

an image of a drone snapshot,

a natural-language target_prompt describing the object to identify (e.g., "red pickup truck facing north"),

drone_location at capture time { lat, lon, alt_agl_ft },

optional mission_id and priority (default priority=3 if missing).

Task:

Analyze the image and decide if at least one object matches target_prompt.

If matched, consider it OBJECT_CONFIRMED; otherwise OBJECT_NOT_FOUND.

Always return only valid JSON that conforms exactly to the provided JSON Schema (see Response Format).

Confidence threshold guideline: if your best-estimate confidence ≥ 0.6, treat as confirmed.

drone_location_at_snapshot should equal the provided drone_location unless the user explicitly provides a corrected snapshot location in inputs.

Do not include detection internals (boxes, found, etc.) in the final JSON—only the operational fields in the schema.

No text outside JSON.

Edge cases:

Ambiguous object or partial occlusion → lower confidence; if <0.6 return OBJECT_NOT_FOUND.

Multiple candidates → confirm if any one satisfies the description.""",
    model="gpt-4.1",
    output_type=AgentOutputSchema(InsightSchema, strict_json_schema=False),
    model_settings=ModelSettings(
        temperature=1,
        top_p=1,
        max_tokens=2048,
        store=True
    )
)


# SARA Formatter Agent Schema
class SaraFormatterSchema(BaseModel):
    model_config = ConfigDict(strict=True)
    
    status: Literal["ERROR", "MISSION_DATA_MISSING", "MISSION_READY", "VISION_VALIDATION"]
    consoleMessage: Optional[str] = None
    missingFields: List[str]
    missionType: Optional[str] = None
    readyForPlanner: bool
    plannerPayload: Optional[Dict[str, Any]] = None


# SARA Formatter Agent
sara_formatter_agent = Agent(
    name="SARA Formatter Agent",
    instructions="""You are the SARA Formatter Agent. 

Your ONLY job is to receive the JSON generated by SARA and transform or normalize that JSON 

into a clean, validated, workflow-ready JSON response.

RULES:

1. You MUST NOT invent information.

2. You MUST NOT modify the meaning of any field coming from SARA.

3. You MUST validate that all required fields in SARA's schema are present.

4. If a required field is missing or malformed, return an ERROR state.

5. You MUST output only JSON, no natural language outside the JSON.

6. You MUST keep all field names exactly as SARA returns them.

7. If SARA sends a field with null, preserve it.

8. You MUST return a transformed/normalized version that is guaranteed to be safe for the next agent.

OUTPUT FORMAT (strict):

{

  "status": "ERROR | MISSION_DATA_MISSING | MISSION_READY | VISION_VALIDATION",

  "consoleMessage": "string or null",

  "missingFields": [...],

  "missionType": "SEARCH_OBJECT | VISION_CONFIRMATION | null",

  "readyForPlanner": boolean,

  "plannerPayload": { ... } or null

}

TRANSFORMATION RULES:

- status:

  Copy directly from SARA.

- consoleMessage:

  If status = MISSION_DATA_MISSING or ERROR → use SARA.messageForConsole

  Otherwise → null

- readyForPlanner:

  true only if:

    status = "MISSION_READY" OR status = "VISION_VALIDATION"

  Otherwise false.

- missionType:

  Copy directly from SARA.

- missingFields:

  Copy directly from SARA (always array).

- plannerPayload:

  If SARA.plannerPayload is null → return null

  Else → return a normalized version:

    {

      "objective": string,

      "lat": number,

      "lon": number,

      "additionalData": {}

    }

ERROR HANDLING:

- If SARA's JSON is malformed or missing required fields:

  Return:

  {

    "status": "ERROR",

    "consoleMessage": "Invalid SARA response.",

    "missingFields": [],

    "missionType": null,

    "readyForPlanner": false,

    "plannerPayload": null

  }

FINAL RULES:

- Return EXACTLY one JSON object.

- No extra text, no commentary, no natural language outside the JSON.""",
    model="gpt-4.1",
    output_type=AgentOutputSchema(SaraFormatterSchema, strict_json_schema=False),
    model_settings=ModelSettings(
        temperature=1,
        top_p=1,
        max_tokens=2048,
        store=True
    )
)


# Planner Formatter Agent Schema
class PlannerFormatterSchema(BaseModel):
    model_config = ConfigDict(strict=True)
    
    status: Literal["OK", "ERROR"]
    missionId: Optional[str] = None
    priority: Optional[int] = None
    tasks: Optional[List[Dict[str, Any]]] = None
    consoleMessage: Optional[str] = None


# Data Formatter Schema
class DataFormatterPayload(BaseModel):
    model_config = ConfigDict(strict=True)
    
    drone_location_at_snapshot: Optional[Dict[str, float]] = None
    drone_location: Optional[Dict[str, float]] = None
    waypoint: Optional[Dict[str, Any]] = None


class DataFormatterSchema(BaseModel):
    model_config = ConfigDict(strict=True)
    
    status: Literal["OK", "ERROR"]
    use_case: Literal["OBJECT_CONFIRMED", "APPEND_TASK"]
    mission_id: Optional[str] = None  # Can be null for OBJECT_CONFIRMED
    priority: int
    payload: DataFormatterPayload
    errors: List[str]


# Planner Formatter Agent
planner_formatter_agent = Agent(
    name="PLANNER Formatter Agent",
    instructions="""You are the Planner Formatter Agent.

Your only job is to receive the raw text returned by the Planner agent 

(e.g., "Mission plan created: { ... }") and extract, validate, clean, 

and normalize the mission plan JSON.

STRICT RULES:

1. You MUST output ONLY a JSON object. Never output natural language outside JSON.

2. You MUST extract the JSON object even if it appears inside text.

3. You MUST validate that the extracted JSON has the required mission fields.

4. If extraction or validation fails, return an error JSON (defined below).

5. You MUST NOT invent or modify mission values.

6. You MAY rename and normalize fields if required by the workflow format.

7. If Planner returns null, empty text, or invalid JSON → return ERROR.

8. Always preserve arrays and numeric types exactly as received.

OUTPUT FORMAT (strict):

{

  "status": "OK | ERROR",

  "missionId": "string or null",

  "priority": "number or null",

  "tasks": "array or null",

  "consoleMessage": "string or null"

}

PARSING LOGIC:

- Extract the first JSON object found in the Planner's output text.

- The mission JSON must contain:

    mission_id

    priority

    tasks (array)

If these fields are present:

  status = "OK"

  missionId = extracted mission_id

  priority = extracted priority

  tasks = extracted tasks

  consoleMessage = null

If they are missing OR JSON is malformed:

  status = "ERROR"

  missionId = null

  priority = null

  tasks = null

  consoleMessage = "Invalid or malformed mission plan returned by Planner."

ERROR TEMPLATE:

{

  "status": "ERROR",

  "missionId": null,

  "priority": null,

  "tasks": null,

  "consoleMessage": "Invalid or malformed mission plan returned by Planner."

}

FINAL RULES:

- Return EXACTLY one JSON object.

- Do NOT output text outside JSON.

- Do NOT wrap the JSON in quotes.""",
    model="gpt-4.1",
    output_type=AgentOutputSchema(PlannerFormatterSchema, strict_json_schema=False),
    model_settings=ModelSettings(
        temperature=1,
        top_p=1,
        max_tokens=2048,
        store=True
    )
)


# Data Formatter Agent
data_formatter_agent = Agent(
    name="Data Formatter",
    instructions="""You validate and normalize incoming drone-mission inputs before any planning.

Your job:

- Ensure presence, types, and ranges are correct FOR THE CURRENT use_case.

- Return either a normalized payload or a clear error list.

- Always return pure JSON according to the tool's response schema.

- No prose or markdown, no comments, no extra text.

Incoming fields (typical):

- use_case: "OBJECT_CONFIRMED" or "APPEND_TASK"

- mission_id: string (may be empty or missing for OBJECT_CONFIRMED)

- priority: string ("low" | "normal" | "high" | "immediate") or number (1–5)

- Coordinates objects, depending on use_case:

  - OBJECT_CONFIRMED: drone_location_at_snapshot { lat, lon, alt_agl_ft }

  - APPEND_TASK: drone_location { lat, lon, alt_agl_ft } and waypoint { lat, lon, alt_agl_ft, fusion_status }

### NORMALIZATION & VALIDATION RULES

- Coerce numeric strings to numbers for: lat, lon, alt_agl_ft, priority.

- Priority mapping:

  - "low" → 1

  - "normal" → 3

  - "high" or "immediate" → 5

- If use_case == "OBJECT_CONFIRMED":

  - Force priority = 5 (override any input).

- Coordinate ranges:

  - -90 ≤ lat ≤ 90

  - -180 ≤ lon ≤ 180

  - alt_agl_ft ≥ 0  (0 is valid and MUST NOT be treated as an error)

### REQUIRED FIELDS PER USE_CASE

1) OBJECT_CONFIRMED

- REQUIRED:

  - use_case must be "OBJECT_CONFIRMED"

  - drone_location_at_snapshot object with:

    - lat (number in valid range)

    - lon (number in valid range)

    - alt_agl_ft (number, ≥ 0)

- mission_id:

  - NOT required at this step.

  - If missing or empty string, set mission_id = null in the output.

- You MUST NOT include `drone_location` or `waypoint` in the output payload for OBJECT_CONFIRMED.

2) APPEND_TASK

- REQUIRED:

  - use_case must be "APPEND_TASK"

  - non-empty mission_id (string)

  - drone_location object with:

    - lat, lon, alt_agl_ft (numbers in valid range)

  - waypoint object with:

    - lat, lon, alt_agl_ft (numbers in valid range)

    - fusion_status: "safe" or "nosafe"

- For APPEND_TASK, mission_id IS required; if missing or empty → ERROR.

### UNKNOWN FIELDS

- Remove unknown fields from the output.

- Do NOT add any extra sections. 

- Very important:

  - For OBJECT_CONFIRMED: payload MUST ONLY contain drone_location_at_snapshot.

  - For APPEND_TASK: payload MUST ONLY contain drone_location and waypoint.

### ERROR BEHAVIOR

- If any REQUIRED field for the CURRENT use_case is missing or invalid:

  - status = "ERROR"

  - List every problem in `errors`.

- Do not attempt recovery beyond:

  - type coercion

  - numeric clamping within allowed ranges.

What you must return (response JSON):

- status: "OK" or "ERROR"

- use_case: the normalized use case ("OBJECT_CONFIRMED" | "APPEND_TASK")

- mission_id: 

  - For OBJECT_CONFIRMED: may be null if not provided or empty.

  - For APPEND_TASK: must be a non-empty string, otherwise ERROR.

- priority: numeric 1–5 (after normalization and overrides)

- payload:

  - For OBJECT_CONFIRMED:

    {

      "drone_location_at_snapshot": {

        "lat": number,

        "lon": number,

        "alt_agl_ft": number

      }

    }

  - For APPEND_TASK:

    {

      "drone_location": {

        "lat": number,

        "lon": number,

        "alt_agl_ft": number

      },

      "waypoint": {

        "lat": number,

        "lon": number,

        "alt_agl_ft": number,

        "fusion_status": "safe" | "nosafe"

      }

    }

- errors:

  - [] when status = "OK"

  - Otherwise, a list of human-readable validation messages.

Formatting rules:

- Single JSON object, no comments, no trailing commas.

- All numbers must be numeric (not strings).

- Do NOT invent defaults that change semantics.

- If a required field for the CURRENT use_case is absent or invalid, return ERROR.

- Do NOT treat mission_id as required for OBJECT_CONFIRMED.""",
    model="gpt-4.1",
    output_type=AgentOutputSchema(DataFormatterSchema, strict_json_schema=False),
    model_settings=ModelSettings(
        temperature=1,
        top_p=1,
        max_tokens=2048,
        store=True
    )
)


# INSIGHT Formatter Agent (empty instructions as per TypeScript code)
insight_formatter_agent = Agent(
    name="INSIGHT Formatter Agent",
    instructions="",
    model="gpt-4.1",
    model_settings=ModelSettings(
        temperature=1,
        top_p=1,
        max_tokens=2048,
        store=True
    )
)


async def run_chat_workflow(message: str, conversation_history: Optional[List[Dict[str, Any]]] = None, image_data_url: Optional[str] = None) -> Dict[str, Any]:
    """Run the SARA chat workflow using ChatKit.
    
    Args:
        message: User's message
        conversation_history: Optional list of previous messages in the conversation
        image_data_url: Optional base64 data URL of an image to include with the message
    
    Returns:
        Dictionary with the chat response
    """
    # Workflow ID for SARA chat
    workflow_id = "wf_691793d924ec81908711804df04c5c8707e036ccde1385d1"
    
    # Build conversation history in the format expected by Runner.run
    # For the first message, use input_text format (same as run_vision)
    # For subsequent messages after agent responses, the format may differ
    conversation_items: list[dict] = []
    
    # Add conversation history if provided
    if conversation_history:
        for msg in conversation_history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                # User messages: use input_text format
                conversation_items.append({
                    "role": "user",
                    "content": [{"type": "input_text", "text": str(content)}]
                })
            else:
                # Assistant messages from history: should already be in correct format
                # If it's a string, wrap it in output_text format
                if isinstance(content, str):
                    conversation_items.append({
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": str(content)}]
                    })
                else:
                    # Assume it's already in the correct format
                    conversation_items.append({
                        "role": "assistant",
                        "content": content
                    })
    
    # Add current user message
    # Use input_text format for the first message (same as run_vision)
    # But if there's already conversation history with assistant messages, 
    # the format might need to be different - try simple string first
    user_content = []
    
    # Add text content
    if conversation_history and any(msg.get("role") == "assistant" for msg in conversation_history):
        # If there's assistant messages in history, use simple string format
        user_content = message
    else:
        # First message or only user messages: use input_text format
        user_content = [{"type": "input_text", "text": message}]
    
    # Add image if provided
    if image_data_url:
        # If user_content is a string, convert to list format
        if isinstance(user_content, str):
            user_content = [{"type": "input_text", "text": user_content}]
        # Add image to content
        user_content.append({"type": "input_image", "image_url": image_data_url})
    
    conversation_items.append({
        "role": "user",
        "content": user_content
    })
    
    # Create Runner with traceMetadata including workflow_id
    run_config = RunConfig(trace_metadata={
        "__trace_source__": "agent-builder",
        "workflow_id": workflow_id
    })
    
    # Step 1: Run SARA agent
    sara_result = await Runner.run(
        sara_agent,
        input=conversation_items,
        run_config=run_config
    )
    
    if not sara_result.final_output:
        raise RuntimeError("SARA agent result is undefined")
    
    # Add SARA's response to conversation history
    # The new_items from Runner already have the correct format (output_text for assistant)
    if hasattr(sara_result, 'new_items') and sara_result.new_items:
        for item in sara_result.new_items:
            # Get the raw_item which has the correct format
            raw_item = getattr(item, 'raw_item', None)
            if raw_item is None:
                # Fallback: construct from item if raw_item not available
                if hasattr(item, 'role') and hasattr(item, 'content'):
                    raw_item = {
                        "role": item.role,
                        "content": item.content
                    }
                else:
                    raw_item = item
            
            if isinstance(raw_item, dict):
                conversation_items.append(raw_item)
    
    sara_output = sara_result.final_output
    
    # Convert SARA output to dict if it's a Pydantic model
    if hasattr(sara_output, 'model_dump'):
        sara_result_dict = sara_output.model_dump()
    else:
        sara_result_dict = sara_output if isinstance(sara_output, dict) else {"status": str(sara_output)}
    
    # Step 2: Check SARA's status and route accordingly
    status = sara_result_dict.get("status")
    
    if status == "VISION_VALIDATION":
        # Run INSIGHT agent
        insight_result = await Runner.run(
            insight_agent,
            input=conversation_items,
            run_config=run_config
        )
        
        if not insight_result.final_output:
            raise RuntimeError("INSIGHT agent result is undefined")
        
        # Add INSIGHT's response to conversation history
        if hasattr(insight_result, 'new_items') and insight_result.new_items:
            for item in insight_result.new_items:
                raw_item = getattr(item, 'raw_item', item)
                if isinstance(raw_item, dict):
                    conversation_items.append(raw_item)
        
        # Convert INSIGHT output to dict
        if hasattr(insight_result.final_output, 'model_dump'):
            insight_output = insight_result.final_output.model_dump()
        else:
            insight_output = insight_result.final_output if isinstance(insight_result.final_output, dict) else {}
        
        use_case = insight_output.get("use_case")
        
        if use_case == "OBJECT_CONFIRMED":
            # Run Data Formatter agent
            data_formatter_result = await Runner.run(
                data_formatter_agent,
                input=conversation_items,
                run_config=run_config
            )
            
            if not data_formatter_result.final_output:
                raise RuntimeError("Data Formatter agent result is undefined")
            
            # Add Data Formatter's response to conversation history
            if hasattr(data_formatter_result, 'new_items') and data_formatter_result.new_items:
                for item in data_formatter_result.new_items:
                    raw_item = getattr(item, 'raw_item', item)
                    if isinstance(raw_item, dict):
                        conversation_items.append(raw_item)
            
            # Convert Data Formatter output to dict
            if hasattr(data_formatter_result.final_output, 'model_dump'):
                data_formatter_output = data_formatter_result.final_output.model_dump()
            else:
                data_formatter_output = data_formatter_result.final_output if isinstance(data_formatter_result.final_output, dict) else {}
            
            data_formatter_status = data_formatter_output.get("status")
            
            if data_formatter_status == "OK":
                # Run PLANNER agent
                planner_result = await Runner.run(
                    planner_agent,
                    input=conversation_items,
                    run_config=run_config
                )
                
                if not planner_result.final_output:
                    raise RuntimeError("PLANNER agent result is undefined")
                
                # Add PLANNER's response to conversation history
                if hasattr(planner_result, 'new_items') and planner_result.new_items:
                    for item in planner_result.new_items:
                        raw_item = getattr(item, 'raw_item', item)
                        if isinstance(raw_item, dict):
                            conversation_items.append(raw_item)
                
                # Run PLANNER Formatter Agent
                planner_formatter_result = await Runner.run(
                    planner_formatter_agent,
                    input=conversation_items,
                    run_config=run_config
                )
                
                if not planner_formatter_result.final_output:
                    raise RuntimeError("PLANNER Formatter agent result is undefined")
                
                # Convert formatter output to dict
                if hasattr(planner_formatter_result.final_output, 'model_dump'):
                    formatter_output = planner_formatter_result.final_output.model_dump()
                else:
                    formatter_output = planner_formatter_result.final_output if isinstance(planner_formatter_result.final_output, dict) else {}
                
                # Build response based on formatter output
                if formatter_output.get("status") == "OK":
                    response_text = f"Mission plan created successfully:\n{json.dumps({'mission_id': formatter_output.get('missionId'), 'priority': formatter_output.get('priority'), 'tasks': formatter_output.get('tasks')}, indent=2)}"
                else:
                    error_msg = formatter_output.get("consoleMessage", "Failed to create mission plan")
                    response_text = f"Error: {error_msg}"
                
                return {
                    "response": response_text,
                    "conversation_id": None
                }
            else:
                # Data Formatter returned ERROR - run planner formatter anyway (as per TypeScript code)
                planner_formatter_result = await Runner.run(
                    planner_formatter_agent,
                    input=conversation_items,
                    run_config=run_config
                )
                
                if not planner_formatter_result.final_output:
                    raise RuntimeError("PLANNER Formatter agent result is undefined")
                
                # Convert formatter output to dict
                if hasattr(planner_formatter_result.final_output, 'model_dump'):
                    formatter_output = planner_formatter_result.final_output.model_dump()
                else:
                    formatter_output = planner_formatter_result.final_output if isinstance(planner_formatter_result.final_output, dict) else {}
                
                # Build response - this will likely be an error
                error_msg = formatter_output.get("consoleMessage", "Data validation failed")
                response_text = f"Error: {error_msg}"
                
                return {
                    "response": response_text,
                    "conversation_id": None
                }
        else:
            # INSIGHT returned OBJECT_NOT_FOUND - run INSIGHT Formatter Agent
            insight_formatter_result = await Runner.run(
                insight_formatter_agent,
                input=conversation_items,
                run_config=run_config
            )
            
            if not insight_formatter_result.final_output:
                raise RuntimeError("INSIGHT Formatter agent result is undefined")
            
            # Convert formatter output to dict or string
            if hasattr(insight_formatter_result.final_output, 'model_dump'):
                formatter_output = insight_formatter_result.final_output.model_dump()
            elif isinstance(insight_formatter_result.final_output, dict):
                formatter_output = insight_formatter_result.final_output
            else:
                formatter_output = {"output": str(insight_formatter_result.final_output)}
            
            # Build response
            response_text = json.dumps(formatter_output, indent=2) if isinstance(formatter_output, dict) else str(formatter_output)
            
            return {
                "response": response_text,
                "conversation_id": None
            }
        
    elif status == "MISSION_READY":
        # Run PLANNER agent
        planner_result = await Runner.run(
            planner_agent,
            input=conversation_items,
            run_config=run_config
        )
        
        if not planner_result.final_output:
            raise RuntimeError("PLANNER agent result is undefined")
        
        # Add PLANNER's response to conversation history
        if hasattr(planner_result, 'new_items') and planner_result.new_items:
            for item in planner_result.new_items:
                raw_item = getattr(item, 'raw_item', item)
                if isinstance(raw_item, dict):
                    conversation_items.append(raw_item)
        
        # Run PLANNER Formatter Agent
        planner_formatter_result = await Runner.run(
            planner_formatter_agent,
            input=conversation_items,
            run_config=run_config
        )
        
        if not planner_formatter_result.final_output:
            raise RuntimeError("PLANNER Formatter agent result is undefined")
        
        # Convert formatter output to dict
        if hasattr(planner_formatter_result.final_output, 'model_dump'):
            formatter_output = planner_formatter_result.final_output.model_dump()
        else:
            formatter_output = planner_formatter_result.final_output if isinstance(planner_formatter_result.final_output, dict) else {}
        
        # Build response based on formatter output
        if formatter_output.get("status") == "OK":
            response_text = f"Mission plan created successfully:\n{json.dumps({'mission_id': formatter_output.get('missionId'), 'priority': formatter_output.get('priority'), 'tasks': formatter_output.get('tasks')}, indent=2)}"
        else:
            error_msg = formatter_output.get("consoleMessage", "Failed to create mission plan")
            response_text = f"Error: {error_msg}"
        
        return {
            "response": response_text,
            "conversation_id": None
        }
        
    else:
        # Run SARA Formatter Agent for ERROR or MISSION_DATA_MISSING cases
        sara_formatter_result = await Runner.run(
            sara_formatter_agent,
            input=conversation_items,
            run_config=run_config
        )
        
        if not sara_formatter_result.final_output:
            raise RuntimeError("SARA Formatter agent result is undefined")
        
        # Convert formatter output to dict
        if hasattr(sara_formatter_result.final_output, 'model_dump'):
            formatter_output = sara_formatter_result.final_output.model_dump()
        else:
            formatter_output = sara_formatter_result.final_output if isinstance(sara_formatter_result.final_output, dict) else {}
        
        # Convert to a natural language response for the chat
        formatter_status = formatter_output.get("status", status)
        if formatter_status == "MISSION_DATA_MISSING":
            missing_fields = formatter_output.get("missingFields", [])
            console_message = formatter_output.get("consoleMessage", "Missing required fields")
            response_text = f"{console_message}. Missing fields: {', '.join(missing_fields)}"
        elif formatter_status == "ERROR":
            console_message = formatter_output.get("consoleMessage", "I could not understand the request.")
            response_text = console_message
        else:
            response_text = json.dumps(formatter_output, indent=2)
        
        return {
            "response": response_text,
            "conversation_id": None
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

