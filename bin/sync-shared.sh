#!/usr/bin/env bash
# Copies backend/_shared (core code, requirements, vendored packages) into every service with a function.py.
# Packages are installed once into backend/_shared/.vendor and reinstalled only when requirements.txt changes.
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SHARED="$ROOT/backend/_shared"
VENDOR="$SHARED/.vendor"
STAMP="$VENDOR/.requirements.sha"
REQ_HASH="$(sha256sum "$SHARED/requirements.txt" | cut -d' ' -f1)"

if [ ! -f "$STAMP" ] || [ "$(cat "$STAMP")" != "$REQ_HASH" ]; then
  echo "  installing shared Python packages for Lambda (python 3.13, x86_64)..."
  rm -rf "$VENDOR"
  python3 -m pip install --quiet --break-system-packages \
    --target "$VENDOR" \
    --platform manylinux2014_x86_64 --implementation cp --python-version 3.13 \
    --only-binary=:all: \
    -r "$SHARED/requirements.txt"
  echo "$REQ_HASH" > "$STAMP"
fi

for dir in "$ROOT"/backend/*/; do
  name="$(basename "$dir")"
  case "$name" in _*|.*) continue ;; esac
  [ -f "$dir/function.py" ] || continue
  rm -rf "$dir/core" "$dir/.vendor"
  cp -r "$SHARED/core" "$dir/core"
  cp -r "$VENDOR" "$dir/.vendor"
  cp "$SHARED/requirements.txt" "$dir/requirements.txt"
  echo "  synced shared core -> backend/$name"
done
