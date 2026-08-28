#!/usr/bin/env python3
"""EXP-0141: derive, for each swept byte/field, the tightest MASK/PATTERN rule
that exactly reproduces the accepted-value set -- or report that no single
mask/pattern rule does.

This exists so the prose in RESULTS.md ("bits 0-2 must be 0, bits 3-5 are
don't-care") is CHECKED against the raw data rather than eyeballed from a
compressed range string. A field whose accepted set is not a mask/pattern is
printed as `NOT A MASK RULE`, which is itself a result.
"""
import json
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent


def rule(accepted, width):
    """Bits constant across all accepted values -> candidate mask/pattern."""
    if not accepted:
        return None, None, False
    universe = 1 << width
    ones = accepted[0]
    zeros = ~accepted[0]
    for v in accepted:
        ones &= v
        zeros &= ~v
    mask = (ones | zeros) & (universe - 1)
    pattern = ones & mask
    predicted = {v for v in range(universe) if (v & mask) == pattern}
    return mask, pattern, predicted == set(accepted)


def main():
    run = sys.argv[1] if len(sys.argv) > 1 else "m4-20260828-run11"
    rows = [json.loads(l) for l in (EXP / "raw" / run / "sweep.jsonl").open()]
    arms, seen = [], set()
    for r in rows:
        if r["arm"] in seen or r["arm"].startswith(("_HEALTH", "CTRL")):
            continue
        seen.add(r["arm"]); arms.append(r["arm"])
    out = {}
    for a in arms:
        rs = [r for r in rows if r["arm"] == a and not str(r["field"]).startswith("_")]
        vals = sorted({r["value"] for r in rs})
        ok = sorted({r["value"] for r in rs if r["outcome"] == "ok"})
        if not vals:
            continue
        width = max(1, max(vals).bit_length())
        width = 8 if max(vals) < 256 and len(vals) > 128 else width
        m, p, exact = rule(ok, width)
        out[a] = {"instr": rs[0]["instr"], "field": rs[0]["field"],
                  "n_swept": len(vals), "n_accepted": len(ok),
                  "mask": m, "pattern": p, "mask_rule_is_exact": exact,
                  "rule": (None if m is None else
                           ("v & 0x%02X == 0x%02X" % (m, p)) + ("" if exact else "  (NOT EXACT)")),
                  "free_bits": None if m is None else
                               [i for i in range(width) if not (m >> i) & 1]}
    (EXP / "analysis" / "bitrules.json").write_text(
        json.dumps(out, indent=1, sort_keys=True) + "\n")
    for a in arms:
        if a not in out:
            continue
        d = out[a]
        tag = "EXACT" if d["mask_rule_is_exact"] else "not-a-mask"
        print("  %-32s %-22s %3d/%-4d  %-24s %s"
              % (a, d["field"][:22], d["n_accepted"], d["n_swept"],
                 d["rule"] or "-", tag))


if __name__ == "__main__":
    main()
