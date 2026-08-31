#!/bin/sh
# EXP-0213 ssh/scp helpers.  The password is passed ONLY through the SSHPASS
# environment variable -- it is never written into this or any other file.
#   ALARM=<s> sh harness/neo.sh sh  '<remote command>'
#   ALARM=<s> sh harness/neo.sh put <src...> <dst>
#   ALARM=<s> sh harness/neo.sh get <src...> <dst>
NEO="${NEO:-192.168.170.254}"
SSHOPT="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=15 -o ServerAliveInterval=15 -o ServerAliveCountMax=4"
case "$1" in
  sh)  shift; A="${ALARM:-300}"; exec perl -e 'alarm shift; exec @ARGV' "$A" sshpass -e ssh $SSHOPT "user@$NEO" "$@" ;;
  put) shift; A="${ALARM:-300}"; exec perl -e 'alarm shift; exec @ARGV' "$A" sshpass -e scp $SSHOPT "$@" ;;
  get) shift; A="${ALARM:-300}"; exec perl -e 'alarm shift; exec @ARGV' "$A" sshpass -e scp $SSHOPT "$@" ;;
  *) echo "usage: neo.sh sh <cmd> | put <src..> <dst> | get <src..> <dst>" >&2; exit 2;;
esac
