#!/usr/bin/env python3
"""PREFREEZE DIAGNOSTIC (NEVER evidence). Corrects diag_fals2's ATOMIC arm.

For STYLE-P cases `bytes` is the WHOLE patched `_agc.main` and `byte_index`/`tgt`
are ABSOLUTE offsets, so diag_fals2 mutated byte 0 of the kernel (its `get_sr`)
rather than byte 0 of `atomic_mem`, which is why 254/256 values "fired". Redone
at the real offset. Also asks the prior question: IS the k_atomic_hi observable
even deterministic? A nondeterministic observable cannot support any verdict.
"""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / "harness"))
import sweeprun as S
import casematrix as CM
import run as R

rep = json.loads((EXP / "work" / "anchors" / "anchor_report.json").read_text())
cases = CM.build_cases(rep)
work = EXP / "work" / "diag"
inputs = R.write_inputs(work)
res = {}
for arm in ("ATOMIC/highreg", "ATOMIC/lowreg", "ATOMIC/minop",
            "IFPUSH/flat", "IFPUSH/nest3.inner"):
    base = [x for x in cases if x["arm"] == arm and x["role"] == "baseline"][0]
    tgt = base["tgt"]
    ins, outs, grid, tg, oidx = R.INPLACE_BIND[base["probe"]]
    pc = S.InPlaceCarrier(EXP / "kernels" / "probes.metal", base["probe"], work,
                          dict((i, inputs[v]) for i, v in ins.items()), outs, grid, tg)
    pc.out_index = oidx
    anchor = bytes.fromhex(base["bytes"])
    print("=== %s  probe=%s  main=%dB  atomic/if at tgt=%d ==="
          % (arm, base["probe"], len(anchor), tgt))

    # (a) DETERMINISM: same bytes, 6 dispatches
    hs = []
    for _ in range(6):
        r, o = pc.run_patched(anchor)
        hs.append(R.words_digest(o.get(oidx, [])))
    det = len(set(hs)) == 1
    print("   determinism over 6 identical dispatches: %s (%d distinct digest(s))"
          % ("STABLE" if det else "*** UNSTABLE ***", len(set(hs))))

    # (b) byte0 of the instruction under test, at the CORRECT offset
    hb = hs[0]
    fire, nonok = [], []
    for v in range(256):
        blk = bytearray(anchor); blk[tgt] = v
        r, o = pc.run_patched(bytes(blk))
        h = R.words_digest(o.get(oidx, []))
        if r["status"] != "OK":
            nonok.append((v, r["status"]))
        elif h != hb:
            fire.append(v)
    print("   byte0-of-instruction values that CHANGE the observation: %d/256"
          % len(fire))
    print("   first few: %s" % ["0x%02x" % v for v in fire[:16]])
    print("   non-OK statuses: %d %s" % (len(nonok), [("0x%02x" % v, s) for v, s in nonok[:8]]))
    print("   does 0x00 fire? %s" % (0x00 in fire or any(v == 0 for v, _ in nonok)))
    res[arm] = {"deterministic": det, "distinct_baseline_digests": len(set(hs)),
                "n_fire": len(fire), "fire": fire[:64],
                "nonok": [[v, s] for v, s in nonok],
                "zero_fires": bool(0x00 in fire or any(v == 0 for v, _ in nonok)),
                "tgt": tgt}
    pc.close()
(EXP / "raw" / "prefreeze" / "diag_fals3.json").write_text(json.dumps(res, indent=1))
