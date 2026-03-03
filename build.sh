#!/usr/bin/env bash
# build.sh Ã¢â‚¬â€ Render build script
# Installs system packages and Python dependencies

set -o errexit  # exit on error

echo "=== Installing system packages ==="
apt-get update -qq
apt-get install -y -qq \
  poppler-utils \
  tesseract-ocr \
  libpq-dev \
  build-essential \
  libffi-dev \
  libjpeg-dev \
  zlib1g-dev \
  libfreetype6-dev

echo "=== Installing Python dependencies ==="
pip install --upgrade pip setuptools wheel
pip install --prefer-binary -r requirements.txt

echo "=== Build complete ==="
