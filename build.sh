#!/usr/bin/env bash
# this_file: build.sh
# Test, build and check the sdist and wheel in dist/.
# The version comes from the git tag on HEAD (hatch-vcs). An untagged or dirty
# tree builds a dev version with a local segment, which PyPI rejects.
# Usage: ./build.sh [--skip-tests]
set -euo pipefail
cd "$(dirname "$0")"

if [[ "${1:-}" != "--skip-tests" ]]; then
    echo "== test =="
    ./test.sh
fi

echo "== clean =="
rm -rf dist

echo "== uv build =="
uv build

echo "== twine check =="
uvx twine check --strict dist/*

ls -1 dist
