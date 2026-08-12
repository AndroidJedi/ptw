FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
ARG FLUTTER_VERSION=3.44.9
ARG FLUTTER_SHA256=a9120fa4a01048bdef438ddc3a2d4b7389662ea98a95db86eeaf10382bc4efcb
RUN groupadd --system --gid 10001 ptw && useradd --system --uid 10001 --gid ptw ptw \
    && apt-get update && apt-get install -y --no-install-recommends git openssh-client curl xz-utils \
    && curl -fsSLo /tmp/flutter.tar.xz "https://storage.googleapis.com/flutter_infra_release/releases/stable/linux/flutter_linux_${FLUTTER_VERSION}-stable.tar.xz" \
    && echo "${FLUTTER_SHA256}  /tmp/flutter.tar.xz" | sha256sum -c - \
    && tar -xJf /tmp/flutter.tar.xz -C /opt \
    && git config --system --add safe.directory /opt/flutter \
    && /opt/flutter/bin/flutter config --no-analytics \
    && rm -rf /var/lib/apt/lists/*
ENV PATH="/opt/flutter/bin:/opt/flutter/bin/cache/dart-sdk/bin:${PATH}"
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY common ./common
COPY commander ./commander
COPY engineering ./engineering
COPY worker ./worker
COPY watcher ./watcher
USER 10001:10001
CMD ["python", "-m", "worker.main"]
