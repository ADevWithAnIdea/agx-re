#!/usr/bin/env python3
"""EXP-0206 PRE-FREEZE CALIBRATION -- human-readable region walk. NOT CITED."""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / "harness")); sys.path.insert(0, str(HERE))
import carriers206 as C, locate206 as L   # noqa: E402
BIN = EXP / "work" / "bin"; WORK = EXP / "work"
for name in sys.argv[1:]:
    spec = C.CARRIERS[name]
    arch, regions = L.compile_carrier(BIN, EXP / spec["metal"], spec["func"], WORK / "arch")
    print("=== %s" % name)
    for rn in L.code_regions(regions):
        b = regions[rn]["bytes"]
        recs, err = L.walk(b)
        print(" -- region %s len=%d walk_err=%s" % (rn, len(b), err))
        for r in recs:
            print("    %4d %2d %-18s %s" % (r["off"], r["len"], r["mnemonic"],
                                            b[r["off"]:r["off"]+r["len"]].hex()))
        for mn in ("ret", "ret_luse", "stop", "call", "if_push", "pop_reconverge"):
            occ = L.occurrences(b, mn)
            if occ["agreed"] or occ["signature_only"]:
                print("    ~ %-15s agreed=%s sig_only=%s walk_only=%s"
                      % (mn, occ["agreed"], occ["signature_only"], occ["walk_only"]))
