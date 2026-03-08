FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
COPY backend/ backend/
RUN pip install .
CMD ["uvicorn", "nexus.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
