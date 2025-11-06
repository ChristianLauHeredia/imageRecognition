from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from PIL import Image
import io
import os
import mimetypes
from pathlib import Path

# Cargar variables de entorno desde .env antes de importar el SDK de agents
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

from app.schemas import VisionResult
from app.agent_def import to_data_url, run_vision


app = FastAPI(title="Vision Agent Proxy", version="1.0.0")


@app.on_event("startup")
async def startup_event():
    """Verificar que OPENAI_API_KEY esté configurada al iniciar"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        import warnings
        warnings.warn(
            "OPENAI_API_KEY no está configurada. "
            "Configúrala como variable de entorno antes de ejecutar el servidor.",
            UserWarning
        )


@app.post("/analyze")
async def analyze(prompt: str = Form(...), image: UploadFile = File(...)):
    if not image or not image.filename:
        raise HTTPException(status_code=400, detail="image file is required")
    
    # validar que abre como imagen
    raw = await image.read()
    try:
        img = Image.open(io.BytesIO(raw))
        img.verify()
        # Obtener el formato real de la imagen
        img_format = img.format.lower() if img.format else None
    except Exception:
        raise HTTPException(status_code=400, detail="invalid image")
    
    # Usar content_type del UploadFile o detectar desde el formato de la imagen
    mime_type = image.content_type
    if not mime_type and img_format:
        mime_type = f"image/{img_format}"
    if not mime_type:
        mime_type, _ = mimetypes.guess_type(image.filename or "image")
    
    data_url = to_data_url(raw, image.filename, mime_type=mime_type)
    
    try:
        result_dict = await run_vision(prompt, data_url)
        result = VisionResult.model_validate(result_dict)
        return JSONResponse(content=result.model_dump())
    except HTTPException:
        raise
    except Exception as e:
        # Nota: no revelar trazas; mensaje claro
        raise HTTPException(status_code=500, detail=str(e))

