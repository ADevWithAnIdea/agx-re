#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0170 Arm A -- recompute, from the pinned db.json alone, which fields overlap
their OWN descriptor's `match` constants and how many encodings of each the OLD
(OR-only) isadb.assemble() could reach.

Closed form, justified in PRE_REGISTRATION.md 3:

    old assemble()  ->  word = match | OR_f (val_f << start_f)
    a supplied value v for field f therefore landed as  v | (M_f >> start_f)
    where M_f = the match bits inside f's span.
    |{ v | m : v in [0, 2^w) }| = 2^(w - popcount(m))

so  reachable_old = 2^(w - popcount(M_f))  and  reachable_fraction = 2^-popcount(M_f).

Also scans field<->field span overlaps inside one descriptor, which the same OR
collapsed whenever the other field's held value was non-zero.

READ-ONLY.  Writes only analysis/static_overlap.json.
Usage: python3 analysis/static_overlap.py
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.abspath(os.path.join(HERE, ".."))
DB = os.path.join(EXP, "work", "db.snapshot.json")

# The six rows EXP-0166 tabulated; H2's falsifier F2 checks the closed form against them.
H2_EXPECT = {
    ("iter", "grp"): 8,
    ("iter_at", "grp"): 8,
    ("tex_sample", "kind"): 4,
    ("pack_convert", "fmt_class"): 16,
    ("irotate", "b2"): 32,
    ("shift_amt_move", "kind"): 64,
}


def popcount(x):
    return bin(x).count("1")


def main():
    db = json.load(open(DB))
    rows = []
    ff_rows = []
    n_instr = 0
    for ins in db["instructions"]:
        n_instr += 1
        m = ins["mnemonic"]
        matchmask = 0
        for (ms, mw, mv) in (ins.get("match") or []):
            matchmask |= (mv & ((1 << mw) - 1)) << ms
        flds = [(f["name"], f["start"], f["width"]) for f in ins.get("fields", [])]
        for (name, s, w) in flds:
            span = ((1 << w) - 1) << s
            Mf = matchmask & span
            p = popcount(Mf)
            rows.append({
                "mnemonic": m, "field": name, "start": s, "width": w,
                "match_bits_in_span": Mf >> s,
                "match_bits_in_span_hex": hex(Mf >> s),
                "popcount": p,
                "overlap": bool(Mf),
                "reachable_old": 1 << (w - p),
                "encodable": 1 << w,
                "reachable_fraction_old": 1.0 / (1 << p),
            })
        # field <-> field overlaps within the same descriptor (secondary)
        for i in range(len(flds)):
            for j in range(i + 1, len(flds)):
                n1, s1, w1 = flds[i]
                n2, s2, w2 = flds[j]
                a = ((1 << w1) - 1) << s1
                b = ((1 << w2) - 1) << s2
                if a & b:
                    ff_rows.append({"mnemonic": m, "a": n1, "b": n2,
                                    "shared_bits": popcount(a & b),
                                    "shared_mask_hex": hex(a & b)})

    ov = [r for r in rows if r["overlap"]]
    # H2 / F2
    h2 = {}
    for (mn, fn), want in H2_EXPECT.items():
        got = next((r["reachable_old"] for r in rows
                    if r["mnemonic"] == mn and r["field"] == fn), None)
        h2["%s.%s" % (mn, fn)] = {"expected_by_EXP-0166": want, "computed": got,
                                  "agree": got == want}
    out = {
        "_meta": {
            "generated_by": "EXP-0170/analysis/static_overlap.py",
            "db_snapshot": "work/db.snapshot.json",
            "closed_form": "reachable_old = 2^(width - popcount(match & span))",
        },
        "totals": {
            "instructions": n_instr,
            "fields": len(rows),
            "fields_overlapping_own_match": len(ov),
            "instructions_with_an_overlapping_field": len({r["mnemonic"] for r in ov}),
            "fields_fully_pinned_by_match": len([r for r in ov if r["reachable_old"] == 1]),
            "field_field_overlaps": len(ff_rows),
        },
        "by_reachable_fraction": {},
        "H1_expected_53": len(ov) == 53,
        "H2_closed_form_check": h2,
        "H2_all_agree": all(v["agree"] for v in h2.values()),
        "overlapping_fields": sorted(ov, key=lambda r: (r["reachable_fraction_old"],
                                                        r["mnemonic"], r["field"])),
        "field_field_overlaps": ff_rows,
    }
    hist = {}
    for r in ov:
        k = "1/%d" % (1 << r["popcount"])
        hist[k] = hist.get(k, 0) + 1
    out["by_reachable_fraction"] = dict(sorted(hist.items(),
                                               key=lambda kv: int(kv[0].split("/")[1])))
    json.dump(out, open(os.path.join(HERE, "static_overlap.json"), "w"),
              indent=1, sort_keys=False)
    print("instructions: %d   fields: %d" % (n_instr, len(rows)))
    print("fields overlapping own match: %d   (EXP-0166 said 53 -> H1 %s)"
          % (len(ov), "CONFIRMED" if len(ov) == 53 else "REFUTED"))
    print("distinct instructions affected: %d" % out["totals"]["instructions_with_an_overlapping_field"])
    print("fields with only ONE reachable encoding: %d" % out["totals"]["fields_fully_pinned_by_match"])
    print("reachable-fraction histogram:", out["by_reachable_fraction"])
    print("H2 closed-form check vs EXP-0166's six rows:",
          "ALL AGREE" if out["H2_all_agree"] else "DISAGREE")
    for k, v in h2.items():
        print("   %-28s expected %4s  computed %4s  %s"
              % (k, v["expected_by_EXP-0166"], v["computed"], "ok" if v["agree"] else "MISMATCH"))
    print("field<->field span overlaps in the same descriptor: %d" % len(ff_rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
