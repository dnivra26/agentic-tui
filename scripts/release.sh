#!/usr/bin/env bash
# Full release workflow: check, build, tag, publish.
#
# Usage:
#   ./scripts/release.sh          # release to PyPI
#   ./scripts/release.sh --test   # release to TestPyPI
#
# Authentication:
#   export UV_PUBLISH_TOKEN=pypi-xxxxx
#
# This script:
#   1. Reads the version from pyproject.toml
#   2. Checks for uncommitted changes
#   3. Builds sdist + wheel
#   4. Creates a git tag (vX.Y.Z)
#   5. Publishes to PyPI (or TestPyPI with --test)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Extract version from pyproject.toml
VERSION=$(python -c "
import re
with open('pyproject.toml') as f:
    m = re.search(r'version\s*=\s*\"([^\"]+)\"', f.read())
    print(m.group(1))
")

echo "==> Releasing agentic-tui v${VERSION}"
echo ""

# Check for uncommitted changes
if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
    echo "Warning: You have uncommitted changes."
    echo ""
    git status --short
    echo ""
    read -p "Continue anyway? [y/N] " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 1
    fi
fi

# Build
echo "==> Building..."
bash "$SCRIPT_DIR/build.sh"
echo ""

# Tag
TAG="v${VERSION}"
if git rev-parse "$TAG" &> /dev/null 2>&1; then
    echo "==> Git tag $TAG already exists, skipping."
else
    echo "==> Creating git tag $TAG..."
    git tag -a "$TAG" -m "Release $TAG"
    echo "    Created tag $TAG. Push with: git push origin $TAG"
fi
echo ""

# Publish
if [ "${1:-}" = "--test" ]; then
    echo "==> Publishing to TestPyPI..."
    uv publish --publish-url https://test.pypi.org/legacy/
    echo ""
    echo "Done. Test install:"
    echo "  uv pip install --index-url https://test.pypi.org/simple/ agentic-tui==${VERSION}"
else
    echo "==> Publishing to PyPI..."
    uv publish
    echo ""
    echo "Done. Install:"
    echo "  uv pip install agentic-tui==${VERSION}"
fi

echo ""
echo "Don't forget to push the tag: git push origin $TAG"
