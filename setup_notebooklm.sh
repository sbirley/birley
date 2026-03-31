#!/bin/bash
# Setup script for notebooklm-py authentication
#
# Since browser-based login requires a GUI, this script supports
# two authentication methods:
#
# Method 1: Import storage state from local machine
#   1. On your local machine, run:
#      pip install "notebooklm-py[browser]"
#      playwright install chromium
#      notebooklm login
#   2. Copy the file to this server:
#      scp ~/.notebooklm/storage_state.json user@server:~/.notebooklm/
#   3. Run this script: ./setup_notebooklm.sh
#
# Method 2: Set NOTEBOOKLM_AUTH_JSON environment variable
#   export NOTEBOOKLM_AUTH_JSON='{"cookies": [...]}'
#   Then use notebooklm-py programmatically.

set -e

NOTEBOOKLM_HOME="${NOTEBOOKLM_HOME:-$HOME/.notebooklm}"

# Ensure venv is activated
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -d "$SCRIPT_DIR/.venv" ]; then
    source "$SCRIPT_DIR/.venv/bin/activate"
fi

# Create config directory
mkdir -p "$NOTEBOOKLM_HOME"

# Check for existing storage state
if [ -f "$NOTEBOOKLM_HOME/storage_state.json" ]; then
    echo "Found existing storage state at $NOTEBOOKLM_HOME/storage_state.json"
    echo "Testing authentication..."
    notebooklm status && echo "Authentication OK!" || echo "Auth may be expired. Re-login on local machine and copy storage_state.json again."
    exit 0
fi

# Check for env var
if [ -n "$NOTEBOOKLM_AUTH_JSON" ]; then
    echo "Found NOTEBOOKLM_AUTH_JSON environment variable."
    echo "Writing to $NOTEBOOKLM_HOME/storage_state.json..."
    echo "$NOTEBOOKLM_AUTH_JSON" > "$NOTEBOOKLM_HOME/storage_state.json"
    echo "Testing authentication..."
    notebooklm status && echo "Authentication OK!" || echo "Auth JSON may be invalid or expired."
    exit 0
fi

echo "No authentication found."
echo ""
echo "To authenticate, choose one of these methods:"
echo ""
echo "1. Login on your local machine and copy the storage file:"
echo "   Local:  pip install 'notebooklm-py[browser]' && playwright install chromium && notebooklm login"
echo "   Copy:   scp ~/.notebooklm/storage_state.json <this-server>:~/.notebooklm/"
echo "   Then:   ./setup_notebooklm.sh"
echo ""
echo "2. Set the NOTEBOOKLM_AUTH_JSON environment variable:"
echo "   export NOTEBOOKLM_AUTH_JSON='\$(cat ~/.notebooklm/storage_state.json)'"
echo "   Then:   ./setup_notebooklm.sh"
exit 1
