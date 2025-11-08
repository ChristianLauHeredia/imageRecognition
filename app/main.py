from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
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


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Maneja errores de validación y devuelve mensajes claros"""
    errors = exc.errors()
    error_messages = []
    
    for error in errors:
        field = ".".join(str(loc) for loc in error.get("loc", []))
        error_type = error.get("type")
        msg = error.get("msg")
        
        # Mensajes personalizados según el campo
        if "image" in field.lower() or "file" in field.lower():
            error_messages.append("La imagen es requerida")
        elif "prompt" in field.lower():
            error_messages.append("El prompt es requerido")
        elif error_type == "missing":
            error_messages.append(f"El campo '{field}' es requerido")
        else:
            error_messages.append(f"{field}: {msg}")
    
    detail = ". ".join(error_messages) if error_messages else "Error de validación en los datos enviados"
    return JSONResponse(
        status_code=400,
        content={"detail": detail}
    )


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
    # Validar que se proporcionó una imagen
    if not image or not image.filename:
        raise HTTPException(
            status_code=400, 
            detail="La imagen es requerida. Por favor, envía un archivo de imagen."
        )
    
    # Validar que el archivo no esté vacío
    raw = await image.read()
    if not raw or len(raw) == 0:
        raise HTTPException(
            status_code=400,
            detail="El archivo de imagen está vacío. Por favor, envía una imagen válida."
        )
    
    # Validar que abre como imagen
    try:
        img = Image.open(io.BytesIO(raw))
        img.verify()
        # Obtener el formato real de la imagen
        img_format = img.format.lower() if img.format else None
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail="La imagen proporcionada no es válida o está corrupta. Por favor, envía una imagen en formato PNG, JPEG, o similar."
        )
    
    # Usar content_type del UploadFile o detectar desde el formato de la imagen
    mime_type = image.content_type
    if not mime_type and img_format:
        mime_type = f"image/{img_format}"
    if not mime_type:
        mime_type, _ = mimetypes.guess_type(image.filename or "image")
    
    # Validar que el prompt no esté vacío
    if not prompt or not prompt.strip():
        raise HTTPException(
            status_code=400,
            detail="El prompt es requerido. Por favor, proporciona una descripción del objeto a buscar en la imagen."
        )
    
    data_url = to_data_url(raw, image.filename, mime_type=mime_type)
    
    try:
        result_dict = await run_vision(prompt, data_url)
        result = VisionResult.model_validate(result_dict)
        return JSONResponse(content=result.model_dump())
    except HTTPException:
        raise
    except ValueError as e:
        # Errores de validación de Pydantic
        raise HTTPException(
            status_code=500,
            detail=f"Error al procesar la respuesta del agente: {str(e)}"
        )
    except Exception as e:
        # Otros errores - mensaje genérico pero útil
        error_msg = str(e)
        if "api_key" in error_msg.lower() or "OPENAI_API_KEY" in error_msg:
            raise HTTPException(
                status_code=500,
                detail="Error de configuración: La API key de OpenAI no está configurada correctamente."
            )
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor al procesar la imagen. Por favor, intenta nuevamente."
        )

