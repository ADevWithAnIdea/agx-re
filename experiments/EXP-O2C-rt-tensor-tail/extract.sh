#!/bin/bash
# EXP-O2C device-side compile+extract driver. For each (file, function) it runs
# shdump to compile our own MSL and agxparse to carve _agc.main, printing
# "group function bytes hex". Compile failures are printed as FAIL lines (a
# first-class negative result). Compute kernels only unless --render given.
# CLEAN-ROOM: only our own MSL is compiled and only our own bytes extracted.
cd ~/cleanroom_work/exp_o2c || exit 1
OUT=work; mkdir -p $OUT
emit() {  # grp file fn extra_shdump_args
  local grp=$1 file=$2 fn=$3; shift 3
  local bin=$OUT/${grp}_${fn}.bin
  if ./shdump -o "$bin" -f "$fn" --no-fast-math "$@" "kernels/$file" >"$OUT/${grp}_${fn}.log" 2>&1; then
    local hex=$(python3 agxparse.py "$bin" --extract-hex 2>/dev/null | tr -d '\n ')
    if [ -n "$hex" ]; then echo "$grp $fn $hex"; else echo "$grp $fn EXTRACT_FAIL"; fi
  else
    echo "$grp $fn COMPILE_FAIL"
  fi
}
emit_stage() {  # grp file stage vfn ffn  (render; extract given stage)
  local grp=$1 file=$2 stage=$3 vfn=$4 ffn=$5
  local bin=$OUT/${grp}_${ffn}.bin
  if ./shdump -o "$bin" --render --vertex "$vfn" --fragment "$ffn" --no-fast-math "kernels/$file" >"$OUT/${grp}_${ffn}.log" 2>&1; then
    local hex=$(python3 agxparse.py "$bin" --stage "$stage" --extract-hex 2>/dev/null | tr -d '\n ')
    if [ -n "$hex" ]; then echo "$grp ${ffn}@${stage} $hex"; else echo "$grp ${ffn}@${stage} EXTRACT_FAIL"; fi
  else
    echo "$grp ${ffn}@${stage} COMPILE_FAIL"
  fi
}

# emit_iso: compile ONE function from an isolated per-kernel temp file (so an
# invalid kernel doesn't poison the rest of the library). grp file fn
emit_iso() {
  local grp=$1 file=$2 fn=$3
  local mf=$OUT/${grp}_${fn}.metal
  [ -f "$mf" ] || { echo "$grp $fn NO_SPLIT"; return; }
  local bin=$OUT/${grp}_${fn}.bin
  if ./shdump -o "$bin" -f "$fn" --no-fast-math "$mf" >"$OUT/${grp}_${fn}.log" 2>&1; then
    local hex=$(python3 agxparse.py "$bin" --extract-hex 2>/dev/null | tr -d '\n ')
    if [ -n "$hex" ]; then echo "$grp $fn $hex"; else echo "$grp $fn EXTRACT_FAIL"; fi
  else
    echo "$grp $fn COMPILE_FAIL"
  fi
}

case "$1" in
 tensor)
  for f in mad_f32 mul_f32 mad_f16 mad_bf16 mad_ba mad_chain ls_f32 ls_f32_t ls_f32_st mad_at; do
    emit tensor tensor.metal $f; done ;;
 mpp)
  python3 splitk.py kernels/mpp2.metal mpp $OUT >/dev/null 2>&1
  for f in mm_mul mm_mac mm_tl mm_tr mm_16 mm_f32 mm_2sg; do
    emit_iso mpp mpp2.metal $f; done ;;
 rtpay)
  for f in call_p2 call_pbig call_pnone call_pin; do
    emit rtpay rtpay.metal $f; done ;;
 rtprim)
  python3 splitk.py kernels/rtprim.metal rtprim $OUT >/dev/null 2>&1
  for f in tag_tri tag_bbox tag_curve tag_world mb_prim mb_const mb_inst tag_opaque; do
    emit_iso rtprim rtprim.metal $f; done ;;
 rtfrag)
  emit_stage rtfrag rtfrag.metal fragment v_main f_rt
  emit_stage rtfrag rtfrag.metal fragment v_main f_plain
  emit_stage rtfrag rtfrag.metal fragment v_main f_rt_isect
  emit_stage rtfrag rtfrag.metal vertex   v_main f_rt ;;
 *) echo "usage: $0 {tensor|mpp|rtpay|rtprim|rtfrag}"; exit 1 ;;
esac
