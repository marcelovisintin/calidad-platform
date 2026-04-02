FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# NOTE produccion: agregar usuario no-root con entrypoint que fije ownership
# de volumenes montados antes de hacer exec al proceso de la app.
WORKDIR /srv/calidad/backend

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements /tmp/requirements
RUN pip install --upgrade pip \
    && pip install -r /tmp/requirements/production.txt

COPY backend /srv/calidad/backend
