FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/backend

COPY backend/pyproject.toml /app/backend/pyproject.toml
RUN pip install --no-cache-dir fastapi "uvicorn[standard]" pydantic docker

COPY backend /app/backend

EXPOSE 8000

CMD ["python", "backend/run_server.py"]
