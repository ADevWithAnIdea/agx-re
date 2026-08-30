#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0164 step 3 -- regenerate every table quoted in RESULTS.md from audit.json.

Usage:  python3 analysis/tables.py            # all tables to stdout
"""
import collections, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
A = json.load(open(os.path.join(HERE, "audit.json")))
F, META = A["fields"], A["_meta"]
COV = json.load(open(os.path.join(HERE, "experiment_coverage.json")))
EMIT = json.load(open(os.path.join(HERE, "emittability.json")))
REC = json.load(open(os.path.join(HERE, "reclassify.json")))
BUCKETS = ["STABLE-LIVE", "INERT-MULTI", "INERT-SINGLE", "UNSTABLE",
           "SINGLE-RUN", "UNVERIFIABLE"]


def esc(x):
    """Arm names contain `|` (the carrier|arm pair key); escape it for markdown."""
    return str(x).replace("|", "\\|")


def t1():
    print("### T1 — bucket census (664 emitter-grade fields)\n")
    print("| bucket | fields | share |")
    print("|---|---:|---:|")
    b = META["summary"]["buckets"]
    for k in BUCKETS:
        print("| `%s` | %d | %.1f%% |" % (k, b.get(k, 0), 100.0 * b.get(k, 0) / len(F)))
    print("| **total** | **%d** | |" % len(F))
    print("\n`UNVERIFIABLE` by reason: " +
          ", ".join("`%s` %d" % (k, v) for k, v in
                    sorted(META["summary"]["unverifiable_reasons"].items())))


def t2():
    print("\n### T2 — per cited experiment\n")
    tab = collections.defaultdict(collections.Counter)
    for r in F.values():
        for e in r["evidence"]:
            tab[e][r["bucket"]] += 1
    print("| experiment | cited by | STABLE | I-MULTI | I-SINGLE | UNSTABLE | 1-RUN | UNVER | raw verdict |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---|")
    for e in sorted(tab, key=lambda x: -sum(tab[x].values())):
        t = tab[e]
        if sum(t.values()) < 3:
            continue
        print("| `%s` | %d | %d | %d | %d | %d | %d | %d | %s |" %
              (e, sum(t.values()), t["STABLE-LIVE"], t["INERT-MULTI"], t["INERT-SINGLE"],
               t["UNSTABLE"], t["SINGLE-RUN"], t["UNVERIFIABLE"],
               COV[e]["parse_verdict"]))


def t3():
    print("\n### T3 — emittability ladder (denominator 166 emitter-relevant descriptors)\n")
    print("| withholding policy | fields withheld | emittable | of 166 |")
    print("|---|---:|---:|---:|")
    print("| published `validation.json` | 0 | %d | %.1f%% |"
          % (EMIT["published"]["n"], 100.0 * EMIT["published"]["n"] / 166))
    order = ["inert_single_only", "inert_single_plus_unstable", "chain_broken_only",
             "lenient", "strict"]
    for k in order:
        v = EMIT["variants"][k]
        print("| `%s` | %d | %d | %.1f%% |"
              % (k, v["n_fields_withheld"], v["emittable"], 100.0 * v["emittable"] / 166))


def t4():
    print("\n### T4 — instructions that lose emittable status under the strict set\n")
    d = REC["why_each_instruction_is_lost"]
    rows = []
    for m, fs in d.items():
        bc = collections.Counter(f["bucket"] for f in fs)
        ev = sorted({e for f in fs for e in f["evidence"]})
        rows.append((len(fs), m, bc, ev))
    rows.sort(key=lambda x: (x[0], x[1]))
    print("| instruction | withheld fields | buckets | citing experiments |")
    print("|---|---:|---|---|")
    for n, m, bc, ev in rows:
        print("| `%s` | %d | %s | %s |" %
              (m, n, ", ".join("%s %d" % (k, v) for k, v in sorted(bc.items())),
               ", ".join("`%s`" % e for e in ev)))


def t5():
    print("\n### T5 — field NAMES that block the most instructions\n")
    print("| field name | instructions blocked | instructions |")
    print("|---|---:|---|")
    for x in REC["load_bearing_field_names"]:
        if x["n_instructions_blocked"] < 2:
            continue
        print("| `%s` | %d | %s |" % (x["field_name"], x["n_instructions_blocked"],
                                      ", ".join("`%s`" % i for i in x["instructions"])))


def t6():
    print("\n### T6 — representative-arm defect (H2): inert arm + stable-live arm, same raw\n")
    m = json.load(open(os.path.join(HERE, "mixed_arm_liveness.json")))
    print("| field | experiment | inert arm(s) (values swept) | stable-live arm(s) (moved) |")
    print("|---|---|---|---|")
    for k in sorted(m):
        for e in m[k]:
            print("| `%s` | `%s` | %s | %s |" %
                  (k, e["experiment"],
                   ", ".join("`%s` (%d)" % (esc(a), e["inert_values_swept"][a])
                             for a in e["inert_arms"]),
                   ", ".join("`%s` (%d)" % (esc(a), e["live_moved"][a])
                             for a in e["stable_live_arms"])))


def t7():
    print("\n### T7 — the INERT-SINGLE list (the suspect class)\n")
    rows = [(k, r) for k, r in F.items() if r["bucket"] == "INERT-SINGLE"]
    rows.sort()
    print("| field | values swept | arm | runs | evidence |")
    print("|---|---:|---|---:|---|")
    for k, r in rows:
        arm = r["arms_tested"][0] if r["arms_tested"] else "-"
        nr = max((v["n_gated_runs"] for ex in r["per_experiment"].values()
                  for v in ex.values()), default=0)
        print("| `%s` | %d | `%s` | %d | %s |" %
              (k, r["max_values_dispatched"], esc(arm), nr,
               ", ".join("`%s`" % e for e in r["evidence"])))


if __name__ == "__main__":
    which = sys.argv[1:] or ["1", "2", "3", "4", "5", "6", "7"]
    for w in which:
        globals()["t" + w]()
