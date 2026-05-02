#!/usr/bin/env bash
# Build agentic-tui distribution packages (sdist + wheel).
#
# Usage: ./scripts/build.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "==> Cleaning previous builds..."
rm -rf dist/ build/ src/*.egg-info

echo "==> Building sdist and wheel..."
uv build

echo ""
echo "==> Build artifacts:"
ls -lh dist/

echo ""
echo "Done. To publish, run: ./scripts/publish.sh"
