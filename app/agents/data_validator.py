"""
Data Validator Agent - Validates and normalizes incoming drone-mission inputs
"""
from typing import Dict, Any, Optional, List, Literal
from pydantic import BaseModel, ConfigDict, Field
from pathlib import Path

# Load environment variables
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv(override=False)

from agents import Agent, ModelSettings, AgentOutputSchema


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
    priority: int = Field(ge=1, le=5, description="Operational priority (1-5).")
    payload: DataValidatorSchema__Payload
    errors: List[str]


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


