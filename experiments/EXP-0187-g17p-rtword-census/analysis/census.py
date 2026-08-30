#!/usr/bin/env python3
"""EXP-0187 PRE-FREEZE CENSUS for target 1 (calibration only -- NO VERDICT MAY CITE IT).

Runs ON THE NEO. Compiles every RT carrier in `harness/carriers187.py` with our
own `shdump`, then reports per carrier:

  * does it compile at all with the exact pipeline the sweep will use;
  * does it EMIT `n4_rt_word` (a carrier that does not is dropped before device
    time, and the drop is recorded as a measured negative -- "N carriers tried",
    not a failure);
  * how many occurrences, at which offsets, with which BASELINE `dst` value, so
    `gen_arms.py` can choose occurrences that differ in the dimension the field
    controls rather than N copies of one arm (EXP-0164: eight carriers at
    samples=1 are ONE carrier);
  * what the pinned tokenizer decodes at each offset AND at off+4 -- the latter
    because `n4_rt_word` has exactly ONE modelled field, so no same-instruction
    control exists, and the nearest available detection-power control is a
    known-live field of the instruction the word is emitted immediately before
    (`db.json`: if_push / frame_marker / reg_move; "+4 lands on the next op
    leader in all occurrences");
  * whether the signature also matches at non-parcel-aligned offsets (which
    would mean the descriptor signature is ambiguous).

Output: `raw/prefreeze/census.json` + a human summary on stdout.

Derived from EXP-0184 analysis/census.py (our own code, cited).
CLEAN-ROOM: OWN-SHADER. Only our own MSL is compiled and scanned.
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / "harness"))

import carriers187 as C      # noqa: E402
import locate187 as L        # noqa: E402

BIN = EXP / "work" / "bin"
WORK = EXP / "work" / "census"
MNEMONIC = "n4_rt_word"
FIELD = "dst"

# Known-live fields of the ops `n4_rt_word` is emitted immediately before, from
# the LIVE validation.json read at pre-registration time (EXP-0184 promoted
# rt_query_traverse.dst; EXP-0140 promoted if_push.scope_kind). A control arm is
# only generated when the successor is one of these.
SUCCESSOR_CONTROLS = {
    "if_push":            ("scope_kind", 24, 8),
    "pop_reconverge":     ("scope_kind", 24, 8),
    "rt_query_traverse":  ("opB", 56, 8),
    "frame_marker_compact": ("b1", 8, 8),
}


def main():
    out = {}
    for name in sorted(C.CARRIERS):
        spec = C.CARRIERS[name]
        rec = {"group": "rq", "mnemonic": MNEMONIC, "func": spec["func"],
               "metal": spec["metal"], "accel_kind": spec["accel_kind"]}
        try:
            arch, off, main = L.compile_carrier(
                BIN, EXP / spec["metal"], spec["func"], WORK)
        except Exception as e:                                  # noqa: BLE001
            rec["error"] = str(e)[:600]
            out[name] = rec
            print("%-10s COMPILE FAIL %s" % (name, str(e)[:110]))
            continue
        rec.update(archive=arch, main_off=off, main_len=len(main),
                   main_sha256=hashlib.sha256(main).hexdigest())
        by, ntok, leftover = L.walk(main)
        rec["walk_tokens"] = ntok
        rec["walk_leftover_hex"] = leftover
        rec["walk_hits"] = by.get(MNEMONIC, [])
        s, w = L.field_span(MNEMONIC, FIELD)
        hits = L.find_occurrences(main, MNEMONIC, step=1)
        for h in hits:
            raw = bytes.fromhex(h["bytes"])
            h["baseline_field"] = (int.from_bytes(raw, "little") >> s) & ((1 << w) - 1)
            h["token"] = L.token_at(main, h["off"])
            h["succ_token"] = L.token_at(main, h["off"] + h["len"])
            sm = (h["succ_token"] or {}).get("mnemonic")
            h["succ_control"] = SUCCESSOR_CONTROLS.get(sm)
            h["walk_confirmed"] = h["off"] in rec["walk_hits"]
        rec["occurrences"] = hits
        rec["n_occ"] = len(hits)
        rec["n_occ_aligned"] = sum(1 for h in hits if h["parcel_aligned"])
        rec["n_occ_walk_confirmed"] = sum(1 for h in hits if h["walk_confirmed"])
        rec["distinct_baseline_field"] = sorted({h["baseline_field"] for h in hits})
        rec["successors"] = sorted({str((h["succ_token"] or {}).get("mnemonic"))
                                    for h in hits})
        # CARRIER-LEVEL detection-power control. `n4_rt_word` has exactly ONE
        # modelled field, so no same-instruction control is possible and only 3
        # of 32 occurrences are followed by an op with a known-live field. The
        # fallback is `rt_query_traverse.opB`, HW-VALIDATED load-bearing on A18
        # (EXP-M4-14) and re-measured on G17P by EXP-0184. It establishes that
        # the CARRIER has an observable ray-query path -- weaker than an
        # occurrence-level control, and labelled as such in every verdict.
        rtq = [h for h in L.find_occurrences(main, "rt_query_traverse", step=1)
               if h["parcel_aligned"]]
        for h in rtq:
            h["token"] = L.token_at(main, h["off"])
        rec["rtq_occurrences"] = rtq
        rec["n_rtq"] = len(rtq)
        out[name] = rec
        print("%-10s main=%-6d occ=%-3d aligned=%-3d walk=%-3d rtq=%-3d baselines=%s succ=%s"
              % (name, len(main), len(hits), rec["n_occ_aligned"],
                 rec["n_occ_walk_confirmed"], rec["n_rtq"],
                 [hex(x) for x in rec["distinct_baseline_field"][:8]],
                 rec["successors"][:5]))
    d = EXP / "raw" / "prefreeze"
    d.mkdir(parents=True, exist_ok=True)
    (d / "census.json").write_text(json.dumps(out, indent=1, sort_keys=True))
    print("\nwrote", d / "census.json")


if __name__ == "__main__":
    main()
