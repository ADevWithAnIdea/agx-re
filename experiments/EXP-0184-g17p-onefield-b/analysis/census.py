#!/usr/bin/env python3
"""EXP-0184 PRE-FREEZE CENSUS (calibration only -- NO VERDICT MAY CITE IT).

Runs ON THE NEO. Compiles every carrier in `harness/carriers184.py` with our own
`shdump`, then reports, per carrier:

  * does it compile at all with the exact pipeline the sweep will use;
  * does it EMIT the target instruction (a carrier that does not is dropped
    before device time, and the drop is recorded as a measured negative --
    "N carriers tried", not a failure);
  * how many occurrences, at which offsets, with which BASELINE FIELD VALUE, so
    `gen_arms.py` can choose occurrences that differ in the dimension the field
    controls rather than N copies of one arm (EXP-0164: eight carriers at
    samples=1 are ONE carrier);
  * what the pinned tokenizer decodes at each offset, and whether the descriptor
    signature also matches at non-parcel-aligned offsets (which would mean the
    signature is ambiguous).

Output: `raw/prefreeze/census.json` + a human summary on stdout.

CLEAN-ROOM: OWN-SHADER. Only our own MSL is compiled and scanned.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / "harness"))

import carriers184 as C      # noqa: E402
import locate184 as L        # noqa: E402

BIN = EXP / "work" / "bin"
WORK = EXP / "work" / "census"

TARGETS = {
    "cs":  ("copysign", ["cs_load", "cs_alu", "cs_mix", "cs_two", "cs_chain"]),
    "cvt": ("cvt_f2i", ["cvt_s32", "cvt_u32", "cvt_s16", "cvt_u16", "cvt_h32"]),
    "cf":  ("if_push", ["cf_if1", "cf_if2", "cf_if3", "cf_loop", "cf_loopif"]),
    "rq":  ("rt_query_traverse",
            ["rq_mdist", "rq_mprim", "rq_cdist", "rq_ccount"]),
}


def main():
    out = {}
    for group, (mn, carriers) in TARGETS.items():
        for name in carriers:
            spec = C.CARRIERS[name]
            rec = {"group": group, "mnemonic": mn, "func": spec["func"],
                   "metal": spec["metal"]}
            try:
                arch, off, main = L.compile_carrier(
                    BIN, EXP / spec["metal"], spec["func"], WORK)
            except Exception as e:                              # noqa: BLE001
                rec["error"] = str(e)[:600]
                out[name] = rec
                print("%-10s COMPILE FAIL %s" % (name, str(e)[:110]))
                continue
            import hashlib
            rec.update(archive=arch, main_off=off, main_len=len(main),
                       main_sha256=hashlib.sha256(main).hexdigest())
            hits = L.find_occurrences(main, mn, step=1)
            for h in hits:
                raw = bytes.fromhex(h["bytes"])
                s, w = L.field_span(mn, _target_field(mn))
                h["baseline_field"] = (int.from_bytes(raw, "little") >> s) & ((1 << w) - 1)
                h["token"] = L.token_at(main, h["off"])
            rec["occurrences"] = hits
            rec["n_occ"] = len(hits)
            rec["n_occ_aligned"] = sum(1 for h in hits if h["parcel_aligned"])
            rec["distinct_baseline_field"] = sorted(
                {h["baseline_field"] for h in hits})
            out[name] = rec
            print("%-10s %-18s main=%-6d occ=%-3d aligned=%-3d baselines=%s"
                  % (name, mn, len(main), len(hits), rec["n_occ_aligned"],
                     rec["distinct_baseline_field"][:8]))
    d = EXP / "raw" / "prefreeze"
    d.mkdir(parents=True, exist_ok=True)
    (d / "census.json").write_text(json.dumps(out, indent=1, sort_keys=True))
    print("\nwrote", d / "census.json")


def _target_field(mn):
    return {"copysign": "operands", "cvt_f2i": "b9", "if_push": "scope",
            "rt_query_traverse": "dst"}[mn]


if __name__ == "__main__":
    main()
