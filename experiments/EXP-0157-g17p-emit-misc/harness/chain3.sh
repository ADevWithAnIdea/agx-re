#!/bin/bash
# EXP-0157 chain 3 (run ON THE NEO under nohup).
#
# run02 was STOPPED at 11 830 records and is RETAINED as a partial capture, not
# reused and not topped up (SUBAGENT_BRIEF: "a partial capture is retained,
# never reused"). It had completed all of arm R and the `sfusin` groups, which
# is what gates the ray-query cluster, `n2_op6` and `sfu_marker`; it then slowed
# to ~10 records/min because half of `sfumix.n2_op6.opsel` faults with
# `...ErrorHang` and, under sustained sibling load, each of those costs a device
# recovery. Finishing it would have taken ~16 hours of shared GPU for arms whose
# instructions were already gated in another carrier.
#
# run03 is therefore a NEW run id: a TARGETED second capture of exactly the four
# carriers run02 never reached -- u64eq (n2_op6, n3_mov, scoreboard_fence),
# roundm (n2_op10), h4fma and h3mix (h_coord_hi, h_coord_hi_ext) -- replaying
# run01's resolved case list so the gate still compares like with like.
#
# It waits for the lease-held fault-confirmation pass to finish first, so that
# pass keeps the isolation FIELD-SWEEP-PROTOCOL 7A requires.
set -u
cd "$HOME/agxre/EXP-0157"
export AGX_TOOLS="$HOME/agxre/tools"

while pgrep -f "run.py --run-id g17p_reval01" >/dev/null; do sleep 30; done
sleep 5
echo "[chain3] reval clear at $(date -u +%FT%TZ)"

python3 -B harness/run.py --run-id g17p_run03 --bin-dir bin --work work/w_run03 \
    --raw raw/g17p_run03 --arms R,S,H --carriers u64eq,roundm,h4fma,h3mix \
    --replay raw/g17p_run01/00_cases.json > work/run03.log 2>&1
echo "[chain3] run03 finished $(date -u +%FT%TZ)"

cat raw/g17p_run01/sweep.jsonl raw/g17p_run02/sweep.jsonl raw/g17p_run03/sweep.jsonl \
    > work/gated_all2.jsonl
"$HOME/agxre/gpulease.sh" EXP-0157 2400 -- \
  python3 -B harness/run.py --run-id g17p_reval02 --bin-dir bin --work work/w_reval2 \
    --raw raw/g17p_reval02 --arms R,S,H --carriers u64eq,roundm,h4fma,h3mix \
    --replay raw/g17p_run01/00_cases.json --revalidate work/gated_all2.jsonl \
    --revalidate-outcomes fault,hang,nondeterministic --repeats 5 > work/reval02.log 2>&1
echo "[chain3] reval02 finished $(date -u +%FT%TZ) rc=$?"
