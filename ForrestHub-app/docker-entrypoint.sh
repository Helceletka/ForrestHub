#!/bin/sh
set -e

# Persisted data directory (named volume mount target).
DATA_DIR="${FH_DATA_DIR:-/app/data}"
mkdir -p "$DATA_DIR" /app/ForrestHub-logs /app/ForrestHub-games

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

# Align ownership on the shared volumes so the code-server container
# (running as FH_PUID:FH_PGID) can also read/write these files.
FH_PUID="${FH_PUID:-1000}"
FH_PGID="${FH_PGID:-1000}"

# Create / update the runtime group + user to match the requested IDs.
if ! getent group "$FH_PGID" >/dev/null; then
    groupadd -g "$FH_PGID" forresthub 2>/dev/null || addgroup --gid "$FH_PGID" forresthub
fi
if ! getent passwd "$FH_PUID" >/dev/null; then
    useradd -u "$FH_PUID" -g "$FH_PGID" -M -s /usr/sbin/nologin forresthub 2>/dev/null \
        || adduser --uid "$FH_PUID" --gid "$FH_PGID" --disabled-password --gecos "" --no-create-home forresthub
fi

chown -R "$FH_PUID:$FH_PGID" \
    "$DATA_DIR" \
    /app/ForrestHub-logs \
    /app/ForrestHub-games \
    /app/ForrestHub-data.json 2>/dev/null || true

# Make sure newly created files are group-writable so the IDE user can edit them.
umask 0002

exec gosu "$FH_PUID:$FH_PGID" python run.py \
    --host "${FH_HOST:-0.0.0.0}" \
    --port "${FH_PORT:-4444}" \
    ${FH_HOST_QR:+--host-qr "$FH_HOST_QR"} \
    ${FH_SERVER:+--server} \
    $FH_EXTRA_ARGS
