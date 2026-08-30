#!/usr/bin/env python3
"""EXP-0157 POST-FREEZE carrier extension: bounding-box ray-query carriers.

Registered only when `EXTRA_CARRIERS=bbox` is set, so the frozen `carriers.py`
is untouched and the pre-registered arms R/S/H are byte-identical to what was
captured before this file existed. Records produced with these carriers carry
arm letter `B` and are reported separately from the pre-registered arms.

Rationale is in `harness/reachprobe.py` and RESULTS.md: a triangle-only query
never executes the code holding `rtq_pred`/`rtq_dualsrc`, so those descriptors
need the CUSTOM-INTERSECTION traversal path instead.

Every oracle below was verified against the unmutated carrier on G17P before
any sweep: count 3.0, prim 6.0, commit 1.0, geom 6.0, sentinel 7.5.
"""
import carriers as C


def _bb(func, want0, doc):
    return {
        "metal": "kernels/k_rq_bbox.metal", "func": func, "grid": 1, "tg": 1,
        "accel": 1, "accel_kind": "bbox",
        "inputs": {0: ("poison_rq.bin", C.poison_bytes(C.RQ_WORDS))},
        "outs": {0: 4 * C.RQ_WORDS}, "dtype": {0: C.F32},
        "oracle": {0: [want0, C.SENTINEL, None, None]},
        "src_exp": "EXP-0157", "doc": doc,
    }


def register():
    C.CARRIERS["bb_count"] = _bb("k_bb_count", 3.0, "number of bounding-box candidates")
    C.CARRIERS["bb_prim"] = _bb("k_bb_prim", 6.0, "sum of (bbox primitive id + 1)")
    C.CARRIERS["bb_commit"] = _bb("k_bb_commit", 1.0,
                                  "custom-intersection commit loop; committed distance")
    C.CARRIERS["bb_geom"] = _bb("k_bb_geom", 6.0, "sum of (bbox geometry id + 2)")
