"""
Vision Analyzer Agent - Analyzes images to detect objects
"""
from typing import Dict, Literal, Union
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


class VisionAnalyzerSchema__DroneLocationAtSnapshot(BaseModel):
    model_config = ConfigDict(strict=True)
    
    lat: float
    lon: float
    alt_agl_ft: float


class VisionAnalyzerSchema(BaseModel):
    model_config = ConfigDict(strict=True)
    
    use_case: Literal["OBJECT_CONFIRMED", "OBJECT_NOT_FOUND"]
    mission_id: str
    priority: int = Field(ge=1, le=5, description="Operational priority; default 3 if not supplied.")
    drone_location_at_snapshot: VisionAnalyzerSchema__DroneLocationAtSnapshot


vision_analyzer = Agent(
    name="Vision Analyzer",
    instructions="""You are a strict visual detector agent. You receive:

an image of a drone snapshot,

a prompt that may contain:
- target_prompt: natural-language description of the object to identify (e.g., "red pickup truck facing north")
- lat, lon, alt_agl_ft: drone location coordinates at capture time
- priority: mission priority (optional, default to 3 if not provided)

mission_id: mission identifier (provided separately)

Task:

1. Extract information from the prompt:
   - Extract the target_prompt (description of object to identify)
   - Extract lat, lon, alt_agl_ft from the prompt (look for patterns like "lat 12.34", "lon -67.89", "alt 100" or "altitude 100 ft")
   - Extract priority if mentioned (default to 3 if not found)

2. Carefully analyze the image and determine if at least one object CLEARLY and UNEQUIVOCALLY matches the target_prompt description.

CRITICAL: You must be very conservative. Only return OBJECT_CONFIRMED if you are HIGHLY CONFIDENT (≥0.85 confidence) that the object is present and matches the description.

If you have ANY doubt, uncertainty, or the object is partially obscured, ambiguous, or could be mistaken for something else, return OBJECT_NOT_FOUND.

Always return only valid JSON that conforms exactly to the provided JSON Schema (see Response Format).

Confidence threshold: ONLY treat as confirmed if your best-estimate confidence ≥ 0.85. Be strict - false positives are worse than false negatives.

drone_location_at_snapshot must include lat, lon, and alt_agl_ft extracted from the prompt. If coordinates are not found in the prompt, use reasonable defaults but this should be rare.

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
    output_type=AgentOutputSchema(VisionAnalyzerSchema, strict_json_schema=False),
    model_settings=ModelSettings(
        temperature=0.3,  # Lower temperature for more conservative, deterministic responses
        top_p=0.9,  # Slightly lower top_p for more focused responses
        max_tokens=2048,
        store=True
    )
)


