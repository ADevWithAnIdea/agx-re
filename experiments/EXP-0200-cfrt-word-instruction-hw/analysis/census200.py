#!/usr/bin/env python3
"""EXP-0200 pre-freeze census (runs ON THE NEO; writes raw/prefreeze/census200.json).

  python3 analysis/census200.py

Compiles every carrier from OUR OWN MSL and reports, per carrier:

  * `walk` -- the token stream the PINNED tokenizer produces from offset 0, with
    the leftover, because a walk that stops early can only UNDERCOUNT.
  * `walk_holes[mnemonic]` -- WALK-CONFIRMED occurrences of each of the six
    target words plus `pad_operand`: offset, length and bytes. These are the
    natural holes the transparency arm substitutes into. Signature hits are
    reported separately as `sig_hits`, as an upper bound only: a signature hit
    may sit INTERIOR to a longer token and be no carrier at all (EXP-0148's
    `cubearray_coord_const` is exactly that shape).
  * `sig_holes[mnemonic]` -- the AMENDED source of 4-byte transparency holes
    (PRE_REGISTRATION.md 7.4, amendment A1). The pinned tokenizer's walk stops
    at 60-62 tokens on EVERY intersection_query carrier (EXP-0187 4.2,
    EXP-0157 measured the same), so `walk_holes` is empty for all three 4-byte
    targets on every RT carrier -- a tokenizer limitation, NOT evidence of
    absence. A signature hit is promoted to a hole only if it is
    PARCEL-ALIGNED and `decode_one` AT THAT OFFSET returns that mnemonic with
    the descriptor's own length. Both numbers are reported so the promotion is
    auditable.
  * `ruler_candidates` -- runs of consecutive walked instructions summing to
    exactly 8 bytes in the 2 %..75 % window. Which of them are usable is decided
    on the DEVICE by run200.py --probe-holes, not here.

NO VERDICT MAY CITE THIS FILE. It is calibration: it chooses where to look, and
the frozen gate in analysis/verdicts200.py never reads it.

CLEAN-ROOM: OWN-SHADER. Only our own compiled MSL is scanned.
"""
import json
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(EXP / "harness"))
import carriers200 as C          # noqa: E402
import locate200 as L            # noqa: E402

TARGETS = ("n1_word", "n2_compact2", "n3_word",
           "rtq_pred", "n4_cf_word", "n4_rt_word", "pad_operand")

BIN = EXP / "work" / "bin"
WORK = EXP / "work"


def main():
    out = {}
    for name in sorted(C.CARRIERS):
        spec = C.CARRIERS[name]
        try:
            arch, off, main = L.compile_carrier(
                BIN, EXP / spec["metal"], spec["func"], WORK / "arch")
        except Exception as e:                                  # noqa: BLE001
            out[name] = {"compile_failed": str(e)[:400]}
            print("%-10s COMPILE FAILED %s" % (name, str(e)[:120]))
            continue
        bounds, leftover = L.walk_boundaries(main)
        rec = {"func": spec["func"], "main_len": len(main), "main_off": off,
               "n_tokens": len(bounds), "leftover_hex": leftover,
               "walk": [{"off": o, "len": l, "mnemonic": m}
                        for (o, l, m) in bounds],
               "walk_holes": {}, "sig_hits": {}, "sig_holes": {},
               "ruler_candidates": L.find_runs(bounds, len(main), 8, 0.02, 0.75)}
        for mn in TARGETS:
            hits = L.find_occurrences(main, mn)
            rec["sig_hits"][mn] = len(hits)
            holes = []
            for (o, l, m) in bounds:
                if m == mn:
                    holes.append({"off": o, "len": l,
                                  "bytes": main[o:o + l].hex()})
            rec["walk_holes"][mn] = holes
            sig = []
            for h in hits:
                if not h["parcel_aligned"]:
                    continue
                tok = L.token_at(main, h["off"])
                if tok.get("mnemonic") == mn and tok.get("length") == h["len"]:
                    sig.append({"off": h["off"], "len": h["len"],
                                "bytes": h["bytes"], "decode_one": tok})
            rec["sig_holes"][mn] = sig
        out[name] = rec
        print("%-10s tokens=%-4d ruler_cand=%-3d  %s"
              % (name, len(bounds), len(rec["ruler_candidates"]),
                 " ".join("%s:w%d/s%d/h%d" % (m, len(rec["walk_holes"][m]),
                                              rec["sig_hits"][m],
                                              len(rec["sig_holes"][m]))
                          for m in TARGETS)))
    out_name = sys.argv[1] if len(sys.argv) > 1 else "census200.json"
    p = EXP / "raw" / "prefreeze" / out_name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=1, sort_keys=True))
    print("wrote", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
