#!/usr/bin/env python3
"""gen_arms.py -- generate harness/arms.py from the PRE-FREEZE census.

The arm list is GENERATED, then FROZEN, then asserted byte-exact at run time
(run.py refuses any arm whose instruction bytes or offset moved since the
census).  This file is the only place the selection rule lives, so a reviewer can
read the rule rather than infer it from the arms.

FROZEN SELECTION RULE
  1. Only occurrences of the target mnemonic in the FRAGMENT stage (tex_deriv is
     fragment-only; the write and sample carriers are fragment programs).
  2. PLAUSIBILITY FILTER, per mnemonic, to reject anchored-scan artefacts on the
     carriers whose forward tokenization stops early:
       tex_write   -- byte+12 (`wop`) must be in 0x88..0x8F.  db.json documents
                      byte+12 as "0x88 base + N for the Nth write in a shader",
                      so a hit outside that window is not a write.  This rejects
                      exactly one occurrence (twcomp#3, wop 0x87) and keeps every
                      occurrence that corresponds to a write in our own MSL.
       tex_sample  -- byte+12 (`tex_type`) must be in {1,2,3} (db.json's complete
                      enum: 2D-class / 3D / buffer).
       tex_deriv   -- byte+6 (`axis`) must be 0x90 or 0x92 (db.json's complete
                      enum: dfdy / dfdx).
  3. SPAN THE CARRIERS FIRST.  Every carrier authored for the mnemonic gets one
     arm (its first plausible occurrence) before any carrier gets a second.  The
     CARRIER is the dimension -- that is the whole premise of this experiment --
     so a budget that spends itself on three occurrences of one carrier is the
     failure mode the design exists to avoid.
  4. THEN SPAN THE FIELD'S OWN BASELINE VALUES.  Any occurrence whose
     compiler-chosen value of the target field is not yet represented is added
     next.  An occurrence whose baseline differs is direct evidence that the
     carrier set spans the field's own value space (tex_write.amode takes BOTH
     0x54 and 0x55 in our own census, which no prior experiment's arms did).
  4b. THEN SPAN THE (CARRIER, BASELINE VALUE) PAIRS.  A second carrier that also
     reaches an already-seen baseline value is still a second carrier, so any
     (carrier, value) pair not yet represented is added next.
  5. Then fill the mnemonic's budget ROUND-ROBIN over carriers (not in raw
     occurrence order, which would spend the budget on whichever carrier happens
     to emit the most copies), at most CAP arms per carrier.
"""
import json, os, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "harness"))
sys.path.insert(0, os.path.join(HERE, "pinned"))
import carriers as CA                     # noqa: E402

CENSUS = os.path.join(HERE, "raw", "prefreeze", "census_run2.json")
CAP = 3

# which carriers serve which mnemonic (frozen; mirrors carriers.py `why`)
SERVES = {
    "tex_sample": ["msfilt", "msfixl", "msgath", "msread", "mscmp", "mslodq"],
    "tex_deriv":  ["deriv", "deriv2"],
    "tex_write":  ["twmip", "twbuf", "twcube", "twcomp", "twdyn"],
}
# how many arms this experiment budgets per mnemonic
BUDGET = {"tex_sample": 10, "tex_deriv": 6, "tex_write": 12}


def plausible(m, hexs):
    b = bytes.fromhex(hexs)
    if m == "tex_write":
        return len(b) == 16 and 0x88 <= b[12] <= 0x8F
    if m == "tex_sample":
        return len(b) == 14 and b[12] in (1, 2, 3)
    if m == "tex_deriv":
        return len(b) == 10 and b[6] in (0x90, 0x92)
    return True


def main():
    cen = json.load(open(CENSUS))
    arms = []
    for m, fields in sorted(CA.TARGETS.items()):
        pool = []
        for name in SERVES[m]:
            ent = cen["carriers"].get(name, {})
            st = ent.get("stages", {}).get("fragment", {})
            via = (st.get("located_via") or {}).get(m, "?")
            for k, o in enumerate((st.get("occurrences") or {}).get(m, [])):
                if not plausible(m, o["hex"]):
                    continue
                pool.append(dict(carrier=name, occ=k, off=o["off"], hex=o["hex"],
                                 fields=o["fields"], via=via))
        key = fields[0]
        per_carrier, chosen, seen_car, seen_val = {}, [], set(), set()

        def take(p):
            per_carrier[p["carrier"]] = per_carrier.get(p["carrier"], 0) + 1
            seen_car.add(p["carrier"])
            seen_val.add(p["fields"].get(key))
            chosen.append(p)

        for p in pool:                      # rule 3: one arm per CARRIER
            if p["carrier"] not in seen_car:
                take(p)
        for p in pool:                      # rule 4: unrepresented baseline values
            if len(chosen) >= BUDGET[m]:
                break
            if p in chosen or p["fields"].get(key) in seen_val:
                continue
            if per_carrier.get(p["carrier"], 0) >= CAP:
                continue
            take(p)
        seen_pair = {(p["carrier"], p["fields"].get(key)) for p in chosen}
        for p in pool:                      # rule 4b: (carrier, value) pairs
            if len(chosen) >= BUDGET[m]:
                break
            pair = (p["carrier"], p["fields"].get(key))
            if p in chosen or pair in seen_pair:
                continue
            if per_carrier.get(p["carrier"], 0) >= CAP:
                continue
            seen_pair.add(pair)
            take(p)
        # rule 5: ROUND-ROBIN fill over carriers
        rest = {}
        for p in pool:
            if p not in chosen:
                rest.setdefault(p["carrier"], []).append(p)
        order = [c for c in SERVES[m] if c in rest]
        while len(chosen) < BUDGET[m] and order:
            nxt = []
            for c in order:
                if len(chosen) >= BUDGET[m]:
                    break
                if per_carrier.get(c, 0) >= CAP or not rest[c]:
                    continue
                take(rest[c].pop(0))
                if rest[c] and per_carrier.get(c, 0) < CAP:
                    nxt.append(c)
            order = nxt
        for p in chosen:
            arms.append({
                "id": f"{m}@{p['carrier']}/{p['occ']}",
                "mnemonic": m, "carrier": p["carrier"], "stage": "fragment",
                "occ": p["occ"], "fields": list(fields),
                "expect_off": p["off"], "expect_hex": p["hex"],
                "baseline_fields": {f: p["fields"].get(f) for f in fields},
                "located_via": p["via"],
                "why": CA.CARRIERS[p["carrier"]]["why"],
            })
    out = os.path.join(HERE, "harness", "arms.py")
    with open(out, "w") as f:
        f.write('#!/usr/bin/env python3\n'
                '"""arms.py -- FROZEN arm list, GENERATED by analysis/gen_arms.py\n'
                'from raw/prefreeze/census_run2.json under the selection rule in\n'
                'that file.  run.py asserts every arm\'s bytes and offset are still\n'
                'exactly these before it sweeps, and refuses the arm otherwise.\n'
                'Do not hand-edit."""\n\n')
        f.write("ARMS = " + json.dumps(arms, indent=1, sort_keys=True) + "\n")
    print(f"wrote {out}: {len(arms)} arms")
    for a in arms:
        print(f"  {a['id']:32s} base={a['baseline_fields']} via={a['located_via']}")


if __name__ == "__main__":
    main()
