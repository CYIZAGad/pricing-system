#!/usr/bin/env bash
# build.sh — Render build script
# Installs system packages and Python dependencies

set -o errexit  # exit on error

echo "=== Installing system packages ==="
apt-get update -qq && apt-get install -y -qq poppler-utils tesseract-ocr

echo "=== Installing Python dependencies ==="
pip install --upgrade pip
pip install -r requirements.txt

echo "=== Build complete ==="
