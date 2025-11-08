from typing import List, Dict, Any, Optional
import base64
import mimetypes
from pathlib import Path
from pydantic import BaseModel

# Cargar variables de entorno desde .env antes de importar el SDK de agents
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

from agents import Agent, ModelSettings, TResponseInputItem, Runner, RunConfig, trace


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


class WorkflowInput(BaseModel):
    input_as_text: str


# Main code entrypoint
async def run_workflow(workflow_input: WorkflowInput):
    with trace("Image recognition"):
        state = {}
        workflow = workflow_input.model_dump()
        conversation_history: list[TResponseInputItem] = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": workflow["input_as_text"]
                    }
                ]
            }
        ]
        vision_analyzer_result_temp = await Runner.run(
            vision_analyzer,
            input=[
                *conversation_history
            ],
            run_config=RunConfig(trace_metadata={
                "__trace_source__": "agent-builder",
                "workflow_id": "wf_690bb53b414081909b10b956dce260b509d21cb3785aa894"
            })
        )

        conversation_history.extend([item.to_input_item() for item in vision_analyzer_result_temp.new_items])

        vision_analyzer_result = {
            "output_text": vision_analyzer_result_temp.final_output.json(),
            "output_parsed": vision_analyzer_result_temp.final_output.model_dump()
        }


def to_data_url(data: bytes, filename: str, mime_type: Optional[str] = None) -> str:
    """Convierte datos binarios a data URL en formato base64.
    
    Args:
        data: Datos binarios de la imagen
        filename: Nombre del archivo (para detectar MIME type si no se proporciona)
        mime_type: MIME type opcional (si se proporciona, se usa en lugar de detectar)
    
    Returns:
        Data URL en formato: data:image/{format};base64,{base64_encoded_data}
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
    # final_output ya es un modelo pydantic del schema → convertir a dict limpio
    return result.final_output.model_dump()

