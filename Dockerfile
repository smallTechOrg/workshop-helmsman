FROM python:3.11-slim

WORKDIR /app

# Local-only dependencies. No network calls required at runtime.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY frontend ./frontend

ENV BIND_HOST=0.0.0.0 BIND_PORT=8001 PYTHONUNBUFFERED=1

EXPOSE 8001
CMD ["python", "-m", "src"]
