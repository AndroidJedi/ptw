FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN groupadd --system --gid 10001 ptw && useradd --system --uid 10001 --gid ptw ptw
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY common ./common
COPY commander ./commander
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "commander.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]

