FROM node:22.14.0-bookworm-slim AS template-preview
WORKDIR /build
COPY apps/commander-web/package*.json ./apps/commander-web/
RUN npm --prefix apps/commander-web ci
COPY apps/commander-web ./apps/commander-web
COPY natal/assets ./natal/assets
COPY validation_pipeline/studio_assets ./validation_pipeline/studio_assets
RUN npm --prefix apps/commander-web run build:template-preview

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TZ=Europe/Kyiv
WORKDIR /app
COPY requirements-validation.txt ./
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-dejavu-core git ripgrep nodejs chromium \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r requirements-validation.txt \
    && groupadd --gid 10001 validation \
    && useradd --system --uid 10001 --gid validation validation
COPY validation_pipeline ./validation_pipeline
COPY commander/ids.py ./commander/ids.py
COPY commander/__init__.py ./commander/__init__.py
COPY natal/assets/logo-natal.png ./natal/assets/logo-natal.png
COPY natal/assets/inter.ttf ./natal/assets/inter.ttf
COPY --from=template-preview /build/.local/template-preview ./template-preview
COPY --from=template-preview /build/apps/commander-web/node_modules/playwright ./apps/commander-web/node_modules/playwright
COPY --from=template-preview /build/apps/commander-web/node_modules/playwright-core ./apps/commander-web/node_modules/playwright-core
COPY apps/commander-web/scripts/render-template-landing.mjs ./apps/commander-web/scripts/render-template-landing.mjs
ENV PTW_TEMPLATE_PREVIEW_BUNDLE=/app/template-preview PTW_TEMPLATE_CHROMIUM=/usr/bin/chromium
USER validation
CMD ["uvicorn", "validation_pipeline.api:create_app_from_env", "--factory", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
