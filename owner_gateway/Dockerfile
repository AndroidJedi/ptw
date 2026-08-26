FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements-owner-gateway.txt ./
RUN pip install --no-cache-dir -r requirements-owner-gateway.txt \
    && groupadd --system --gid 10002 owner-gateway \
    && useradd --system --uid 10002 --gid 10002 owner-gateway
COPY owner_gateway ./owner_gateway
USER owner-gateway
CMD ["uvicorn", "owner_gateway.api:create_app_from_env", "--factory", "--host", "0.0.0.0", "--port", "8088"]
