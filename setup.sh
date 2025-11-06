#!/bin/bash
# Script para configurar el entorno del proyecto

set -e

echo "🚀 Configurando entorno del proyecto Vision Agent Proxy..."
echo ""

# Verificar Python 3.11
echo "1. Verificando Python 3.11..."
if command -v python3.11 &> /dev/null; then
    PYTHON_CMD=python3.11
    echo "   ✓ Python 3.11 encontrado"
elif command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    PYTHON_CMD=python3
    echo "   ⚠ Usando Python $PYTHON_VERSION (se recomienda 3.11)"
else
    echo "   ✗ Python no encontrado. Por favor instala Python 3.11"
    exit 1
fi

# Crear entorno virtual
echo ""
echo "2. Creando entorno virtual..."
if [ -d ".venv" ]; then
    echo "   ⚠ Entorno virtual ya existe, omitiendo creación"
else
    $PYTHON_CMD -m venv .venv
    echo "   ✓ Entorno virtual creado"
fi

# Activar entorno virtual
echo ""
echo "3. Activando entorno virtual..."
source .venv/bin/activate

# Actualizar pip
echo ""
echo "4. Actualizando pip..."
pip install --upgrade pip --quiet

# Instalar dependencias
echo ""
echo "5. Instalando dependencias desde requirements.txt..."
pip install -r requirements.txt

echo ""
echo "✅ ¡Configuración completada!"
echo ""
echo "Para activar el entorno virtual en el futuro, ejecuta:"
echo "   source .venv/bin/activate"
echo ""
echo "Para ejecutar el servidor:"
echo "   uvicorn app.main:app --reload"
echo ""


