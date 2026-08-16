FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TZ=Europe/Kyiv
WORKDIR /app
COPY requirements-idea-generation.txt ./
RUN pip install --no-cache-dir -r requirements-idea-generation.txt && useradd --system --uid 10001 idea
COPY idea_generation ./idea_generation
COPY ideaGeneration ./ideaGeneration
COPY db/idea_generation ./db/idea_generation
USER idea
CMD ["python", "-m", "idea_generation"]
