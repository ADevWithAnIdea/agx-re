#!/bin/sh
# EXP-0027 indirect-command capture matrix. Runs on the A18 device under
# ~/cleanroom_work/exp0027. Captures registered GPU BOs for direct vs indirect
# vs ICB draws/dispatches, then diffs. Pulls back text only.
set -e
cd "$(dirname "$0")"

echo "=== build ==="
clang -arch arm64e -dynamiclib -o iotrace.dylib iotrace.c -framework IOKit -framework CoreFoundation
clang -fobjc-arc -framework Metal -framework Foundation -o ivar ivar.m 2>/dev/null
echo built

DYL=./iotrace.dylib
export IOTRACE_MAX_MAP=0x30000

run() { # run LABEL -- <ivar args...>
  label="$1"; shift; [ "$1" = "--" ] && shift
  d="capi/$label"; rm -rf "$d"; mkdir -p "$d"
  echo "--- capture $label : $* ---"
  IOTRACE_LOG="capi/$label.trace" IOTRACE_DUMP_DIR="$d" \
    DYLD_INSERT_LIBRARIES=$DYL ./ivar "$@" --dump > "capi/$label.stdout" 2>&1 || true
  grep -E '^(CONFIG|VA |PIXEL|OUT|SUBMIT|ICB|FAIL|ARGERR)' "capi/$label.stdout" || true
}

rm -rf capi; mkdir -p capi

# ---- draw: direct vs args-in-buffer vs ICB (non-indexed and indexed) ----
run draw_direct     -- --mode draw_direct
run draw_direct2    -- --mode draw_direct
run draw_indirect   -- --mode draw_indirect
run draw_dir_idx    -- --mode draw_direct   --indexed
run draw_ind_idx    -- --mode draw_indirect --indexed
run icb_draw        -- --mode icb_draw
run icb_draw2       -- --mode icb_draw --icbn 2
run icb_draw_idx    -- --mode icb_draw --indexed

# ---- dispatch: direct vs args-in-buffer vs ICB ----
run disp_direct     -- --mode disp_direct
run disp_direct2    -- --mode disp_direct
run disp_indirect   -- --mode disp_indirect
run icb_disp        -- --mode icb_disp
run icb_disp2       -- --mode icb_disp --icbn 2

echo "=== analysis ==="
mkdir -p ana
LBL="draw_direct draw_direct2 draw_indirect draw_dir_idx draw_ind_idx icb_draw icb_draw2 icb_draw_idx disp_direct disp_direct2 disp_indirect icb_disp icb_disp2"
for l in $LBL; do python3 dumpscan.py capi/$l --list > ana/list_$l.txt 2>&1 || true; done

# determinism check
python3 bodiff.py capi/draw_direct capi/draw_direct2 --maxlen 0x400 > ana/diff_draw_det.txt 2>&1 || true
python3 bodiff.py capi/disp_direct capi/disp_direct2 --maxlen 0x400 > ana/diff_disp_det.txt 2>&1 || true

# core diffs
python3 bodiff.py capi/draw_direct capi/draw_indirect --maxlen 0x400 > ana/diff_draw_indirect.txt 2>&1 || true
python3 bodiff.py capi/draw_dir_idx capi/draw_ind_idx --maxlen 0x400 > ana/diff_draw_indirect_idx.txt 2>&1 || true
python3 bodiff.py capi/draw_direct capi/icb_draw --maxlen 0x400 > ana/diff_icb_draw.txt 2>&1 || true
python3 bodiff.py capi/icb_draw capi/icb_draw2 --maxlen 0x400 > ana/diff_icb_draw_n2.txt 2>&1 || true
python3 bodiff.py capi/disp_direct capi/disp_indirect --maxlen 0x400 > ana/diff_disp_indirect.txt 2>&1 || true
python3 bodiff.py capi/disp_direct capi/icb_disp --maxlen 0x400 > ana/diff_icb_disp.txt 2>&1 || true
python3 bodiff.py capi/icb_disp capi/icb_disp2 --maxlen 0x400 > ana/diff_icb_disp_n2.txt 2>&1 || true

# pointer graphs
for l in draw_indirect disp_indirect icb_draw icb_disp; do
  python3 bograph.py capi/$l > ana/graph_$l.txt 2>&1 || true
done
echo "=== done ==="; ls ana | head -40
