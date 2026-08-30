#!/bin/bash
# EXP-0156 full gated capture batch, run ON the neo under nohup.
# Leased (hang-prone) groups first, then the free groups, so this experiment's
# own CF hangs cannot innocent-victim its own unleased captures.
D="$(cd "$(dirname "$0")" && pwd)/drive.sh"
CF="cf.baseline,jump.branch_ctrl,pop_reconverge,ret.linkmode,ret_luse"
JC="jc.liveness,jump_cond"
CH="if_push_pred,ret.scoreboard,mask_op"
MEM="atdev,attg"
BF="bfadd,bffma,hmax,h2fma,bf.,h.,h2."
bash "$D" lease g17p-20260830-cf01b "$JC"
bash "$D" lease g17p-20260830-cf01c "$CH"
bash "$D" lease g17p-20260830-cf02a "$CF"
bash "$D" lease g17p-20260830-cf02b "$JC"
bash "$D" lease g17p-20260830-cf02c "$CH"
bash "$D" free  g17p-20260830-mem01 "$MEM" --exclude attg_atomic_tg_b5
bash "$D" free  g17p-20260830-mem02 "$MEM" --exclude attg_atomic_tg_b5
bash "$D" lease g17p-20260830-mtg01 "attg_atomic_tg_b5"
bash "$D" lease g17p-20260830-mtg02 "attg_atomic_tg_b5"
bash "$D" free  g17p-20260830-bf01  "$BF"
bash "$D" free  g17p-20260830-bf02  "$BF"
echo "BATCH COMPLETE $(date -u +%FT%TZ)"
