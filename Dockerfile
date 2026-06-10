# Overridable so CI/sandboxes hitting Docker Hub rate limits can build from a
# mirror, e.g. --build-arg BASE_IMAGE=public.ecr.aws/docker/library/python:3.12-slim
ARG BASE_IMAGE=python:3.12-slim
FROM ${BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Render injects PORT at runtime. gunicorn binds to it; the shell form lets the
# env var interpolate. 2 workers is plenty for this app's traffic profile;
# bump if you see request queueing in Render's metrics.
EXPOSE 8000
CMD gunicorn --workers 2 --threads 4 --timeout 60 --bind 0.0.0.0:${PORT:-8000} app:app
