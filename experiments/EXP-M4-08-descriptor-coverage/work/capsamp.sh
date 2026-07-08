#!/bin/sh
# capsamp.sh — DESC-3 (LOD/aniso scaling + saturation) & DESC-4 (address/border codes).
# Sweeps sampler params via tvar.m, extracts the 8-byte sampler descriptor (slot1),
# prints as u64 so bitfields are readable. Clean-room: DATA-TRACE of our own process.
set -u
DYL=./iotrace.dylib
OUT=${1:-../raw/sampler_capture.txt}
: > "$OUT"

samp() { # label + tvar args...
  lbl=$1; shift
  d=/tmp/sm_$lbl; rm -rf "$d"; mkdir -p "$d"
  IOTRACE_LOG=/dev/null IOTRACE_DUMP_DIR="$d" DYLD_INSERT_LIBRARIES=$DYL \
    ./tvar "$@" --dump >/tmp/sm_$lbl.out 2>/dev/null
  # sampler descriptor = second '+0000' line (SAMPDESC) from descauto
  s=$(python3 descauto.py "$d" --tlen 0x10 --slen 0x08 2>/dev/null | grep -A1 SAMPDESC | grep '+0000')
  w0=$(echo "$s" | awk '{print $2}'); w1=$(echo "$s" | awk '{print $3}')
  # combine to little-endian u64
  printf 'SAMP %-16s w0=%s w1=%s\n' "$lbl" "$w0" "$w1" >> "$OUT"
  rm -rf "$d"
}

# --- DESC-3: lodMin ×64 (bits[0:12]) fractional + boundary ---
for v in 0 0.25 0.5 1.5 13.9 14.1 16.0 32.0 64.0 100.0 127.0; do
  samp "lodmin_$v" --lodmin $v
done
# --- DESC-3: lodMax ×8 (bits[13:19]) fractional + 14.0-saturation + field max ---
for v in 0.25 1.5 3.0 13.9 14.0 14.1 15.0 15.875 16.0; do
  samp "lodmax_$v" --lodmax $v
done
# --- DESC-3: anisotropy (bits[20:22] log2) 1,2,4,8,16 (+ >16 tries) ---
for a in 1 2 4 8 16 32 64 128; do
  samp "aniso_$a" --aniso $a
done
# --- DESC-4: address modes reachable via Metal (edge/repeat/mirror/clampzero/border/mirroredge) ---
for m in edge repeat mirror clampzero border mirroredge; do
  samp "saddr_$m" --saddr $m
done
# border presets 0/1/2 (code 3 not reachable via Metal enum)
for b in tblack oblack owhite; do
  samp "border_$b" --border $b
done
echo "wrote $OUT"; cat "$OUT"
