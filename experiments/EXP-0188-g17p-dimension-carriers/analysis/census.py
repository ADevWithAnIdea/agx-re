#!/usr/bin/env python3
"""EXP-0188 PRE-FREEZE CENSUS (calibration only -- NO VERDICT MAY CITE IT).

Runs ON THE NEO. Compiles every carrier in `harness/carriers188.py` with our own
`shdump`, then reports, per (target, carrier):

  * does it compile at all with the exact pipeline the sweep will use;
  * does it EMIT the target instruction (a carrier that does not is dropped
    before device time, and the drop is recorded as a MEASURED NEGATIVE --
    "N carriers tried, 0 occurrences" -- not as a failure);
  * how many occurrences, at which offsets, with which BASELINE FIELD VALUE and
    which value of the DIMENSION FIELD, so `gen_arms.py` can choose occurrences
    that differ in the dimension the field controls rather than N copies of one
    arm (EXP-0164: eight carriers at samples=1 are ONE carrier);
  * what the pinned tokenizer decodes at each offset, and whether the descriptor
    signature also matches at non-parcel-aligned offsets (which would mean the
    signature is ambiguous).

THE DIMENSION FIELD is the whole point of this experiment and is named per
target in `harness/targets188.py`:

    if_push.scope       -> dimension field `scope_kind`  (0x01 cond-skip vs
                           0x1a loop-iter: the REGION KIND EXP-0184 never reached)
    simd_ballot.cache   -> the carrier's DIVERGENCE DEPTH (0..3 / loop)
    simd_shuffle.cache  -> same
    iadd2.b2_fmt        -> the carrier's OPERAND FORMAT (u32/s32/u16/u64/imm/uni)

If the compiler's own value of the target field already VARIES across the
dimension, the census says so before any device time is spent, and that variation
is itself the proof that the carrier set can express the field.

Output: `raw/prefreeze/census.json` + a human summary on stdout.

CLEAN-ROOM: OWN-SHADER. Only our own MSL is compiled and scanned.
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / "harness"))

import carriers188 as C      # noqa: E402
import locate188 as L        # noqa: E402
import targets188 as T       # noqa: E402

BIN = EXP / "work" / "bin"
WORK = EXP / "work" / "census"


def main():
    out = {}
    compiled = {}
    for tgt in T.TARGETS:
        mn, fld, group = tgt["mnemonic"], tgt["field"], tgt["group"]
        for name in tgt["carriers"]:
            spec = C.CARRIERS[name]
            key = "%s/%s" % (group, name)
            rec = {"group": group, "mnemonic": mn, "field": fld,
                   "carrier": name, "func": spec["func"], "metal": spec["metal"],
                   "dimension": tgt["dimension"],
                   "dimension_value": tgt["dimension_values"].get(name)}
            if name not in compiled:
                try:
                    compiled[name] = L.compile_carrier(
                        BIN, EXP / spec["metal"], spec["func"], WORK)
                except Exception as e:                          # noqa: BLE001
                    compiled[name] = ("ERR", str(e)[:600], None)
            arch, off, main = compiled[name]
            if arch == "ERR":
                rec["error"] = off
                out[key] = rec
                print("%-14s COMPILE FAIL %s" % (key, str(off)[:100]))
                continue
            rec.update(archive=arch, main_off=off, main_len=len(main),
                       main_sha256=hashlib.sha256(main).hexdigest())
            hits = L.find_occurrences(main, mn, step=1)
            s, w = L.field_span(mn, fld)
            for h in hits:
                raw = bytes.fromhex(h["bytes"])
                iv = int.from_bytes(raw, "little")
                h["baseline_field"] = (iv >> s) & ((1 << w) - 1)
                h["token"] = L.token_at(main, h["off"])
                for dn in tgt.get("occ_dimension_fields", []):
                    ds, dw = L.field_span(mn, dn)
                    h["dim_" + dn] = (iv >> ds) & ((1 << dw) - 1)
            rec["occurrences"] = hits
            rec["n_occ"] = len(hits)
            rec["n_occ_aligned"] = sum(1 for h in hits if h["parcel_aligned"])
            rec["distinct_baseline_field"] = sorted({h["baseline_field"] for h in hits})
            for dn in tgt.get("occ_dimension_fields", []):
                rec["distinct_" + dn] = sorted({h["dim_" + dn] for h in hits})
            out[key] = rec
            extra = " ".join("%s=%s" % (dn, rec["distinct_" + dn])
                             for dn in tgt.get("occ_dimension_fields", []))
            print("%-14s %-14s main=%-6d occ=%-3d aligned=%-3d %s=%s %s"
                  % (key, mn, len(main), len(hits), rec["n_occ_aligned"],
                     fld, rec["distinct_baseline_field"][:8], extra))
    d = EXP / "raw" / "prefreeze"
    d.mkdir(parents=True, exist_ok=True)
    (d / "census.json").write_text(json.dumps(out, indent=1, sort_keys=True))
    print("\nwrote", d / "census.json")


if __name__ == "__main__":
    main()
