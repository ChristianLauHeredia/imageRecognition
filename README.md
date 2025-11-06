# Vision Agent Proxy API

API FastAPI que expone un endpoint para análisis de imágenes usando el agente `vision_analyzer`.

## Requisitos Previos

- Python 3.11 (o superior)
- Herramientas de desarrollo de Xcode (se instalan automáticamente si no están)

## Setup

### Opción 1: Script automático (recomendado)

```bash
./setup.sh
```

Este script:
- Verifica Python
- Crea el entorno virtual
- Instala todas las dependencias

### Opción 2: Manual

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

**Nota:** Si no tienes Python 3.11, puedes usar `python3` (el script detectará la versión disponible).

**Nota:** El SDK `openai-agents` se instala automáticamente desde PyPI al ejecutar `pip install -r requirements.txt`. No necesitas clonar el repositorio del SDK manualmente.

## Configurar OPENAI_API_KEY

El SDK de agents busca automáticamente la variable de entorno `OPENAI_API_KEY`. Configúrala antes de ejecutar el servidor:

### Opción 1: Variable de entorno (recomendado)

```bash
export OPENAI_API_KEY=sk-tu-api-key-aqui
```

### Opción 2: Archivo .env (con python-dotenv)

1. Copia el archivo de ejemplo:
   ```bash
   cp env.example .env
   ```

2. Edita `.env` y agrega tu API key:
   ```
   OPENAI_API_KEY=sk-tu-api-key-aqui
   ```

3. Carga las variables antes de ejecutar:
   ```bash
   source .env  # o usa python-dotenv
   ```

### Obtener tu API Key

1. Ve a https://platform.openai.com/api-keys
2. Crea una nueva API key
3. Copia la key (empieza con `sk-`)

**Nota:** El servidor mostrará una advertencia al iniciar si la API key no está configurada.

## Ejecutar

### Opción 1: Script automático (recomendado)

El script `run.sh` carga automáticamente las variables de entorno desde `.env`:

```bash
./run.sh
```

### Opción 2: Manual

```bash
# Activar entorno virtual
source .venv/bin/activate

# Cargar variables de entorno desde .env
source .env

# Ejecutar servidor
uvicorn app.main:app --reload
```

O con la API key directamente:

```bash
source .venv/bin/activate
OPENAI_API_KEY=sk-tu-api-key-aqui uvicorn app.main:app --reload
```

## Ejemplo de uso

```bash
curl -X POST http://localhost:8000/analyze \
  -F "prompt=detect a stop sign" \
  -F "image=@samples/stop.jpg"
```

### Respuesta esperada

```json
{
  "found": true,
  "confidence": 0.87,
  "boxes": [
    {
      "x": 0.12,
      "y": 0.34,
      "w": 0.22,
      "h": 0.19,
      "confidence": 0.83
    }
  ]
}
```

## Tests

```bash
pytest tests/
```

## Deploy

Este proyecto está listo para hacer deploy en cualquier plataforma que soporte Python y FastAPI. Ver [DEPLOY.md](DEPLOY.md) para instrucciones detalladas.

**Plataformas soportadas:**
- **Vercel** ⭐ (Recomendado para serverless)
- Railway
- Render
- Fly.io
- Heroku
- Google Cloud Run
- AWS Lambda (con configuración adicional)
- Docker

## Estructura

- `app/main.py` - FastAPI app y endpoint `/analyze`
- `app/agent_def.py` - Definición del agente y funciones auxiliares
- `app/schemas.py` - Modelos Pydantic para validación
- `tests/test_contract.py` - Tests de contrato
- `Dockerfile` - Configuración para deploy con Docker
- `Procfile` - Configuración para plataformas como Heroku
- `vercel.json` - Configuración para Vercel
- `api/index.py` - Punto de entrada para Vercel Serverless Functions
- `DEPLOY.md` - Guía completa de deploy
- `VERCEL.md` - Guía específica para deploy en Vercel

