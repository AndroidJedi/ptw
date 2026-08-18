FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements-commander.txt ./
RUN pip install --no-cache-dir -r requirements-commander.txt && apt-get update && apt-get install -y --no-install-recommends postgresql-client && rm -rf /var/lib/apt/lists/*
COPY idea_system ./idea_system
COPY ideaGeneration ./ideaGeneration
RUN useradd --system --uid 10001 idea
USER idea
CMD ["uvicorn","idea_system.app:create_app","--factory","--host","0.0.0.0","--port","8080","--no-access-log"]
