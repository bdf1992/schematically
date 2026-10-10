ARG PLAYWRIGHT_VERSION

FROM node:22-bookworm-slim AS node

FROM mcr.microsoft.com/playwright/python:v${PLAYWRIGHT_VERSION}-noble
COPY --from=node /usr/local/bin/node /usr/local/bin/node
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
ENV PIP_BREAK_SYSTEM_PACKAGES=1
COPY requirements-dev.txt /tmp/requirements-dev.txt
RUN python3 -m pip install --no-cache-dir -r /tmp/requirements-dev.txt
