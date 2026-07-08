#!/bin/sh
# EXP-M4-09 CMD-2: independent sweep of all 8 stencil ops on each of the three
# op fields (spass, szfail, sfail) in the 0x58000 fixed-function state pool.
# CLEAN-ROOM: DATA-TRACE + OWN-SHADER. Runs on the LOCAL Apple M4.
set -e
cd "$(dirname "$0")"

DYL=./iotrace.dylib
CAP=0x800

run() {  # run LABEL -- <svar args...>
  label="$1"; shift; [ "$1" = "--" ] && shift
  d="caps/$label"; rm -rf "$d"; mkdir -p "$d"
  IOTRACE_MAX_MAP="$CAP" IOTRACE_LOG=/dev/null IOTRACE_DUMP_DIR="$d" \
    DYLD_INSERT_LIBRARIES=$DYL ./svar "$@" --dump > "caps/$label.out" 2>&1 || true
  st=$(grep -oE 'status=[0-9]+' "caps/$label.out" | head -1)
  fa=$(grep -E '^(PIPELINE_FAIL|SHADER_FAIL|ARGERR)' "caps/$label.out" || true)
  echo "  [$label] ${st:-NOSTATUS} ${fa:+FAIL:$fa}"
}

rm -rf caps analysis; mkdir -p caps analysis

OPS="keep zero replace incrclamp decrclamp invert incrwrap decrwrap"

# reference (enabled): compare=less, pass=replace, zfail=keep, sfail=keep
run s_ref -- --stencil --scmp less --spass replace

# spass sweep: vary pass op, hold zfail=keep sfail=keep
for op in $OPS; do
  run spass_$op -- --stencil --scmp less --spass $op
done

# szfail sweep: vary zfail op, hold spass=replace (anchor, keeps packet enabled) sfail=keep
for op in $OPS; do
  run szfail_$op -- --stencil --scmp less --spass replace --szfail $op
done

# sfail sweep: vary sfail op, hold spass=replace (anchor) szfail=keep
for op in $OPS; do
  run sfail_$op -- --stencil --scmp less --spass replace --sfail $op
done

# back-face: svar --sback sets a DISTINCT hardcoded back face:
#   cmp=equal, sfail=zero(1), zfail=invert(5), pass=replace(2), read=0x0f, write=0x3c
run sback -- --stencil --scmp less --spass replace --sback

echo "=== extract stencil words ==="
python3 extract.py > analysis/table.txt
cat analysis/table.txt
