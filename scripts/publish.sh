#!/usr/bin/env bash
# Publish agentic-tui to PyPI.
#
# Usage:
#   ./scripts/publish.sh          # publish to PyPI
#   ./scripts/publish.sh --test   # publish to TestPyPI first
#
# Authentication:
#   Set UV_PUBLISH_TOKEN env var with your PyPI API token:
#     export UV_PUBLISH_TOKEN=pypi-xxxxx
#
#   Or pass it inline:
#     UV_PUBLISH_TOKEN=pypi-xxxxx ./scripts/publish.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Build if dist/ is empty or missing
if [ ! -d dist ] || [ -z "$(ls -A dist/ 2>/dev/null)" ]; then
    echo "==> No build artifacts found. Building first..."
    bash "$SCRIPT_DIR/build.sh"
fi

echo ""
echo "==> Artifacts to publish:"
ls -lh dist/
echo ""

if [ "${1:-}" = "--test" ]; then
    echo "==> Uploading to TestPyPI..."
    uv publish --publish-url https://test.pypi.org/legacy/
    echo ""
    echo "Done. Install from TestPyPI with:"
    echo "  uv pip install --index-url https://test.pypi.org/simple/ agentic-tui"
else
    echo "==> Uploading to PyPI..."
    uv publish
    echo ""
    echo "Done. Install with:"
    echo "  uv pip install agentic-tui"
fi
