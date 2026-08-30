#!/usr/bin/env python3
"""EXP-0205 PRE-FREEZE CALIBRATION (runs ON THE NEO under ~/agxre/EXP-0205).

    python3 analysis/calibrate.py > raw/prefreeze/calibration.txt

This is explicitly PRE-FREEZE work and its output lands in `raw/prefreeze/`,
never in a gated run directory.  It answers the questions a frozen contract has
to state and cannot guess:

  1. do our own kernels compile on G17P at all;
  2. how many occurrences of the target descriptor each carrier contains (an
     arm is only usable if the occurrence whose result reaches the output can
     be named unambiguously);
  3. what the BASELINE VALUE of every field under test actually is, including
     `opcls`, which decides which half of db.json's `op` enum pairs the host
     oracle must predict;
  4. what the UNMUTATED program outputs, so the host oracles are checked
     against hardware BEFORE any sweep is scored against them;
  5. THE MEASURED SIMD WIDTH -- recorded, never assumed.

CLEAN-ROOM: OWN-SHADER + HW-PROBE.  Every byte is the compiled form of our own
MSL in kernels/.  No Apple binary is inspected.
"""
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / "harness"))

import carriers205 as C          # noqa: E402
import locate205 as L            # noqa: E402
import saferunner205 as SR       # noqa: E402

SafeRunner = SR.make_classes(str(L.PINNED))
BIN = EXP / "work" / "bin"
WORK = EXP / "work"

TARGETS = {
    "sb_ballot": ("simd_ballot", ["pred", "cache", "psrc", "dst"]),
    "sb_active": ("simd_ballot", ["pred", "cache", "psrc", "dst"]),
    "sb_reuse":  ("simd_ballot", ["pred", "cache", "psrc", "dst"]),
    "sr_sum":    ("simd_reduce", ["op", "dtype", "opcls", "scope", "src", "dst", "cache"]),
    "sr_scan":   ("simd_reduce", ["op", "dtype", "opcls", "scope", "src", "dst", "cache"]),
    "sr_max":    ("simd_reduce", ["op", "dtype", "opcls", "scope", "src", "dst", "cache"]),
    "sr_fsum":   ("simd_reduce", ["op", "dtype", "opcls", "scope", "src", "dst", "cache"]),
    "sh_bc":     ("simd_shuffle", ["dir", "cache", "mode", "lane", "src", "dst"]),
    "sh_xor":    ("simd_shuffle", ["dir", "cache", "mode", "lane", "src", "dst"]),
    "sh_reuse":  ("simd_shuffle", ["dir", "cache", "mode", "lane", "src", "dst"]),
    "sb_width":  (None, []),
}


def main():
    out = {"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "carriers": {}}
    indir = WORK / "inputs"
    indir.mkdir(parents=True, exist_ok=True)
    spdir = WORK / "splice"
    spdir.mkdir(parents=True, exist_ok=True)

    for name, (mn, fields) in TARGETS.items():
        spec = C.CARRIERS[name]
        rec = {"func": spec["func"], "metal": spec["metal"], "target_instr": mn}
        try:
            arch, moff, main = L.compile_carrier(
                BIN, EXP / spec["metal"], spec["func"], WORK / "arch")
        except Exception as e:                                  # noqa: BLE001
            rec["compile_error"] = str(e)[:600]
            out["carriers"][name] = rec
            print(json.dumps({name: rec}, indent=1))
            continue
        rec["main_len"] = len(main)
        rec["main_hex"] = main.hex()
        if mn:
            occs = L.find_occurrences(main, mn)
            for o in occs:
                raw = bytes.fromhex(o["bytes"])
                o["fields"] = {}
                for f in fields:
                    try:
                        s, w = L.field_span(mn, f)
                    except KeyError:
                        continue
                    o["fields"][f] = L.get_bits(raw, s, w)
                o["token"] = L.token_at(main, o["off"])
            rec["occurrences"] = occs
            rec["n_occ"] = len(occs)

        ins = {}
        for idx, (fn, blob) in C.out_inputs(name).items():
            p = indir / fn
            p.write_bytes(blob)
            ins[idx] = str(p)
        runner = SafeRunner(source=str(EXP / spec["metal"]), function=spec["func"],
                            fast_math=False,
                            agxrun_persist=str(BIN / "agxrun_persist"))
        rec["device"] = runner.device
        resp = runner.request(archive=arch, grid=spec["grid"], tg=spec["tg"],
                              ins=ins, outs={0: 4 * spec["nwords"]}, timeout=12.0)
        rec["status"] = resp["status"]
        rec["gputime_ns"] = resp.get("gputime_ns")
        rec["error"] = resp.get("error")
        blob = resp["outs"].get(0, b"")
        if blob:
            obs, words = C.summarize(name, blob)
            rec["observed_vals"] = ["0x%08x" % v for v in obs["vals_u32"]]
            rec["observed_sec"] = ["0x%08x" % v for v in obs["sec_u32"]]
            rec["sentinel_ok"] = C.sentinel_ok(name, words)
            rec["tail_poison_ok"] = obs["tail_poison_ok"]
            rec["unwritten"] = C.unwritten(name, words)
            exp = C.baseline_oracle(name)
            if exp is not None:
                rec["oracle_vals"] = ["0x%08x" % (v & C.M32) for v in exp]
                rec["oracle_match"] = C.match_oracle(name, words, exp)
            sec = C.baseline_sec_oracle(name)
            if sec is not None:
                rec["oracle_sec"] = ["0x%08x" % (v & C.M32) for v in sec]
                rec["oracle_sec_match"] = all(
                    words[32 + k] == (sec[k] & C.M32) for k in range(32))
            if name == "sb_width":
                w = obs["vals_u32"]
                rec["simd_width_measured"] = sorted({(v >> 16) & 0xFFFF for v in w})
                rec["lane_ids"] = [v & 0xFF for v in w]
                rec["simdgroup_ids"] = sorted({(v >> 8) & 0xFF for v in w})
        runner.close()
        out["carriers"][name] = rec
        print(json.dumps({name: {k: v for k, v in rec.items()
                                 if k not in ("main_hex",)}}, indent=1))

    dest = EXP / "raw" / "prefreeze"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "calibration.json").write_text(json.dumps(out, indent=1))
    print("wrote", dest / "calibration.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
