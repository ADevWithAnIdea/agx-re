#!/usr/bin/env python3
"""PREFREEZE DIAGNOSTIC (NEVER evidence): all 256 values of uniform_mov byte0.

byte0 of this 4-byte instruction carries BOTH the match-pinned opcode nibble
(bits 0..3 == 0xb) AND the `dst` field (bits 4..7). The smoke's falsifier
(byte0 = 0x00) produced the baseline digest, and the baseline's own dst is 0, so
"identical to baseline" is ambiguous between:
   (a) the falsifier is blind because dst=0 writes the same value either way, or
   (b) the low nibble is NOT decisive and 0x0 behaves as 0xb  -- a db.json /
       hardware finding about the match constant.
Sweeping the whole byte separates them: for each value, report WHICH of r0..r15
left its seed.
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
base = [c for c in cases if c["arm"] == "REGMOVE/dump" and c["role"] == "baseline"][0]
anchor = bytes.fromhex(base["bytes"])
work = EXP / "work" / "diag"
R.write_inputs(work)
car = S.SynthCarrier(EXP / "kernels" / "carrier_dag.metal", "k", work)
seeds = H.seed_regs("int")

rows = []
for form in (0x01, 0x00):
    for v in range(256):
        blk = bytes([v]) + anchor[1:2] + bytes([form]) + anchor[3:4]
        c = dict(base); c["bytes"] = blk.hex()
        prog = R.build_program(c, car.region_len, blk)
        resp, w = car.run_program(prog)
        d = S.digest(w)
        regs = [w[i] for i in range(0, 64, 4)] if len(w) >= 64 else []
        if len(regs) < 16:
            chg = [("NODATA", "%d words" % len(w))]
        else:
            chg = [(i, "%08x" % regs[i]) for i in range(16) if regs[i] != seeds[i]]
        rows.append({"form": form, "byte0": v, "nib_lo": v & 0xF, "dst": v >> 4,
                     "status": resp["status"], "pre": (d or {}).get("pre"),
                     "post": (d or {}).get("post"),
                     "tail_ok": (d or {}).get("tail_ok"),
                     "changed": chg})
(EXP / "raw" / "prefreeze" / "diag_byte0.json").write_text(json.dumps(rows, indent=1))

for form in (0x01, 0x00):
    print("=== form (byte+2) = 0x%02x ===" % form)
    print("%-5s %-4s %-4s %-6s %s" % ("byte0", "lo", "dst", "status", "registers that left their seed"))
    for r in [x for x in rows if x["form"] == form]:
        if r["nib_lo"] in (0x0, 0x0b) or r["changed"]:
            print("0x%02x  %-4x %-4d %-6s %s" % (
                r["byte0"], r["nib_lo"], r["dst"], r["status"],
                " ".join("r%s=%s" % (i, s) for i, s in r["changed"]) or "-- NOTHING MOVED --"))
    lo_moved = {}
    for r in [x for x in rows if x["form"] == form]:
        lo_moved.setdefault(r["nib_lo"], 0)
        if r["changed"]:
            lo_moved[r["nib_lo"]] += 1
    print("  per-low-nibble count of values that moved a register (out of 16):")
    print("   ", {("0x%x" % k): v for k, v in sorted(lo_moved.items()) if v})
car.close()
