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

EXPOSE 4444

ENV FH_HOST=0.0.0.0 \
    FH_PORT=4444 \
    FH_HOST_QR=

ENTRYPOINT ["sh", "-c", "exec python run.py --host \"${FH_HOST}\" --port \"${FH_PORT}\" ${FH_HOST_QR:+--host-qr \"$FH_HOST_QR\"} ${FH_SERVER:+--server} $FH_EXTRA_ARGS"]
