FROM python:3.10-slim AS builder

LABEL org.opencontainers.image.title="Raven"
LABEL org.opencontainers.image.description="AI-powered dark web OSINT — fork of Robin, with optional VPN egress and simplified startup."
LABEL org.opencontainers.image.source="https://github.com/apurvsinghgautam/robin"

RUN DEBIAN_FRONTEND="noninteractive" apt-get update && \
    apt-get install -y --no-install-recommends \
      tor \
      build-essential \
      curl \
      libssl-dev \
      libffi-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install -r requirements.txt

COPY . .

RUN chmod +x /app/entrypoint.sh

EXPOSE 8501

ENTRYPOINT ["/app/entrypoint.sh"]