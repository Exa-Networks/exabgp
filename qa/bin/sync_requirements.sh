#!/usr/bin/env bash
# Sync qa/requirements.txt from uv.lock
# Run this after updating dependencies with uv lock or uv add

set -e

echo "Generating qa/requirements.txt from uv.lock..."
uv export --no-hashes --format requirements-txt > qa/requirements.txt
echo "✓ Synced qa/requirements.txt from uv.lock"
