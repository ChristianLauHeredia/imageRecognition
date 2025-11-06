# Guía de Deploy

Este proyecto está listo para hacer deploy en cualquier plataforma que soporte Python 3.9+ y FastAPI.

## Requisitos para Deploy

- Python 3.9 o superior
- Variables de entorno configuradas (especialmente `OPENAI_API_KEY`)

## Plataformas Recomendadas

### 1. Railway

```bash
# Instalar Railway CLI
npm i -g @railway/cli

# Login y crear proyecto
railway login
railway init

# Configurar variables de entorno
railway variables set OPENAI_API_KEY=sk-tu-api-key

# Deploy
railway up
```

### 2. Render

1. Conecta tu repositorio en https://render.com
2. Crea un nuevo "Web Service"
3. Configuración:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Environment Variables**: Agrega `OPENAI_API_KEY`

### 3. Fly.io

```bash
# Instalar Fly CLI
curl -L https://fly.io/install.sh | sh

# Login
fly auth login

# Crear app
fly launch

# Configurar secrets
fly secrets set OPENAI_API_KEY=sk-tu-api-key

# Deploy
fly deploy
```

### 4. Heroku

```bash
# Instalar Heroku CLI
# Login
heroku login

# Crear app
heroku create tu-app-name

# Configurar variables
heroku config:set OPENAI_API_KEY=sk-tu-api-key

# Deploy
git push heroku main
```

### 5. Google Cloud Run

```bash
# Instalar gcloud CLI
# Configurar proyecto
gcloud config set project TU-PROJECT-ID

# Build y deploy
gcloud builds submit --tag gcr.io/TU-PROJECT-ID/image-recognition
gcloud run deploy image-recognition \
  --image gcr.io/TU-PROJECT-ID/image-recognition \
  --platform managed \
  --region us-central1 \
  --set-env-vars OPENAI_API_KEY=sk-tu-api-key
```

### 6. Vercel

Vercel tiene soporte nativo para FastAPI:

```bash
# Instalar Vercel CLI
npm install -g vercel

# Login
vercel login

# Deploy
vercel

# Para producción
vercel --prod
```

**Configuración:**
- Vercel detecta automáticamente FastAPI si está en `app/main.py` o `api/index.py`
- Configura `OPENAI_API_KEY` en el dashboard de Vercel: Settings > Environment Variables
- El archivo `vercel.json` ya está configurado en el proyecto

**Nota:** Vercel funciona con funciones serverless, así que puede haber limitaciones con archivos grandes o procesos de larga duración.

### 7. AWS Lambda (con Mangum)

Si quieres usar AWS Lambda, necesitarás un wrapper como Mangum:

```bash
pip install mangum
```

Y modificar el código para usar Mangum como handler.

## Variables de Entorno Necesarias

- `OPENAI_API_KEY`: Tu API key de OpenAI (requerida)

## Archivos Necesarios para Deploy

Asegúrate de incluir estos archivos en tu repositorio:

- `requirements.txt` - Dependencias del proyecto
- `app/` - Código de la aplicación
- `.gitignore` - Para excluir archivos sensibles
- `README.md` - Documentación

**NO incluir:**
- `.env` - Está en .gitignore, usa variables de entorno de la plataforma
- `.venv/` - Se crea en el servidor
- `openai-agents-python/` - El SDK se instala desde PyPI

## Verificación Post-Deploy

Una vez desplegado, verifica que funciona:

```bash
# Verificar que el servidor responde
curl https://tu-app.com/docs

# Probar el endpoint
curl -X POST https://tu-app.com/analyze \
  -F "prompt=detect a stop sign" \
  -F "image=@ruta/a/imagen.jpg"
```

## Notas Importantes

1. **API Key**: Nunca subas tu API key al repositorio. Usa siempre variables de entorno de la plataforma.

2. **Puerto**: Algunas plataformas (como Render, Railway) asignan el puerto dinámicamente. El código actual usa `--host 0.0.0.0 --port 8000`, pero algunas plataformas requieren leer `$PORT`:
   ```python
   import os
   port = int(os.getenv("PORT", 8000))
   ```

3. **Dependencias**: El SDK `openai-agents` se instala automáticamente desde PyPI al ejecutar `pip install -r requirements.txt`.

4. **Logs**: Revisa los logs de la plataforma si hay problemas. El código muestra advertencias si falta la API key.


