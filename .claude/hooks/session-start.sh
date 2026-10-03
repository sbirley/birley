#!/bin/bash
# Cloud-session setup for the browser and design tooling in .claude/skills.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

# playwright-cli: the skill in .claude/skills/playwright-cli drives this CLI.
# Pinned to the version the skill was installed from.
PLAYWRIGHT_CLI_VERSION=0.1.22
if [ "$(playwright-cli --version 2>/dev/null || true)" != "$PLAYWRIGHT_CLI_VERSION" ]; then
  npm install -g --no-fund --no-audit "@playwright/cli@$PLAYWRIGHT_CLI_VERSION" >/dev/null
fi

# Chromium reads trust from the NSS store, which doesn't include the
# session's egress proxy CA, so every HTTPS page fails without this.
PROXY_CA=/root/.ccr/agent-proxy-ca.crt
NSSDB="$HOME/.pki/nssdb"
if [ -f "$PROXY_CA" ]; then
  if ! command -v certutil >/dev/null 2>&1; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get install -y -qq libnss3-tools >/dev/null 2>&1 \
      || { apt-get update -qq >/dev/null && apt-get install -y -qq libnss3-tools >/dev/null; }
  fi
  mkdir -p "$NSSDB"
  [ -f "$NSSDB/cert9.db" ] || certutil -d "sql:$NSSDB" -N --empty-password
  certutil -d "sql:$NSSDB" -L -n ccr-agent-proxy >/dev/null 2>&1 \
    || certutil -d "sql:$NSSDB" -A -t "C,," -n ccr-agent-proxy -i "$PROXY_CA"
fi

# Prefetch the impeccable engine (gitignored) so its own 5s hooks don't
# time out on the first-run download. Non-fatal.
IMPECCABLE="$CLAUDE_PROJECT_DIR/.claude/skills/impeccable/scripts/impeccable"
if [ -f "$IMPECCABLE" ]; then
  "$IMPECCABLE" engine-probe >/dev/null 2>&1 || echo "impeccable engine prefetch failed; it will retry on first use" >&2
fi
