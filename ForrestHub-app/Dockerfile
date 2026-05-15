FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends git curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY . .

# Keep an immutable seed of the default data file so the entrypoint can
# initialise an empty volume on first run.
RUN mkdir -p /app/_seed \
    && cp ForrestHub-data.json /app/_seed/ForrestHub-data.json \
    && chmod +x docker-entrypoint.sh

EXPOSE 4444

ENV FH_HOST=0.0.0.0 \
    FH_PORT=4444 \
    FH_HOST_QR= \
    FH_DATA_DIR=/app/data

ENTRYPOINT ["./docker-entrypoint.sh"]
