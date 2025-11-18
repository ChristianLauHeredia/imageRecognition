"""
Planner Agent - Generates mission task plans for autonomous drones
"""
from typing import List, Literal, Optional
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


# Planner Schema (for SARA workflow)
class PlannerSchema__AdditionalData(BaseModel):
    objectType: Optional[str] = None
    visualDescription: Optional[str] = None
    color: Optional[str] = None
    sizeLabel: Optional[str] = None
    notes: Optional[str] = None


class PlannerSchema__TasksItem(BaseModel):
    type: str
    lat: float
    lon: float
    alt_agl_ft: float
    duration_s: float
    speed_mps: float


class PlannerSchema(BaseModel):
    priority: float
    additionalData: PlannerSchema__AdditionalData
    tasks: List[PlannerSchema__TasksItem]


# Route Planner Agent Schema (legacy, kept for backward compatibility)
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
    priority: int = Field(ge=1, le=5, description="Operational priority (1-5).")
    tasks: List[PlannerAgentSchema__TasksItem]


# Route Planner Agent (for SARA workflow)
planner = Agent(
    name="PLANNER",
    instructions="""You are DroneMissionTaskPlanner.

Your job is to generate an initial autonomous drone mission task plan using the validated input

received from the previous agent. You MUST output ONLY valid JSON that matches the required

schema, with NO mission_id, NO commentary, and NO extra fields.

----------------------------------------
EXPECTED INPUT
----------------------------------------
You will receive normalized input including:

{
  "priority": number | null,
  "payload": {
      "waypoint": {
          "lat": number,
          "lon": number,
          "alt_agl_ft": number,
          "fusion_status": "safe" | "nosafe"
      },
      "drone_location"?: {...},
      "additionalData"?: {
          "objectType"?: string,
          "visualDescription"?: string,
          "color"?: string,
          "sizeLabel"?: string,
          "notes"?: string
      }
  }
}

`additionalData` must be included in the output even if empty or partially populated.

----------------------------------------
PRIORITY LOGIC
----------------------------------------
- If priority is null or missing → set priority = 1
- Priority must always be numeric (1–5)

----------------------------------------
TASK GENERATION RULES
----------------------------------------
You must always generate EXACTLY two tasks:

TASK 1 — MOVE_TO
- lat = waypoint.lat
- lon = waypoint.lon
- alt_agl_ft = max(waypoint.alt_agl_ft, 60)
- duration_s = 0
- speed_mps = 3.0

TASK 2 — depends on fusion_status:
- If fusion_status == "safe":
    type = "VISION_WAYPOINT"
    speed_mps = 0.5
    duration_s = 60
    alt_agl_ft = same as MOVE_TO
- If fusion_status == "nosafe":
    type = "LOITER"
    speed_mps = 0
    duration_s = 90
    alt_agl_ft = MOVE_TO alt_agl_ft + 20

----------------------------------------
OUTPUT SCHEMA
----------------------------------------
You MUST output EXACTLY:

{
  "priority": number,
  "additionalData": {
    "objectType"?: string,
    "visualDescription"?: string,
    "color"?: string,
    "sizeLabel"?: string,
    "notes"?: string
  },
  "tasks": [
    {
      "type": "MOVE_TO",
      "lat": number,
      "lon": number,
      "alt_agl_ft": number,
      "duration_s": number,
      "speed_mps": number
    },
    {
      "type": "VISION_WAYPOINT" | "LOITER",
      "lat": number,
      "lon": number,
      "alt_agl_ft": number,
      "duration_s": number,
      "speed_mps": number
    }
  ]
}

----------------------------------------
ADDITIONALDATA RULES
----------------------------------------
- Must always exist in the output.
- If missing in input, output as: {}
- Must never modify meaning or invent values.
- Must NEVER add new keys outside the allowed list.

----------------------------------------
ERROR MODE
----------------------------------------
If required fields are missing or invalid, output:

{
  "priority": 0,
  "additionalData": {},
  "tasks": []
}

----------------------------------------
FINAL RULES
----------------------------------------
- Output ONLY JSON
- NO mission_id
- NO explanations, markdown, or comments
- Exactly one JSON object must be returned
""",
    model="gpt-4.1",
    output_type=AgentOutputSchema(PlannerSchema, strict_json_schema=False),
    model_settings=ModelSettings(
        temperature=1,
        top_p=1,
        max_tokens=2048,
        store=True
    )
)

