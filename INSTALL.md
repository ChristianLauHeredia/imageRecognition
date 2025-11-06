# Guía de Instalación

## Estado Actual

✅ **Código completo**: Todos los archivos del proyecto están creados y listos
✅ **Agente integrado**: El código del agente `vision_analyzer` está integrado
⏳ **Esperando**: Instalación de herramientas de desarrollo de Xcode

## Pasos para Completar la Instalación

### 1. Completar Instalación de Xcode Command Line Tools

Se ha iniciado la instalación automática. Deberías ver un diálogo en macOS pidiendo confirmación.

**Si no aparece el diálogo**, ejecuta manualmente:
```bash
xcode-select --install
```

**Espera a que termine** (puede tomar varios minutos, ~1-2 GB de descarga).

### 2. Verificar que Python Funciona

Una vez completada la instalación, verifica:
```bash
python3 --version
```

Deberías ver algo como: `Python 3.x.x`

### 3. Ejecutar el Script de Setup

```bash
cd /Users/arkus/Documents/Projects/imageRecognition
./setup.sh
```

Este script automáticamente:
- Detecta Python disponible
- Crea el entorno virtual `.venv`
- Instala todas las dependencias de `requirements.txt`

### 4. Activar el Entorno Virtual (si no se activó automáticamente)

```bash
source .venv/bin/activate
```

### 5. Ejecutar el Servidor

```bash
uvicorn app.main:app --reload
```

El servidor estará disponible en: `http://localhost:8000`

## Verificación

Una vez que el servidor esté corriendo, puedes:

1. **Ver la documentación interactiva**: http://localhost:8000/docs
2. **Probar el endpoint**:
   ```bash
   curl -X POST http://localhost:8000/analyze \
     -F "prompt=detect a stop sign" \
     -F "image=@ruta/a/tu/imagen.jpg"
   ```

## Solución de Problemas

### Python no funciona después de instalar Xcode
- Cierra y vuelve a abrir la terminal
- Verifica: `which python3`

### Error al instalar dependencias
- Asegúrate de tener conexión a internet
- Verifica: `pip --version`
- Si falla, intenta: `pip install --upgrade pip` primero

### Error "agents module not found"
- El SDK `agents` debe estar instalado en tu entorno
- Verifica que esté en `requirements.txt` o instálalo manualmente

## Próximos Pasos

Una vez que todo esté funcionando:
1. Ejecuta los tests: `pytest tests/`
2. Revisa la documentación en `/docs`
3. Prueba con imágenes reales


