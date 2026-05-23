# syntax=docker/dockerfile:1.7

FROM python:3.11-slim-bookworm AS runtime

# Pull JDK 17 from the official image so Lavalink can run.
# JDK 17 is the modern LTS target for Lavalink v4 and works with v3 as well.
COPY --from=eclipse-temurin:17-jdk-jammy /opt/java/openjdk /opt/java/openjdk
ENV JAVA_HOME=/opt/java/openjdk \
    PATH="/opt/java/openjdk/bin:${PATH}"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /usr/src/app

# Build deps for native wheels (curl_cffi, etc.). git is required because
# requirements.txt installs a few packages directly from git.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        gcc \
        git \
        ca-certificates \
        curl \
        libffi-dev \
 && rm -rf /var/lib/apt/lists/*

# Install Python deps first so the layer cache survives source edits.
COPY requirements.txt ./
RUN pip install --upgrade pip wheel setuptools \
 && pip install -r requirements.txt

# Copy the rest of the source tree.
COPY . .

EXPOSE 8080

# A lightweight healthcheck against the RPC web server.
# If RUN_RPC_SERVER is disabled this will become noisy in logs but won't crash the container.
HEALTHCHECK --interval=60s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -fsS http://127.0.0.1:${PORT:-8080}/ >/dev/null || exit 1

CMD ["python", "-u", "main.py"]
