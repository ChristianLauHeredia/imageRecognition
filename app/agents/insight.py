"""
INSIGHT Agent - Visual detector agent for analyzing drone snapshots
"""
from typing import Literal
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


# INSIGHT Agent Schema
class InsightSchema__DroneLocationAtSnapshot(BaseModel):
    model_config = ConfigDict(strict=True)
    
    lat: float
    lon: float
    alt_agl_ft: float


class InsightSchema(BaseModel):
    model_config = ConfigDict(strict=True)
    
    use_case: Literal["OBJECT_CONFIRMED", "OBJECT_NOT_FOUND"] = Field(
        description="Set OBJECT_CONFIRMED if the target object is visible with confidence >= 0.6, else OBJECT_NOT_FOUND."
    )
    mission_id: str = Field(
        description="Mission identifier (e.g., mis_001)."
    )
    priority: int = Field(
        ge=1,
        le=5,
        description="Operational priority; default 3 if not supplied."
    )
    drone_location_at_snapshot: InsightSchema__DroneLocationAtSnapshot


# INSIGHT Agent
insight = Agent(
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


