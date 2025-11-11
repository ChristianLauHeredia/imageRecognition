from pydantic import BaseModel
from typing import List, Literal, Optional, Union


class BBox(BaseModel):
    x: float
    y: float
    w: float
    h: float
    confidence: float


class VisionResult(BaseModel):
    found: bool
    confidence: float
    boxes: List[BBox]


# Route Planner Schemas
class Location(BaseModel):
    lat: float
    lon: float
    alt_agl_ft: float


class Waypoint(Location):
    fusion_status: Optional[str] = None


class ObjectConfirmedRequest(BaseModel):
    use_case: Literal["OBJECT_CONFIRMED"]
    mission_id: str
    priority: Literal["high", "medium", "low"]
    drone_location_at_snapshot: Location


class AppendTaskRequest(BaseModel):
    use_case: Literal["APPEND_TASK"]
    mission_id: str
    priority: int
    drone_location: Location
    waypoint: Waypoint
    time_of_execution_s: int


class Task(BaseModel):
    type: str
    lat: float
    lon: float
    alt_agl_ft: float
    duration_s: int


class MissionResponse(BaseModel):
    mission_id: str
    priority: int
    lease_ttl_s: int
    tasks: List[Task]


# Union type for route planner requests
RoutePlannerRequest = Union[ObjectConfirmedRequest, AppendTaskRequest]


