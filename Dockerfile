# Optional Docker image. Render's native Python runtime is preferred (see
# render.yaml), but this Dockerfile lets you self-host the same stack on
# any container platform.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "python -m seed.seed && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2"]
