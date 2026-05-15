#!/bin/sh
set -e

# Persisted data directory (named volume mount target).
DATA_DIR="${FH_DATA_DIR:-/app/data}"
mkdir -p "$DATA_DIR"

# Seed the data file from the image on first run so the app finds it.
SEED="/app/_seed/ForrestHub-data.json"
TARGET="$DATA_DIR/ForrestHub-data.json"
if [ ! -f "$TARGET" ]; then
    if [ -f "$SEED" ]; then
        cp "$SEED" "$TARGET"
    else
        echo '{}' > "$TARGET"
    fi
fi

# The app writes to /app/ForrestHub-data.json by convention. Point it at the volume.
ln -sf "$TARGET" /app/ForrestHub-data.json

# Ensure log + live games dirs exist (they're typically volume-mounted too).
mkdir -p /app/ForrestHub-logs /app/ForrestHub-games

exec python run.py \
    --host "${FH_HOST:-0.0.0.0}" \
    --port "${FH_PORT:-4444}" \
    ${FH_HOST_QR:+--host-qr "$FH_HOST_QR"} \
    ${FH_SERVER:+--server} \
    $FH_EXTRA_ARGS
