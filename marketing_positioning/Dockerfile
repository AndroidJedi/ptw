FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TZ=Europe/Kyiv
WORKDIR /app
COPY requirements-marketing-positioning.txt ./
RUN pip install --no-cache-dir -r requirements-marketing-positioning.txt && useradd --system --uid 10001 positioning
COPY marketing_positioning ./marketing_positioning
COPY commander/ids.py ./commander/ids.py
COPY commander/__init__.py ./commander/__init__.py
USER positioning
CMD ["uvicorn", "marketing_positioning.api:create_app_from_env", "--factory", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
