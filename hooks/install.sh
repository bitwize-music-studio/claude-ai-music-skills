#!/bin/bash
# Install git hooks for bitwize-music plugin

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
HOOKS_DIR="$REPO_ROOT/.git/hooks"

echo "Installing git hooks..."

# Install pre-commit hook
if [ -f "$SCRIPT_DIR/pre-commit" ]; then
    cp "$SCRIPT_DIR/pre-commit" "$HOOKS_DIR/pre-commit"
    chmod +x "$HOOKS_DIR/pre-commit"
    echo "✓ Installed pre-commit hook"
else
    echo "✗ pre-commit hook not found"
    exit 1
fi

echo ""
echo "Git hooks installed successfully!"
echo ""
echo "The pre-commit hook requires:"
echo "  - ruff (pip install ruff)"
echo "  - pytest (pip install pytest)"
echo "  - bandit (pip install bandit)"
echo "  - pip-audit (pip install pip-audit)"
echo ""
echo "Install all at once:"
echo "  pip install ruff pytest bandit pip-audit"
