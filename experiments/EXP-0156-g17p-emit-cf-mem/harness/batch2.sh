#!/bin/bash
# EXP-0156 capture batch #2, run ON the neo under nohup.
#
# WHY THERE IS A BATCH #2 (recorded, not tidied away): batch #1's captures
# `cf02a/b/c`, `mem01/02`, `mtg01/02`, `bf01/02` all aborted in `baseline.py`
# with `TypeError: %d format: a number is required, not NoneType`, because the
# addendum carrier `tgac141` was pushed to the neo with `main_len: None` while
# the batch was still running. Those nine run ids are RETAINED as empty
# directories and are NEVER REUSED; this batch uses new ids. `cf01d` never
# created a directory (it exited 75 waiting 900 s for the GPU lease, held by
# EXP-0153), so that id is still free and is used here.
#
# Order: the short, high-value addendum first; then the free groups; then the
# slow leased CF chunks. Leased steps wait up to 40 min for the lease because
# five other agents share the device.
D="$(cd "$(dirname "$0")" && pwd)/drive.sh"
CF="cf.baseline,jump.branch_ctrl,pop_reconverge,ret.linkmode,ret_luse"
JC="jc.liveness,jump_cond"
CH="if_push_pred,ret.scoreboard,mask_op"
MEM="atdev,attg"
BF="bfadd,bffma,hmax,h2fma,bf.,h.,h2."
bash "$D" lease g17p-20260830-t141a "tgac141"  2400
bash "$D" lease g17p-20260830-t141b "tgac141"  2400
bash "$D" free  g17p-20260830-bf03  "$BF"
bash "$D" free  g17p-20260830-bf04  "$BF"
bash "$D" free  g17p-20260830-mem03 "$MEM" --exclude attg_atomic_tg_b5
bash "$D" free  g17p-20260830-mem04 "$MEM" --exclude attg_atomic_tg_b5
bash "$D" lease g17p-20260830-mtg03 "attg_atomic_tg_b5" 2400
bash "$D" lease g17p-20260830-mtg04 "attg_atomic_tg_b5" 2400
bash "$D" lease g17p-20260830-cf01d "$CF" 2400
bash "$D" lease g17p-20260830-cf02d "$CF" 2400
bash "$D" lease g17p-20260830-cf02e "$JC" 2400
bash "$D" lease g17p-20260830-cf02f "$CH" 2400
echo "BATCH2 COMPLETE $(date -u +%FT%TZ)"
