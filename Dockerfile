# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps (souvent utiles si certaines libs en ont besoin)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
  && rm -rf /var/lib/apt/lists/*

# Install python deps first for better layer caching
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the source
COPY . .

# Create reports dir (si ton app écrit dedans)
RUN mkdir -p reports

EXPOSE 8000

# Lance l'API
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
