FROM node:22-slim AS node-runtime

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl git openssh-client \
    && rm -rf /var/lib/apt/lists/*
COPY --from=node-runtime /usr/local/bin/node /usr/local/bin/node
COPY --from=node-runtime /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx
COPY requirements-owner-gateway.txt ./
RUN pip install --no-cache-dir -r requirements-owner-gateway.txt
COPY commander ./commander
COPY idea_generation ./idea_generation
COPY owner_gateway ./owner_gateway
COPY config ./config
COPY commander/assets/fonts ./commander/assets/fonts
RUN groupadd --system --gid 10002 owner-gateway \
    && useradd --system --uid 10002 --gid 10002 --create-home owner-gateway \
    && mkdir -p /var/lib/ptw-owner \
    && chown -R owner-gateway:owner-gateway /var/lib/ptw-owner
USER owner-gateway
RUN git config --global --add safe.directory /workspace
CMD ["uvicorn", "owner_gateway.api:create_app_from_env", "--factory", "--host", "0.0.0.0", "--port", "8088"]
