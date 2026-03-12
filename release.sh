#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<USAGE
Usage: ./release.sh [options]

Build and upload releases for kingkybel-pyprocess.

Options:
  --testpypi-only   Build and upload only to TestPyPI
  --skip-testpypi   Skip TestPyPI and upload only to PyPI
  --skip-upload     Build only (no upload)
  --no-clean        Keep existing build/ and dist/ artifacts
  --yes             Non-interactive mode; skip dirty-tree confirmation
  -h, --help        Show this help

Environment:
  TWINE_USERNAME    Recommended: __token__
  TWINE_PASSWORD    Recommended: your pypi-... token
USAGE
}

TESTPYPI_ONLY=0
SKIP_TESTPYPI=0
SKIP_UPLOAD=0
CLEAN=1
ASSUME_YES=0
TWINE_USER="${TWINE_USERNAME:-}"
TWINE_PASS="${TWINE_PASSWORD:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --testpypi-only)
      TESTPYPI_ONLY=1
      shift
      ;;
    --skip-testpypi)
      SKIP_TESTPYPI=1
      shift
      ;;
    --skip-upload)
      SKIP_UPLOAD=1
      shift
      ;;
    --no-clean)
      CLEAN=0
      shift
      ;;
    --yes)
      ASSUME_YES=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

TWINE_AUTH_ARGS=()
if [[ -n "$TWINE_PASS" ]]; then
  if [[ -z "$TWINE_USER" ]]; then
    TWINE_USER="__token__"
  fi
  TWINE_AUTH_ARGS=(--username "$TWINE_USER" --password "$TWINE_PASS")
fi

if [[ $TESTPYPI_ONLY -eq 1 && $SKIP_TESTPYPI -eq 1 ]]; then
  echo "Error: --testpypi-only and --skip-testpypi cannot be used together." >&2
  exit 1
fi

if [[ -d .git ]]; then
  if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "Warning: working tree has uncommitted changes."
    git status --short
    if [[ $ASSUME_YES -eq 1 ]]; then
      echo "Continuing due to --yes."
    else
      echo
      read -r -p "Continue release anyway? [y/N] " ans
      if [[ "${ans,,}" != "y" ]]; then
        echo "Aborted."
        exit 1
      fi
    fi
  fi
fi

if [[ $CLEAN -eq 1 ]]; then
  echo "Cleaning previous build artifacts..."
  rm -rf build dist ./*.egg-info
fi

echo "Ensuring build tools are available..."
python -m pip install --upgrade build twine >/dev/null

echo "Building package..."
python -m build

if [[ $SKIP_UPLOAD -eq 1 ]]; then
  echo "Build completed. Upload skipped (--skip-upload)."
  exit 0
fi

if [[ ${#TWINE_AUTH_ARGS[@]} -gt 0 ]]; then
  echo "Using TWINE_USERNAME/TWINE_PASSWORD from environment."
else
  echo "TWINE_PASSWORD not set; Twine may prompt for credentials."
fi

if [[ $SKIP_TESTPYPI -eq 0 ]]; then
  echo "Uploading to TestPyPI..."
  python -m twine upload --repository testpypi "${TWINE_AUTH_ARGS[@]}" dist/*
fi

if [[ $TESTPYPI_ONLY -eq 1 ]]; then
  echo "TestPyPI upload completed (--testpypi-only)."
  exit 0
fi

echo "Uploading to PyPI..."
python -m twine upload "${TWINE_AUTH_ARGS[@]}" dist/*

echo "Release completed successfully."
