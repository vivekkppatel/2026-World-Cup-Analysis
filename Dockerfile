# Backend container — FastAPI (api/main.py) over PostgreSQL.
# Works on Render, Railway, Fly.io, Google Cloud Run, etc.
FROM python:3.12-slim

WORKDIR /app

# System deps for psycopg2 / scientific wheels are bundled in the *-binary
# packages, so no apt step is needed for the lean API requirements.
COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

# Copy only what the API needs at runtime.
COPY api/ ./api/
COPY database/ ./database/
COPY models/ ./models/
COPY data/ ./data/
COPY scripts/ ./scripts/

# Hosts inject $PORT; default to 8000 locally.
ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT}"]
