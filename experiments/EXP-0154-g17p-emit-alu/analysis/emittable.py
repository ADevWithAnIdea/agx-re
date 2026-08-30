#!/usr/bin/env python3
"""EXP-0154: which instructions does this experiment make EMITTABLE?

Merges `analysis/field_verdicts.json` with the committed
`tools/agx-isa/validation.json` under the merge policy EXP-0139 established --
evidence accumulates, so each field takes the STRONGER of (label already
committed, this experiment's verdict) -- and applies the emittable rule from
`docs/evidence-classification.md` section 2: an instruction qualifies only if
EVERY field in its db.json descriptor is `hardware-run` or
`isolated-byte-diff`.

Read-only. Does not edit db.json or validation.json (the orchestrator owns
those).
"""
from __future__ import print_function

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / "harness"))
import isa_helpers as H  # noqa: E402

RANK = {"hardware-run": 6, "isolated-byte-diff": 5, "corpus-correlation": 4,
        "tokenization-only": 3, "single-template-inference": 2,
        "api-accept-reject": 1, "host-private": 0, "untested": 0}
GOOD = ("hardware-run", "isolated-byte-diff")


def main():
    db = json.loads((H.ISA_DIR / "db.json").read_text())
    INS = dict((i["mnemonic"], i) for i in db["instructions"])
    # db.json's `emit_unsafe` flag overrides field labels entirely -- that is why
    # validation.json's own coverage block lists 38 emittable instructions where a
    # pure field-label count gives 39 (`tg_addr_compute` is field-complete but
    # emit_unsafe: over-fitted match, two live operand bytes unmodelled).
    UNSAFE = set(i["mnemonic"] for i in db["instructions"] if i.get("emit_unsafe"))
    VAL = json.loads((H.ISA_DIR / "validation.json").read_text())["instructions"]
    MINE = json.loads((HERE / "field_verdicts.json").read_text())

    mine_by = {}
    for k, v in MINE.items():
        if k.startswith("_") or k == "db_defects" or "." not in k:
            continue
        base = k.split("@byte+")[0]
        mn, fld = base.split(".", 1)
        cur = mine_by.get((mn, fld))
        # a wide field swept byte-wise: the composite takes the WEAKEST byte
        if cur is None or RANK[v["label"]] < RANK[cur["label"]]:
            mine_by[(mn, fld)] = v

    before_ok = set()
    after_ok = set()
    rows = []
    for mn, d in INS.items():
        names = [f["name"] for f in d["fields"]]
        pre, post, changed = [], [], []
        for n in names:
            old = VAL.get(mn, {}).get(n, {}).get("label", "untested")
            new = mine_by.get((mn, n), {}).get("label")
            merged = old if (new is None or RANK[new] <= RANK[old]) else new
            pre.append(old in GOOD)
            post.append(merged in GOOD)
            if new and RANK[new] > RANK[old]:
                changed.append((n, old, new))
        binst_ok = VAL.get(mn, {}).get("_instruction", {}).get("label", "untested") in GOOD
        pre_all = ((all(pre) and names) or (not names and binst_ok)) and mn not in UNSAFE
        post_all = ((all(post) and names) or (not names and binst_ok)) and mn not in UNSAFE
        if pre_all:
            before_ok.add(mn)
        if post_all:
            after_ok.add(mn)
        if changed or (post_all and not pre_all):
            rows.append((mn, pre_all, post_all,
                         sum(1 for x in post if x), len(names), changed))

    newly = sorted(after_ok - before_ok)
    print("emittable BEFORE : %d" % len(before_ok))
    print("emittable AFTER  : %d   (+%d)" % (len(after_ok), len(newly)))
    print("newly emittable  :", ", ".join(newly) if newly else "(none)")
    print()
    nup = sum(len(r[5]) for r in rows)
    print("fields upgraded  : %d" % nup)
    for mn, a, b, ng, nt, ch in sorted(rows):
        if ch:
            print("  %-18s %d/%d fields at emitter grade%s"
                  % (mn, ng, nt, "   *** NOW EMITTABLE ***" if (b and not a) else ""))
            for n, o, w in ch:
                print("      %-14s %-24s -> %s" % (n, o, w))
    out = {"emittable_before": sorted(before_ok), "emittable_after": sorted(after_ok),
           "newly_emittable": newly, "fields_upgraded": nup,
           "upgrades": dict(("%s.%s" % (mn, n), {"from": o, "to": w})
                            for mn, a, b, ng, nt, ch in rows for n, o, w in ch)}
    (HERE / "emittable.json").write_text(json.dumps(out, indent=1, sort_keys=True))
    print("\nwrote", HERE / "emittable.json")


if __name__ == "__main__":
    main()
