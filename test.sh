#!/usr/bin/env bash
# this_file: test.sh
set -euo pipefail
cd "$(dirname "$0")"
uv run --extra test --extra gui python -m pytest -xq --cov=vexy_speakup
uv run --extra test --extra gui ruff check src tests
