#!/usr/bin/env python3
"""fixtures.py -- RECORDED REALITY for --selftest.

Every entry below is a result ACTUALLY OBSERVED on the real local M4 during
this experiment's own pilot/development dispatches (transcript-verifiable,
predating the frozen matrix.py case list), used only to ground-truth that
matrix.py's oracle functions correctly reproduce known real hardware output --
not fabricated/hand-typed expected values.

  ifnest_004  (grid=8, function ifnest_004, kernels/cf_nest.metal):
    inputs  a=[0,1,2,3,4,5,50,200]
    outputs o=[-1001,-1001,-1002,-1003,-1004,25,2500,40000]
    (dispatched via tools/agxtest/agxtest.py during PRE_REGISTRATION pilot
    testing, STATUS OK, exact match against the smallest-j / v*v formula.)

  ifnest_128  (grid=8, function ifnest_128, kernels/cf_nest.metal):
    inputs  a=[0,1,2,50,64,127,128,200]
    outputs o=[-1001,-1001,-1002,-1050,-1064,-1127,-1128,40000]
    (same pilot session; depth-128 nested divergent-return, STATUS OK.)

  loopnest1_064  (grid=8, function loopnest1_064, kernels/cf_nest.metal):
    inputs  a=[1,1,1,1,1,1,1,1]
    outputs o=[64,64,64,64,64,64,64,64]
    (same pilot session; pure 64-level nested-loop structural depth, STATUS OK.)
"""

RECORDED_REALITY = {
    "ifnest_004": {
        "bufs": {1: [0, 1, 2, 3, 4, 5, 50, 200]},
        "results": {0: [-1001, -1001, -1002, -1003, -1004, 25, 2500, 40000]},
        "oracle_lookup": lambda matrix: matrix.oracle_ifnest(4),
    },
    "ifnest_128": {
        "bufs": {1: [0, 1, 2, 50, 64, 127, 128, 200]},
        "results": {0: [-1001, -1001, -1002, -1050, -1064, -1127, -1128, 40000]},
        "oracle_lookup": lambda matrix: matrix.oracle_ifnest(128),
    },
    "loopnest1_064": {
        "bufs": {1: [1, 1, 1, 1, 1, 1, 1, 1]},
        "results": {0: [64, 64, 64, 64, 64, 64, 64, 64]},
        "oracle_lookup": lambda matrix: matrix.oracle_loopnest1(64),
    },
}
