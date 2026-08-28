#!/usr/bin/env python3
"""EXP-0146 pilot: quantify non-determinism of the UNMUTATED carrier.
Three fresh runner processes x 100 identical baseline dispatches each."""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
EXP = HERE.parents[1]
sys.path.insert(0, str(EXP / "harness"))
import sweeplib as S, oracles as O, arms as A
K = EXP / "kernels"
WD = HERE / "flakework"; RD = HERE / "flakeraw"
CAR = A.carriers()
for cname in ("u64eq", "sfu_sin", "roundmodes", "logic_and"):
    msl, ins, outs, oidx, dec, oracle, tol = CAR[cname]
    for proc in range(3):
        c = S.Carrier("%s_flake%d" % (cname, proc), K / msl, ins, outs, 8, 8, RD, WD)
        zeros = bad = 0
        first = None
        for i in range(100):
            r = c.run_main(c.main_bytes)
            obs = dec(r["outs"].get(oidx, b""))
            oc, mt = S.classify(r["status"], obs, oracle, tol)
            if i == 0:
                first = oc
            if oc == "silent_zero":
                zeros += 1
            elif not mt:
                bad += 1
        print("%-11s proc%d first=%-12s zeros=%3d other_mismatch=%3d / 100" %
              (cname, proc, first, zeros, bad))
        c.close()
