#!/usr/bin/env python3
"""PREFREEZE DIAGNOSTIC (raw/prefreeze/, NEVER evidence).

Two smoke findings need to be understood before a gated run is allowed to start:

  1. the four REGMOVE arms' falsifier (byte0 = 0x00) produced a digest IDENTICAL
     to the baseline. If the observable cannot tell "this instruction ran" from
     "this instruction is not even this instruction", the arm proves nothing.
  2. the two STOP arms have `ladder=None` by design, because `stop` has no
     known-live field. Their detection power, if any, has to come from the
     terminal-vs-midprogram contrast instead.

Prints the raw 104-word window so the cause is measured, not guessed.
"""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / "harness"))
import isa_helpers as H
import sweeprun as S
import casematrix as CM
import run as R

rep = json.loads((EXP / "work" / "anchors" / "anchor_report.json").read_text())
cases = CM.build_cases(rep)
work = EXP / "work" / "diag"
R.write_inputs(work)
car = S.SynthCarrier(EXP / "kernels" / "carrier_dag.metal", "k", work)

def show(tag, c):
    blk = bytes.fromhex(c["bytes"])
    prog = R.build_program(c, car.region_len, blk)
    resp, w = car.run_program(prog)
    d = S.digest(w)
    regs = [w[i] for i in range(0, 64, 4)] if len(w) >= 64 else []
    print("%-34s status=%-4s bytes=%-10s" % (tag, resp["status"], c["bytes"]))
    print("    r0..r15 = %s" % " ".join("%08x" % x for x in regs))
    print("    PRE=%s POST=%s tail_ok=%s all_poison=%s hi=%08x" % (
        (d or {}).get("pre"), (d or {}).get("post"), (d or {}).get("tail_ok"),
        (d or {}).get("all_poison"), (w[72] if len(w) > 72 else 0)))
    return regs

for arm in ("REGMOVE/dump", "REGMOVE/form", "STOP/terminal", "STOP/midprogram"):
    cs = [c for c in cases if c["arm"] == arm]
    print("=" * 78)
    print(arm)
    for role in ("baseline", "falsifier"):
        for c in [x for x in cs if x["role"] == role][:1]:
            show("  %s" % role, c)
    # a couple of ladder points, and for REGMOVE a couple of real dst values
    for c in [x for x in cs if x["role"] == "ladder"][:3]:
        show("  ladder %s=%s" % (c["field"], c["value"]), c)
    for c in [x for x in cs if x["role"] == "sweep" and x["field"] == "dst"][:4]:
        show("  sweep dst=%s form=%s" % (c["value"], c.get("cross_value")), c)
    for c in [x for x in cs if x["role"] == "sweep" and x["field"] == "reserved"][:3]:
        show("  sweep reserved=%s" % c["value"], c)
car.close()
