#!/bin/bash
# EXP-0157 remote helper. Never commits the password; SSHPASS comes from the env.
NEO="${NEO:-192.168.10.243}"
SSHOPT="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=15 -o LogLevel=ERROR"
case "$1" in
  ssh)  shift; perl -e "alarm ${ALARM:-120}; exec @ARGV" sshpass -e ssh $SSHOPT "user@$NEO" "$@" ;;
  put)  shift; perl -e "alarm ${ALARM:-120}; exec @ARGV" sshpass -e scp $SSHOPT -r "$@" ;;
  *) echo "usage: neo.sh ssh <cmd> | neo.sh put <src...> user@host:dst" >&2; exit 2 ;;
esac
