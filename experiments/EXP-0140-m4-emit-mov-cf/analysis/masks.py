#!/usr/bin/env python3
"""Derive, for each swept 8-bit field, the tightest (mask, value) rule that
exactly characterises its 'accepted' value set -- or report that no single
mask/value pair does.  Pure post-processing of analysis/field_verdicts.json;
no GPU, no hardware claim of its own."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def fit(accepted, universe=256):
    acc = set(accepted)
    if not acc or len(acc) == universe:
        return None
    best = None
    for mask in range(1, 256):
        vals = {v & mask for v in acc}
        if len(vals) != 1:
            continue
        val = vals.pop()
        if {v for v in range(universe) if (v & mask) == val} == acc:
            bits = bin(mask).count("1")
            if best is None or bits < best[2]:
                best = (mask, val, bits)
    return best


def main():
    v = json.load(open(HERE / "field_verdicts.json"))
    out = {}
    for key, f in sorted(v["fields"].items()):
        for setname in ("inert_values", "moving_values", "matched_prediction"):
            s = f.get(setname)
            if not s or max(s) > 255:
                continue
            r = fit(s)
            if r:
                out["%s[%s]" % (key, setname)] = {
                    "rule": "(v & 0x%02X) == 0x%02X" % (r[0], r[1]),
                    "n_values": len(s), "mask_bits": r[2]}
            else:
                out["%s[%s]" % (key, setname)] = {"rule": None, "n_values": len(s)}
    (HERE / "field_masks.json").write_text(json.dumps(out, indent=1, sort_keys=True))
    for k, d in sorted(out.items()):
        print("%-46s %-26s n=%d" % (k, d["rule"] or "(no single mask fits)", d["n_values"]))


if __name__ == "__main__":
    main()
