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
COMMAND="${1:-run}"
if [ $# -gt 0 ]; then
    shift # Shift off the command so remaining args ($@) can be passed to 'run'
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
    pip install -e .
    echo "✅ Local venv ready."

    echo "--- Installing CLI globally via pipx ---"
    if ! command -v pipx &> /dev/null; then
        echo "⚠️  pipx is not installed. Skipping global CLI linkage."
    else
        pipx install -e . --force
        echo "✅ CLI installed globally. Try running 'natural' directly from anywhere!"
    fi
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
        pytest
    else
        python3 -m unittest discover -s tests
    fi
    ;;

  clean)
    echo "--- Cleaning ---"
    rm -rf venv .pytest_cache *.egg-info __pycache__ src/**/__pycache__ tests/__pycache__
    echo "✅ Clean complete."
    ;;

  *)
    echo "Usage: ./build.sh [install|run|test|clean] [args...]" >&2
    exit 1
    ;;
esac
