FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN groupadd --system --gid 10001 ptw && useradd --system --uid 10001 --gid ptw ptw \
    && apt-get update && apt-get install -y --no-install-recommends git openssh-client \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY common ./common
COPY watcher ./watcher
USER 10001:10001
CMD ["python", "-m", "watcher.main"]
