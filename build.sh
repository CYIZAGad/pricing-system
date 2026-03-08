#!/usr/bin/env bash
# build.sh - Render build script

set -o errexit

echo "=== Installing system packages (if available) ==="
if command -v apt-get &> /dev/null && [ -w /var/lib/apt/lists ]; then
  apt-get update -qq
  apt-get install -y -qq poppler-utils tesseract-ocr libpq-dev build-essential libffi-dev libjpeg-dev zlib1g-dev libfreetype6-dev
else
  echo "Skipping apt-get (read-only filesystem or not available)"
fi

echo "=== Upgrading pip ==="
pip install --upgrade pip setuptools wheel

echo "=== Installing Python dependencies ==="
pip install --prefer-binary "numpy>=1.26,<2.0"
pip install --prefer-binary -r requirements.txt

echo "=== Build complete ==="
