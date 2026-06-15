#!/bin/sh
set -eu

DATA_DIR="${QA_AGENT_DATA_DIR:-/app/data}"

if [ "$(id -u)" = "0" ]; then
    mkdir -p "$DATA_DIR"
    chown -R appuser:appuser "$DATA_DIR"
    exec gosu appuser "$@"
fi

exec "$@"
