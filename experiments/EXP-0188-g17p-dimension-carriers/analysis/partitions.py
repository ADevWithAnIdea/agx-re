#!/usr/bin/env python3
"""EXP-0188 behaviour partitions and load-bearing-bit search.

    python3 analysis/partitions.py raw/<run01> raw/<run02>

For every TARGET arm it groups the swept values by their exact observed outcome
partition key (outcome + the full observed value vector), reports the groups, and
then searches for the SMALLEST SET OF BITS of the field that explains the
partition: for each candidate bit mask, does `value & mask` determine the group,
with no exceptions, in BOTH runs?

This is what turns "the field moved" into something an emitter can use. A field
that moves tells an implementer nothing on its own; "bit 1 selects behaviour A vs
behaviour B and bits 0,2..7 are inert" is an encoding rule.

Only values that AGREE across the two runs are used, and the search reports the
number of exceptions so a near-fit cannot be passed off as a fit.

CLEAN-ROOM: pure analysis of our own raw captures.
"""
import hashlib
import itertools
import json
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(EXP / "analysis"))
from verdicts import load, index, vkey, _clean       # noqa: E402


def _arms_path():
    """The gated pair ran against the A3 re-scoped arm list where it exists; the
    frozen `arms188.json` is never modified and remains the parent document."""
    g = EXP / "harness" / "arms188_gated.json"
    return g if g.exists() else (EXP / "harness" / "arms188.json")


def bit_rule(vals_to_group, width):
    """Smallest bit mask over the field whose value determines the group."""
    best = None
    for k in range(1, width + 1):
        for bits in itertools.combinations(range(width), k):
            mask = sum(1 << b for b in bits)
            m = {}
            bad = 0
            for v, g in vals_to_group.items():
                key = v & mask
                if key in m and m[key] != g:
                    bad += 1
                else:
                    m.setdefault(key, g)
            if bad == 0:
                return {"bits": list(bits), "mask": mask,
                        "classes": {hex(k2): g for k2, g in sorted(m.items())}}
            if best is None or bad < best["exceptions"]:
                best = {"bits": list(bits), "mask": mask, "exceptions": bad}
    return {"no_exact_rule": True, "closest": best}


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    i1, i2 = index(load(sys.argv[1])), index(load(sys.argv[2]))
    arms = {a["arm"]: a for a in
            json.loads((_arms_path()).read_text())["arms"]}
    out = {}
    for name, a in sorted(arms.items()):
        if a["role"] != "target" or name not in i1 or name not in i2:
            continue
        c1, c2 = _clean(i1[name]), _clean(i2[name])
        vals = sorted(set(c1) & set(c2))
        agreed = {v: vkey(c1[v]) for v in vals if vkey(c1[v]) == vkey(c2[v])}
        groups = {}
        for v, k in agreed.items():
            groups.setdefault(k, []).append(v)
        rec = {"carrier": a["carrier"], "occ": a["occ"], "off": a["off"],
               "field": a["field"], "width": a["width"],
               "baseline_field_value": a.get("baseline_field"),
               "occ_dimension": a.get("occ_dimension"),
               "n_values_agreeing": len(agreed),
               "n_groups": len(groups),
               "groups": {k.split("|")[0] + "/" + k.split("|")[1][:8]:
                          {"n": len(v), "values": v if len(v) <= 24 else
                           v[:12] + ["..."] + v[-6:]}
                          for k, v in sorted(groups.items(),
                                             key=lambda kv: -len(kv[1]))}}
        if len(groups) > 1:
            rec["bit_rule"] = bit_rule({v: k for v, k in agreed.items()},
                                       a["width"])
        out[name] = rec
    p = EXP / "analysis" / "partitions.json"
    p.write_text(json.dumps(out, indent=1, sort_keys=True))
    for name, r in sorted(out.items()):
        if r["n_groups"] > 1:
            br = r.get("bit_rule", {})
            print("%-40s groups=%-3d bits=%s" %
                  (name, r["n_groups"], br.get("bits", br.get("closest"))))
    print("wrote", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
