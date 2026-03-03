#!/usr/bin/env bash
# build.sh - Render build script

set -o errexit

echo "=== Installing system packages ==="
apt-get update -qq
apt-get install -y -qq poppler-utils tesseract-ocr libpq-dev build-essential libffi-dev libjpeg-dev zlib1g-dev libfreetype6-dev

echo "=== Upgrading pip ==="
pip install --upgrade pip setuptools wheel

echo "=== Installing Python dependencies ==="
pip install --prefer-binary -r requirements.txt

echo "=== Build complete ==="
