# Backend image. Multi-stage isn't needed here (no compiled build step for
# Python), but we still keep the image lean by only copying what's needed
# and not shipping the frontend's node_modules into the API container.
FROM python:3.11-slim

WORKDIR /app

# System deps for psycopg2 (Postgres client headers).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY conftest.py pytest.ini ./

EXPOSE 8000

CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
