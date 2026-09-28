FROM python:3.12-slim

WORKDIR /app

# Instalar dependencias y el paquete
COPY pyproject.toml alembic.ini ./
COPY app ./app
COPY alembic ./alembic
RUN pip install --no-cache-dir .

EXPOSE 8000

# Migrar y arrancar la API
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
