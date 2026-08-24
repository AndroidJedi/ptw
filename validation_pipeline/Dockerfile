FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TZ=Europe/Kyiv
WORKDIR /app
COPY requirements-validation.txt ./
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r requirements-validation.txt \
    && useradd --system --uid 10001 validation
COPY validation_pipeline ./validation_pipeline
COPY natal/assets/inter.ttf /app/natal/assets/inter.ttf
COPY natal/assets/logo-natal.png /app/natal/assets/logo-natal.png
COPY commander/ids.py ./commander/ids.py
COPY commander/__init__.py ./commander/__init__.py
USER validation
CMD ["uvicorn", "validation_pipeline.api:create_app_from_env", "--factory", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
