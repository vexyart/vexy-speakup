#!/usr/bin/env bash
# this_file: run-gui.sh
# Launch the local web UI. Usage: ./run-gui.sh [folder] [--port=8765]
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
exec uv run --extra gui --extra models vexy-speakup gui "$@"
