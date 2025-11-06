FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements y instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código de la aplicación
COPY app/ ./app/

# Exponer puerto
EXPOSE 8000

# Variable de entorno para el puerto (compatible con plataformas como Render, Railway)
ENV PORT=8000

# Comando para ejecutar la aplicación
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}


