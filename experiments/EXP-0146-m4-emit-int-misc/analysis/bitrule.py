#!/usr/bin/env python3
"""Derive, for a field's observed OK-value set, the exact 'required bits / don't-care bits'
rule -- i.e. whether OK == { base | any subset of free_mask }. Purely arithmetic on the
committed observations; no hardware access."""


def rule(ok_values, width_bits=8):
    ok = set(ok_values)
    if not ok:
        return None
    universe = (1 << width_bits) - 1
    base = None
    free = 0
    for b in range(width_bits):
        bit = 1 << b
        # bit b is free iff toggling it maps the ok-set onto itself
        if all(((v ^ bit) in ok) for v in ok):
            free |= bit
    # required pattern = any ok value with the free bits cleared
    cand = sorted(v & ~free for v in ok)
    if len(set(cand)) != 1:
        return {"exact_mask_rule": False, "free_mask": free, "n_ok": len(ok)}
    base = cand[0]
    predicted = set()
    f = [1 << b for b in range(width_bits) if free & (1 << b)]
    for i in range(1 << len(f)):
        v = base
        for j, bit in enumerate(f):
            if i & (1 << j):
                v |= bit
        predicted.add(v)
    return {"exact_mask_rule": predicted == ok, "required_value": base,
            "required_mask": universe & ~free, "free_mask": free, "n_ok": len(ok)}


if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import verdicts as V
    v = V.build()
    out = {}
    for k, d in sorted(v.items()):
        okv = [x for x in d["ok_values"] if isinstance(x, int)]
        w = d["db_width"] or 8
        if d["field"].startswith("byte+"):
            w = 8
        r = rule(okv, w)
        out[k] = r
        if r and r.get("exact_mask_rule"):
            print("%-38s REQ 0x%02x mask 0x%02x  free 0x%02x  (n_ok=%d)" %
                  (k, r["required_value"], r["required_mask"], r["free_mask"], r["n_ok"]))
        elif r:
            print("%-38s no clean mask rule (free 0x%02x, n_ok=%d)" %
                  (k, r["free_mask"], r["n_ok"]))
    Path(Path(__file__).resolve().parent / "bit_rules.json").write_text(
        json.dumps(out, indent=1, sort_keys=True))
