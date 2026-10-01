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

# Qué versión (commit) corre. Se pasa **al arrancar** el contenedor (`-e FINANZAS_VERSION=...`):
# con un ARG de build, podman reutilizaba la capa cacheada y la imagen se quedaba con la versión
# vieja aunque el build dijera «Successfully tagged» (pasó, y es justo lo que esta variable existe
# para detectar). Aquí queda como valor por defecto para quien no lo pase.
ARG FINANZAS_VERSION=desconocida
ENV FINANZAS_VERSION=$FINANZAS_VERSION

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
