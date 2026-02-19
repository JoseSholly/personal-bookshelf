FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential gcc libffi-dev libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy project
COPY . .

# Add entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh


ENTRYPOINT ["/entrypoint.sh"]
