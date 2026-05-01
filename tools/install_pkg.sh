#!/bin/bash
# install_pkg.sh — Install Python or system packages.
# Usage: bash install_pkg.sh pip <package> [package2...]
#        bash install_pkg.sh apt <package> [package2...]

set -euo pipefail
PKG_TYPE="${1:?Usage: install_pkg.sh pip|apt <package> [...]}"
shift

VENV="$HOME/seed/venv/bin/pip"

case "$PKG_TYPE" in
  pip)
    if [[ -x "$VENV" ]]; then
        "$VENV" install --quiet "$@"
    else
        pip3 install --quiet --user "$@"
    fi
    echo "Installed pip: $*"
    ;;
  apt)
    sudo apt-get install -y -qq "$@"
    echo "Installed apt: $*"
    ;;
  *)
    echo "Unknown type: $PKG_TYPE (use pip or apt)" >&2
    exit 1
    ;;
esac
