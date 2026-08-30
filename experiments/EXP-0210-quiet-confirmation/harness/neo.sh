#!/bin/sh
# EXP-0210 ssh/scp helpers.  SSHPASS env var only -- the password is never written to a file.
NEO="${NEO:-192.168.170.254}"
SSHOPT="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=15 -o ServerAliveInterval=15"
case "$1" in
  sh)   shift; A="${ALARM:-300}"; exec perl -e 'alarm shift; exec @ARGV' "$A" sshpass -e ssh $SSHOPT "user@$NEO" "$@" ;;
  put)  shift; A="${ALARM:-180}"; exec perl -e 'alarm shift; exec @ARGV' "$A" sshpass -e scp $SSHOPT "$@" ;;
  *) echo "usage: neo.sh sh <cmd> | neo.sh put <src...> <dst>"; exit 2;;
esac
