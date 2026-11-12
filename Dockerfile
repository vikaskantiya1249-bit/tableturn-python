# The app as an image. Data on a volume at /data, every setting from --env-file, logs to stdout.
FROM python:3.12-slim

WORKDIR /app
COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock

COPY tableturn ./tableturn
COPY seed ./seed

ENV HOST=0.0.0.0 \
    PORT=8080 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

VOLUME ["/data"]

EXPOSE 8080

CMD ["sh", "-c", "exec uvicorn tableturn.app:app --host \"$HOST\" --port \"$PORT\""]