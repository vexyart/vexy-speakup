#!/usr/bin/env bash
# this_file: publish.sh
# Test, tag, build and publish to PyPI with `uv publish`.
# Workflow: test -> gitnextver -> build -> verify version -> uv publish.
#
# gitnextver stages ALL changes (git add -A), commits them with the version as
# message, creates the next vX.Y.Z tag (v1.0.0 when none exists) and pushes.
# A clean tree already tagged on HEAD (e.g. a rerun after a failed upload) skips
# gitnextver. Credentials: UV_PUBLISH_TOKEN, keyring or trusted publishing.
set -euo pipefail
cd "$(dirname "$0")"

head_tag() { git tag --points-at HEAD | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$' | sort -V | tail -n1 || true; }

publish_with_retry() {
    local attempts="${PYPI_PUBLISH_MAX_ATTEMPTS:-3}" delay="${PYPI_PUBLISH_INITIAL_DELAY:-60}"
    local retryable="429|Too Many Requests|too many new projects|timed? ?out|temporarily unavailable|50[234]|connection reset"
    local log status
    log="$(mktemp "${TMPDIR:-/tmp}/uv-publish.XXXXXX")"
    for ((i = 1; i <= attempts; i++)); do
        set +e
        uv publish --check-url https://pypi.org/simple/ dist/* 2>&1 | tee "$log"
        status=${PIPESTATUS[0]}
        set -e
        if ((status == 0)); then rm -f "$log"; return 0; fi
        if ! grep -Eiq "$retryable" "$log" || ((i == attempts)); then rm -f "$log"; return "$status"; fi
        echo "Retryable publish error; waiting ${delay}s (attempt $((i + 1))/$attempts)"
        sleep "$delay"
        delay=$((delay * 2))
    done
}

echo "== test =="
./test.sh

tag="$(head_tag)"
if [[ -n "$tag" && -z "$(git status --porcelain)" ]]; then
    echo "== HEAD already tagged $tag; skipping gitnextver =="
else
    echo "== gitnextver: commits these changes, tags and pushes =="
    git status --short
    uvx gitnextver
    tag="$(head_tag)"
fi

if [[ -z "$tag" ]]; then
    echo "No vX.Y.Z tag on HEAD: gitnextver tags only when there are changes to commit." >&2
    echo "Change something (e.g. CHANGELOG.md), then rerun ./publish.sh." >&2
    exit 1
fi

./build.sh --skip-tests

version="${tag#v}"
if ! ls dist/*-"$version"-*.whl dist/*-"$version".tar.gz >/dev/null 2>&1; then
    echo "dist/ does not match tag $tag:" >&2
    ls -1 dist >&2
    exit 1
fi

echo "== uv publish $version =="
publish_with_retry
echo "Published $version"
