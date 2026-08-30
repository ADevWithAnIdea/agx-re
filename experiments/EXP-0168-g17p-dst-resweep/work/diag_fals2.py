#!/usr/bin/env python3
"""PREFREEZE DIAGNOSTIC (NEVER evidence). Three questions left by the smoke:

  1. COPYSIGN/lowpress -- byte0 = 0x00 does not change the observation. Which
     byte0 values DO? (copysign's match pins byte0=0x07, byte1=0xc2, byte2=0x88;
     the only declared field is `operands` = byte3.)
  2. ATOMIC/highreg -- same question on a STYLE-P carrier, where lowreg/minop
     on the SAME instruction do fire.
  3. STOP/terminal vs STOP/midprogram -- after the carrier fix, are they
     genuinely two carriers? Their baselines must now DIFFER.
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
inputs = R.write_inputs(work)
out = {}

# ---- 3. the STOP contrast -------------------------------------------------
car = S.SynthCarrier(EXP / "kernels" / "carrier_dag.metal", "k", work)
print("=== STOP/terminal vs STOP/midprogram (must now DIFFER) ===")
stopres = {}
for arm in ("STOP/terminal", "STOP/midprogram"):
    for role in ("baseline", "falsifier"):
        c = [x for x in cases if x["arm"] == arm and x["role"] == role][0]
        blk = bytes.fromhex(c["bytes"])
        resp, w = car.run_program(R.build_program(c, car.region_len, blk))
        d = S.digest(w)
        regs = [w[i] for i in range(0, 64, 4)] if len(w) >= 64 else []
        stopres[(arm, role)] = S.digest_hex(d) if d else None
        print("%-17s %-10s status=%-4s r0=%08x r15=%08x PRE=%s POST=%s W_PROBE(72)=%08x"
              % (arm, role, resp["status"], regs[0] if regs else 0,
                 regs[15] if len(regs) > 15 else 0,
                 (d or {}).get("pre"), (d or {}).get("post"),
                 w[72] if len(w) > 72 else 0))
same = stopres[("STOP/terminal", "baseline")] == stopres[("STOP/midprogram", "baseline")]
print("  baselines identical (R2 VIOLATION if True): %s" % same)
out["stop_baselines_identical"] = same

# ---- 1. copysign byte0 ----------------------------------------------------
print("\n=== COPYSIGN/lowpress: which byte0 values change the observation? ===")
base = [x for x in cases if x["arm"] == "COPYSIGN/lowpress" and x["role"] == "baseline"][0]
anchor = bytes.fromhex(base["bytes"])
print("  anchor bytes %s" % anchor.hex())
resp, w = car.run_program(R.build_program(base, car.region_len, anchor))
hb = S.digest_hex(S.digest(w)); seeds = H.seed_regs(base.get("kind") or "int")
regs0 = [w[i] for i in range(0, 64, 4)]
print("  baseline r0..r15 = %s" % " ".join("%08x" % x for x in regs0))
print("  seeds     r0..r15 = %s" % " ".join("%08x" % x for x in seeds))
fire = []
for v in range(256):
    blk = bytes([v]) + anchor[1:]
    c = dict(base); c["bytes"] = blk.hex()
    r2, w2 = car.run_program(R.build_program(c, car.region_len, blk))
    h2 = S.digest_hex(S.digest(w2)) if S.digest(w2) else None
    if h2 != hb or r2["status"] != "OK":
        fire.append((v, r2["status"]))
print("  byte0 values that FIRE (%d/256): %s" % (len(fire), [("0x%02x" % v, s) for v, s in fire[:24]]))
out["copysign_byte0_fires"] = [[v, s] for v, s in fire]
car.close()

# ---- 2. atomic_mem byte0 on the highreg carrier ---------------------------
print("\n=== ATOMIC/highreg: which byte0 values change the observation? ===")
base = [x for x in cases if x["arm"] == "ATOMIC/highreg" and x["role"] == "baseline"][0]
ins, outs, grid, tg, oidx = R.INPLACE_BIND[base["probe"]]
pc = S.InPlaceCarrier(EXP / "kernels" / "probes.metal", base["probe"], work,
                      dict((i, inputs[v]) for i, v in ins.items()), outs, grid, tg)
pc.out_index = oidx
anchor = bytes.fromhex(base["bytes"])
print("  anchor bytes %s (probe %s)" % (anchor.hex(), base["probe"]))
r0, o0 = pc.run_patched(anchor)
hb = R.words_digest(o0.get(oidx, []))
print("  baseline status=%s first 8 words=%s" % (r0["status"], ["%08x" % x for x in o0.get(oidx, [])[:8]]))
fire = []
for v in range(256):
    blk = bytes([v]) + anchor[1:]
    r2, o2 = pc.run_patched(blk)
    h2 = R.words_digest(o2.get(oidx, []))
    if h2 != hb or r2["status"] != "OK":
        fire.append((v, r2["status"]))
print("  byte0 values that FIRE (%d/256): %s" % (len(fire), [("0x%02x" % v, s) for v, s in fire[:24]]))
out["atomic_hi_byte0_fires"] = [[v, s] for v, s in fire]
pc.close()
(EXP / "raw" / "prefreeze" / "diag_fals2.json").write_text(json.dumps(out, indent=1))
