#!/usr/bin/env python3
"""fixtures.py -- RECORDED REALITY for --selftest.

Every entry below is a result ACTUALLY OBSERVED on the real local M4 during
this experiment's own pilot/development dispatches (work/pilot/*.py and the
harness smoke checks run directly against harness/run.py's do_* functions,
predating the frozen raw/ capture), used only to ground-truth that matrix.py's
oracle functions correctly reproduce known real hardware output -- not
fabricated/hand-typed expected values.

  reach_baseline (grid=8, function reach_loop, kernels/reach.metal):
    inputs  a=[0,1,2,3,4,5,6,7]
    outputs o=[1,4,13,40,121,364,1093,3280]  (s=s*3+1 recurrence)
    (dispatched via harness/lib.run_compute during reconnaissance, STATUS OK,
    exact match; reproduced identically via tools/agxtest/agxtest.py directly
    in work/pilot/bisect_reach.py's delta=0 classification.)

  deep_ifnest_255 (compile_limit, kernels/deep/ifnest2_255.metal):
    Clang front-end diagnostic "bracket nesting level exceeded maximum of 256"
    -- COMPILE_FAIL, deterministic, reproduced 3x during reconnaissance
    (work/pilot/bisect_bracket.py bisection + harness smoke check).

  deep_loopnest1_255 (compile_limit, kernels/deep/loopnest1b_255.metal):
    compiles OK (max compilable depth for this family); depth 256 is the
    first COMPILE_FAIL (same Clang diagnostic), both reproduced during
    reconnaissance.

  pred_dst1_ifp1 (locate_splice, kernels/cf_pred.metal:predtest_004):
    inputs  a=[0,1,2,3,4,5,50,200], dst_pred=1, if_push pred nibble=1
    outputs o=[-1003,-1003,-1001,-1001,-1001,-1001,-1001,-1001]
    -- IDENTICAL to dst_pred=1 alone (if_push pred=0), proving the if_push
    "pred" nibble has NO effect on the corruption; confirmed across a 25-point
    dst_pred x if_push_pred matrix during reconnaissance (work/pilot/, direct
    agxtest.py splice dispatches).

  sshuf_raw_062 (locate_splice, kernels/shuf_static.metal:shuffle_static):
    lane byte spliced to raw=0x3e (idx=31, legal max)
    outputs = [31]*32  (broadcast of lane 31's own value, correct in-range)

  squad_raw_002 (locate_splice, kernels/shuf_static.metal:quadshuffle_static):
    lane byte spliced to raw=0x02 (idx=1, legal)
    outputs = [1,1,1,1, 5,5,5,5, 9,9,9,9, 13,13,13,13, 17,17,17,17,
               21,21,21,21, 25,25,25,25, 29,29,29,29]
    (each quad broadcasts its own lane-1 value -- correct quad_shuffle(v,1))
"""

RECORDED_REALITY = {
    "reach_baseline": {
        "bufs": {1: [0, 1, 2, 3, 4, 5, 6, 7]},
        "results": {0: [1, 4, 13, 40, 121, 364, 1093, 3280]},
        "oracle_lookup": lambda matrix: matrix.oracle_expect(matrix.REACH_BASELINE_EXPECTED),
    },
    "pred_dst1_ifp1": {
        "bufs": {1: [0, 1, 2, 3, 4, 5, 50, 200]},
        "results": {0: [-1003, -1003, -1001, -1001, -1001, -1001, -1001, -1001]},
        # no single-value oracle (locate_splice, no-oracle case) -- fixture is
        # for --selftest's schema/matrix-membership check only.
        "oracle_lookup": None,
    },
    "sshuf_raw_062": {
        "bufs": {},
        "results": {0: [31] * 32},
        "oracle_lookup": None,
    },
}
