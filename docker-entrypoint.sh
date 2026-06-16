#!/bin/sh
set -eu

DATA_DIR="${QA_AGENT_DATA_DIR:-/app/data}"
PERMISSION_MARKER="${DATA_DIR}/.qa-agent-permissions-ready"
FORCE_RECURSIVE_CHOWN="${QA_AGENT_FORCE_RECURSIVE_CHOWN:-0}"

if [ "$(id -u)" = "0" ]; then
    mkdir -p "$DATA_DIR"
    if [ "$FORCE_RECURSIVE_CHOWN" = "1" ] || [ ! -f "$PERMISSION_MARKER" ]; then
        chown -R appuser:appuser "$DATA_DIR"
        touch "$PERMISSION_MARKER"
    fi
    chown appuser:appuser "$DATA_DIR" "$PERMISSION_MARKER"
    exec gosu appuser "$@"
fi

exec "$@"
