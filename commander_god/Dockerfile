FROM node:22.14.0-bookworm-slim AS node-runtime
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TZ=Europe/Kyiv
WORKDIR /app
COPY --from=node-runtime /usr/local/bin/node /usr/local/bin/node
COPY --from=node-runtime /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx
COPY requirements-commander-god.txt ./
RUN apt-get update \
    && apt-get install -y --no-install-recommends git openssh-client ripgrep \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r requirements-commander-god.txt
COPY validation_pipeline/__init__.py ./validation_pipeline/__init__.py
COPY validation_pipeline/commander_chat.py ./validation_pipeline/commander_chat.py
COPY validation_pipeline/commander_chat_worker.py ./validation_pipeline/commander_chat_worker.py
COPY validation_pipeline/commander_host_api.py ./validation_pipeline/commander_host_api.py
COPY validation_pipeline/commander_release.py ./validation_pipeline/commander_release.py
COPY validation_pipeline/commander_rpc.py validation_pipeline/commander_workspace.py validation_pipeline/commander_plan_api.py ./validation_pipeline/

CMD ["uvicorn", "validation_pipeline.commander_host_api:create_app_from_env", "--factory", "--host", "0.0.0.0", "--port", "8095", "--no-access-log"]
