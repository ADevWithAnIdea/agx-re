#!/bin/bash
# gpulease — serialize GPU access on the neo so N agents can share one device safely.
#   gpulease <holder> <wait-timeout-sec> -- <command...>
# Atomic via mkdir (no flock on macOS). Stale leases (>15 min) are broken automatically.
LOCKD=/tmp/agx_gpu.lock
HOLDER="${1:?holder name}"; TMO="${2:?timeout}"; shift 2; [ "$1" = "--" ] && shift
START=$(date +%s)
while ! mkdir "$LOCKD" 2>/dev/null; do
  AGE=$(( $(date +%s) - $(stat -f %m "$LOCKD" 2>/dev/null || date +%s) ))
  if [ "$AGE" -gt 900 ]; then
    echo "gpulease: breaking STALE lease held by $(cat $LOCKD/owner 2>/dev/null) age=${AGE}s" >&2
    rm -rf "$LOCKD"; continue
  fi
  if [ $(( $(date +%s) - START )) -gt "$TMO" ]; then
    echo "gpulease: TIMEOUT after ${TMO}s; held by $(cat $LOCKD/owner 2>/dev/null) age=${AGE}s" >&2; exit 75
  fi
  sleep 2
done
trap 'rm -rf "$LOCKD"' EXIT INT TERM
echo "$HOLDER pid=$$ $(date -u +%FT%TZ)" > "$LOCKD/owner"
"$@"; exit $?
