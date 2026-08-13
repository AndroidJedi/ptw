FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements-commander.txt ./
RUN pip install --no-cache-dir -r requirements-commander.txt

COPY commander ./commander
COPY config ./config
COPY assets/fonts ./assets/fonts

RUN groupadd --system --gid 10001 commander \
    && useradd --system --uid 10001 --gid 10001 commander \
    && mkdir -p /var/lib/ptw/assets \
    && chown -R commander:commander /var/lib/ptw
USER commander

CMD ["uvicorn", "commander.api:create_app_from_env", "--factory", "--host", "0.0.0.0", "--port", "8080"]
