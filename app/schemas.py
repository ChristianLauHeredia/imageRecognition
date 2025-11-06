from pydantic import BaseModel
from typing import List


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


