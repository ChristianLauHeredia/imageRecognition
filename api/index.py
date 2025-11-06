"""
Punto de entrada para Vercel Serverless Functions
Vercel busca archivos en el directorio /api/ para funciones serverless
"""
import sys
from pathlib import Path

# Agregar el directorio raíz al path para importar app
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

# Importar la app de FastAPI
from app.main import app

# Vercel detecta automáticamente FastAPI y usa el objeto app directamente
# No necesitamos un handler wrapper adicional
