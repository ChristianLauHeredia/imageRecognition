# Deploy en Vercel

Vercel tiene soporte nativo para FastAPI. Este proyecto está configurado para funcionar en Vercel.

## Configuración Rápida

### Opción 1: Desde el Dashboard de Vercel (Recomendado)

1. Ve a [vercel.com](https://vercel.com) y haz login
2. Click en "Add New Project"
3. Conecta tu repositorio de GitHub: `ChristianLauHeredia/imageRecognition`
4. Vercel detectará automáticamente que es un proyecto FastAPI
5. Configura las variables de entorno:
   - Ve a Settings > Environment Variables
   - Agrega: `OPENAI_API_KEY` = `tu-api-key`
6. Click en "Deploy"

### Opción 2: Desde la CLI

```bash
# Instalar Vercel CLI
npm install -g vercel

# Login
vercel login

# Desde el directorio del proyecto
cd /Users/arkus/Documents/Projects/imageRecognition

# Deploy (preview)
vercel

# Deploy a producción
vercel --prod
```

## Configuración de Variables de Entorno

En el dashboard de Vercel:
1. Ve a tu proyecto
2. Settings > Environment Variables
3. Agrega:
   - **Name**: `OPENAI_API_KEY`
   - **Value**: `sk-tu-api-key-aqui`
   - **Environment**: Production, Preview, Development (selecciona todos)

## Estructura para Vercel

Vercel detecta automáticamente FastAPI si encuentra:
- `app/main.py` con una instancia de `FastAPI` llamada `app`
- O `api/index.py` con una instancia de `FastAPI`

Este proyecto tiene ambos:
- `app/main.py` - Aplicación principal
- `api/index.py` - Wrapper para Vercel (opcional, Vercel puede usar directamente `app/main.py`)

## Limitaciones de Vercel

- **Tiempo de ejecución**: Máximo 10 segundos en plan gratuito, 60 segundos en plan Pro
- **Tamaño de función**: 250 MB máximo
- **Archivos grandes**: Puede haber limitaciones con imágenes muy grandes
- **Cold starts**: La primera llamada puede ser más lenta

## Verificación Post-Deploy

Una vez desplegado, Vercel te dará una URL como:
```
https://tu-proyecto.vercel.app
```

Prueba el endpoint:
```bash
curl -X POST https://tu-proyecto.vercel.app/analyze \
  -F "prompt=detect a stop sign" \
  -F "image=@ruta/a/imagen.jpg"
```

O visita la documentación interactiva:
```
https://tu-proyecto.vercel.app/docs
```

## Troubleshooting

### Error: "Module not found"
- Asegúrate de que todas las dependencias estén en `requirements.txt`
- Vercel instala automáticamente las dependencias durante el build

### Error: "OPENAI_API_KEY not found"
- Verifica que la variable de entorno esté configurada en el dashboard
- Asegúrate de seleccionar todos los ambientes (Production, Preview, Development)

### Timeout en requests largos
- Vercel tiene límites de tiempo de ejecución
- Considera usar Railway o Render para procesos más largos

## Alternativas Recomendadas

Si encuentras limitaciones con Vercel, considera:
- **Railway** - Excelente para FastAPI, fácil configuración
- **Render** - Similar a Heroku, muy fácil de usar
- **Fly.io** - Buena opción con buen rendimiento

