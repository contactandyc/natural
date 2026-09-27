#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
#
# Maintainer: Andy Curtis <contactandyc@gmail.com>

set -Eeuo pipefail

# --- Discover and source scoped environment ---
_cur="$PWD"
while [ "$_cur" != "/" ]; do
  if [ -f "$_cur/.scaffoldrc.yaml" ]; then
    [ -f "$_cur/.scaffoldrc_python_" ] && source "$_cur/.scaffoldrc_python_"
    break
  fi
  _cur="$(dirname "$_cur")"
done
[ -z "${WORKSPACE_DIR:-}" ] && [ -f "$HOME/.scaffoldrc_python_" ] && source "$HOME/.scaffoldrc_python_"

# --- Extract Command and Arguments ---
COMMAND="${1:-build}"
if [ $# -gt 0 ]; then
    shift # Shift off the command so remaining args ($@) can be passed to subcommands
fi

PYTHON_VER="${PYTHON_VERSION:-3.11}"

case "$COMMAND" in
  install|build)
    echo "--- Setting up Python $PYTHON_VER Virtual Environment ---"
    if [ ! -d "venv" ]; then
        python3 -m venv venv
    fi
    source venv/bin/activate

    echo "--- Installing Dependencies ---"
    pip install --upgrade pip
    pip install -e ".[dev]"
    echo "✅ Local venv ready."

    echo "--- Linking CLI to ~/.local/bin ---"
    mkdir -p "$HOME/.local/bin"
    ln -sf "$PWD/venv/bin/natural" "$HOME/.local/bin/natural"
    echo "✅ CLI linked to $HOME/.local/bin/natural. You can run 'natural' from anywhere!"
    ;;

  run)
    if [ ! -d "venv" ]; then
        echo "⚠️  Environment not found. Running install first..."
        "$0" install
    fi
    source venv/bin/activate

    # Execute the module directly, passing through any extra CLI flags
    python3 -m natural "$@"
    ;;

  test)
    echo "--- Running Tests ---"
    if [ ! -d "venv" ]; then
        "$0" install
    fi
    source venv/bin/activate

    if command -v pytest &> /dev/null; then
        pytest "$@"
    else
        python3 -m unittest discover -s tests
    fi
    ;;

  clean)
    echo "--- Cleaning Workspace and Environments ---"
    # Remove virtualenv and python packaging metadata
    rm -rf venv .pytest_cache *.egg-info build dist

    # Remove global symlink if pointing here
    if [ -L "$HOME/.local/bin/natural" ]; then
        current_target="$(readlink "$HOME/.local/bin/natural" || true)"
        if [[ "$current_target" == *"$PWD"* ]]; then
            rm -f "$HOME/.local/bin/natural"
            echo "↳ Unlinked $HOME/.local/bin/natural"
        fi
    fi

    # Clean compiled python bytecode
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true

    echo "✅ Clean complete."
    ;;

  *)
    echo "Usage: ./build.sh [install|build|run|test|clean] [args...]" >&2
    exit 1
    ;;
esac
