#!/bin/bash
# Script para ejecutar el servidor con variables de entorno cargadas

set -e

cd "$(dirname "$0")"

# Activar entorno virtual
if [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "❌ Entorno virtual no encontrado. Ejecuta ./setup.sh primero"
    exit 1
fi

# Cargar variables de entorno desde .env si existe
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
    echo "✓ Variables de entorno cargadas desde .env"
else
    echo "⚠ Archivo .env no encontrado. Asegúrate de configurar OPENAI_API_KEY"
fi

# Verificar que OPENAI_API_KEY esté configurada
if [ -z "$OPENAI_API_KEY" ]; then
    echo "⚠ ADVERTENCIA: OPENAI_API_KEY no está configurada"
    echo "   Configúrala con: export OPENAI_API_KEY=sk-..."
else
    echo "✓ OPENAI_API_KEY configurada"
fi

# Ejecutar servidor
echo ""
echo "🚀 Iniciando servidor en http://localhost:8000"
echo "   Documentación: http://localhost:8000/docs"
echo ""
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000


