FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=10000

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt tzdata

COPY . ./
RUN mkdir -p /app/data \
    && useradd --system --home /app donchi \
    && chown -R donchi:donchi /app
USER donchi

EXPOSE 10000
CMD ["sh", "-c", "exec python -m uvicorn server:app --host 0.0.0.0 --port ${PORT:-10000}"]
