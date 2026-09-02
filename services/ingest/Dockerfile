FROM python:3.11-slim
WORKDIR /app
COPY services/ingest/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY config /app/config
COPY tests/fixtures /app/tests/fixtures
COPY services/ingest /app/services/ingest
ENV PYTHONPATH=/app/services/ingest
ENV ENABLE_SIM=true
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--app-dir", "/app/services/ingest", "--host", "0.0.0.0", "--port", "8000"]
