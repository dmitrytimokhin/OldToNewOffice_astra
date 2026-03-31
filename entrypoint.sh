#!/bin/sh

set -e

USER_ID=$(id -u)

export HOME=/tmp
export XDG_RUNTIME_DIR=/tmp/runtime-$USER_ID
export XDG_CONFIG_HOME=/tmp/.config
export XDG_CACHE_HOME=/tmp/.cache
export XDG_DATA_HOME=/tmp/.local/share

mkdir -p "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"

mkdir -p /tmp/libreoffice
mkdir -p /tmp/.config
mkdir -p /tmp/.cache
mkdir -p /tmp/.local/share

exec "$@"