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
    shift
fi

PYTHON_VER="${PYTHON_VERSION:-3.11}"

case "$COMMAND" in
  install)
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

  test|bless|evaluate)
    if [ ! -d "venv" ]; then
        "$0" install
    fi
    source venv/bin/activate

    pytest_args=()
    if [ "$COMMAND" = "bless" ]; then
        pytest_args+=("--bless")
    elif [ "$COMMAND" = "evaluate" ]; then
        pytest_args+=("--evaluate")
    fi

    filter_terms=()
    for arg in "$@"; do
        if [ "$arg" = "-v" ] || [ "$arg" = "--verbose" ]; then
            pytest_args+=("-s" "--verbose-test")
        elif [[ "$arg" == -* ]]; then
            pytest_args+=("$arg")
        elif [[ "$arg" == *.test ]]; then
            filter_terms+=("$(basename "$arg" .test)")
        elif [[ -f "$arg" ]]; then
            pytest_args+=("$arg")
        else
            filter_terms+=("$arg")
        fi
    done

    if [ ${#filter_terms[@]} -gt 0 ]; then
        combined_expr=$(printf " or %s" "${filter_terms[@]}")
        combined_expr="${combined_expr:4}"
        pytest_args+=("-k" "$combined_expr")
    fi

    echo "--- Running Pytest ${pytest_args[*]:-} ---"
    pytest "${pytest_args[@]:-}"
    ;;

  clean)
    echo "--- Cleaning Workspace and Environments ---"
    rm -rf venv .pytest_cache *.egg-info build dist

    if [ -L "$HOME/.local/bin/natural" ]; then
        current_target="$(readlink "$HOME/.local/bin/natural" || true)"
        if [[ "$current_target" == *"$PWD"* ]]; then
            rm -f "$HOME/.local/bin/natural"
            echo "↳ Unlinked $HOME/.local/bin/natural"
        fi
    fi

    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
    echo "✅ Clean complete."
    ;;

  *)
    # For build, run, parse, or any custom command, delegate directly to the CLI entrypoint
    if [ ! -d "venv" ]; then
        "$0" install
    fi
    source venv/bin/activate
    python3 -m natural "$COMMAND" "$@"
    ;;
esac
