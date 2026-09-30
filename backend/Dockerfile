FROM python:3.12-slim

WORKDIR /app

# OCR de facturas: tesseract (con español) + poppler (para pdf2image)
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-spa poppler-utils \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml alembic.ini ./
COPY app ./app
COPY alembic ./alembic
RUN pip install --no-cache-dir .

# Qué versión (commit) está corriendo esta imagen. Va al final para no invalidar la caché del
# código en cada despliegue, y es lo que permite comprobar que lo desplegado es lo que se cree.
ARG FINANZAS_VERSION=desconocida
ENV FINANZAS_VERSION=$FINANZAS_VERSION

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
