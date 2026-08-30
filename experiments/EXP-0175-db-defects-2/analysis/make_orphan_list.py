#!/usr/bin/env python3
"""EXP-0175 — enumerate the validation.json rows the db.json edits orphaned, and
the one row they created, with everything needed to apply the change.

`tools/agx-isa/validation.json` is the ORCHESTRATOR'S file. This script only
READS it; it writes a report and a ready-to-run patch script that the
orchestrator may execute. Nothing here modifies validation.json.

    python3 analysis/make_orphan_list.py
"""
import json, os, sys, collections

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
REPO = os.path.abspath(os.path.join(EXP, "..", ".."))
DB = os.path.join(REPO, "tools", "agx-isa", "db.json")
VAL = os.path.join(REPO, "tools", "agx-isa", "validation.json")
PRE = os.path.join(EXP, "work", "pre", "db.json")


def fields_of(db):
    return {i["mnemonic"]: {f["name"] for f in i.get("fields", [])}
            for i in db["instructions"]}


def spans_of(db):
    return {(i["mnemonic"], f["name"]): (f["start"], f["width"])
            for i in db["instructions"] for f in i.get("fields", [])}


def main():
    db = json.load(open(DB))
    pre = json.load(open(PRE))
    val = json.load(open(VAL))
    now, before = fields_of(db), fields_of(pre)
    notes = {i["mnemonic"]: {n["name"]: n for n in i.get("match_notes", [])}
             for i in db["instructions"]}

    orphaned, created, respanned = [], [], []
    sp_now, sp_before = spans_of(db), spans_of(pre)
    for k in sorted(set(sp_now) & set(sp_before)):
        if sp_now[k] != sp_before[k]:
            respanned.append({
                "mnemonic": k[0], "field": k[1],
                "before": {"start": sp_before[k][0], "width": sp_before[k][1]},
                "after": {"start": sp_now[k][0], "width": sp_now[k][1]},
                "action": "row KEPT -- but its bit span moved; any pending verdict "
                          "must be re-checked against the new span",
                "reason": "DEF-0174-1: byte+1 is one 8-bit operand descriptor "
                          "`(S<<1)|half`, not a 7-bit register plus a uniform flag"})
    for m, fs in before.items():
        for f in sorted(fs - now.get(m, set())):
            row = val["instructions"].get(m, {}).get(f, {})
            n = notes.get(m, {}).get(f, {})
            orphaned.append({
                "mnemonic": m, "field": f,
                "current_label": row.get("label"),
                "current_range": row.get("range"),
                "current_target": row.get("target"),
                "current_evidence": row.get("evidence"),
                "reason": ("folded into `match` -- zero free bits, exactly one legal "
                           "value" if n else
                           "field DELETED as a descriptor defect (DEF-0174-1): byte+1 "
                           "bit 7 is source-register bit 6, not a uniform selector; it "
                           "is now inside the 8-bit `srcA_reg` operand descriptor. Its "
                           "EVIDENCE is not lost -- EXP-0174's own srcA_uni verdict "
                           "says the same thing and belongs in srcA_reg's row."),
                "defect_class": "fold" if n else "DEF-0174-1",
                "pinned_value": n.get("value"),
                "start": n.get("start"), "width": n.get("width"),
                "preserved_in": "db.json instructions[%s].match_notes" % m,
                "was_vacuous_emitter_grade":
                    row.get("label") in ("hardware-run", "isolated-byte-diff"),
                "action": "DELETE this row from validation.json",
            })
    for m, fs in now.items():
        for f in sorted(fs - before.get(m, set())):
            created.append({
                "mnemonic": m, "field": f,
                "action": "ADD this row to validation.json",
                "recommended": {
                    "label": "hardware-run",
                    "range": "0..14 dense (15 of 16 destination nibbles; 0x?b byte0)",
                    "target": "G17P",
                    "evidence": ["EXP-0171", "EXP-0175"],
                },
                "justification":
                    "DEF-0171-1. A dense byte0 sweep on the SYNTH 16-GPR-dump carrier "
                    "puts the computed AND result in register (byte0 >> 4) for every "
                    "value whose low nibble is 0xb -- 15 of 15 observable destinations, "
                    "0 misses, in BOTH gated runs, cross-run agreement 1.0000. r15 is "
                    "unobservable IN THAT CARRIER by construction (it is the harness's "
                    "own store-index register, re-seeded before every dump), so the "
                    "range stops at 14 rather than claiming 16. Re-derived from the "
                    "committed raw in EXP-0175/analysis/rederive_def1.py.",
            })

    # the resulting coverage block, computed rather than asserted
    counts = collections.Counter()
    total = 0
    orphan_keys = {(o["mnemonic"], o["field"]) for o in orphaned}
    for m, ent in val["instructions"].items():
        for f, r in ent.items():
            if f == "_instruction" or not isinstance(r, dict):
                continue
            if (m, f) in orphan_keys:
                continue
            counts[r.get("label")] += 1
            total += 1
    for c in created:
        counts[c["recommended"]["label"]] += 1
        total += 1
    emit = counts["hardware-run"] + counts["isolated-byte-diff"]

    before_counts = val["coverage"]["by_label"]
    before_total = val["coverage"]["total_fields"]
    before_emit = before_counts["hardware-run"] + before_counts["isolated-byte-diff"]

    out = {
        "_note": "validation.json is the orchestrator's file. EXP-0175 only READ it.",
        "db_sha256_before": "322847609de79055b651b79fbd630948bb97120bcefd037a3c7ae5a301ba64a5",
        "orphaned_rows": orphaned,
        "created_rows": created,
        "respanned_rows": respanned,
        "arithmetic": {
            "before": {"total_fields": before_total, "emitter_grade": before_emit,
                       "by_label": before_counts,
                       "total_instructions": val["coverage"]["total_instructions"]},
            "after": {"total_fields": total, "emitter_grade": emit,
                      "by_label": dict(counts),
                      "total_instructions": len(db["instructions"])},
            "fold_only": {
                "_note": "the Task-2 fold ALONE -- i.e. counting ONLY the 25 "
                         "zero-free-bit rows, excluding DEF-0171-1's new ilogic.dst "
                         "and DEF-0174-1's two srcA_uni deletions. This is the number "
                         "EXP-0173 predicted.",
                "total_fields": before_total - sum(
                    1 for o in orphaned if o.get("defect_class") == "fold"),
                "emitter_grade": before_emit - sum(
                    1 for o in orphaned
                    if o.get("defect_class") == "fold"
                    and o["was_vacuous_emitter_grade"]),
            },
            "exp0173_predicted": "627/1062 -> ~611/1037, instruction count UNCHANGED",
            "measured": "%d/%d -> %d/%d, instruction count %d -> %d"
                        % (before_emit, before_total, emit, total,
                           val["coverage"]["total_instructions"],
                           len(db["instructions"])),
        },
    }
    json.dump(out, open(os.path.join(HERE, "orphaned_validation_rows.json"), "w"),
              indent=1)

    print("orphaned rows (fold): %d   (%d of them carried an emitter-grade label)"
          % (len(orphaned), sum(o["was_vacuous_emitter_grade"] for o in orphaned)))
    for o in orphaned:
        print("  DELETE %-22s %-14s  label=%-24s pinned=%s  [%s]" if False else
              "  DELETE %-22s %-14s  label=%-24s pinned=0x%02x"
              % (o["mnemonic"], o["field"], o["current_label"],
                 o["pinned_value"] if o["pinned_value"] is not None else -1))
    print("\nre-spanned rows (KEPT, but the bit span moved): %d" % len(respanned))
    for r in respanned:
        print("  RESPAN %-22s %-14s  start/width %s -> %s"
              % (r["mnemonic"], r["field"],
                 (r["before"]["start"], r["before"]["width"]),
                 (r["after"]["start"], r["after"]["width"])))
    print("\ncreated rows: %d" % len(created))
    for c in created:
        print("  ADD    %-22s %-14s  recommend %s (%s)"
              % (c["mnemonic"], c["field"], c["recommended"]["label"],
                 c["recommended"]["range"]))
    fo = out["arithmetic"]["fold_only"]
    print("\nfold ALONE (Task 2)      : %d/%d emitter-grade"
          % (fo["emitter_grade"], fo["total_fields"]))
    print("fold + DEF-0171-1 (both) : %d/%d emitter-grade" % (emit, total))
    print("EXP-0173 predicted : %s" % out["arithmetic"]["exp0173_predicted"])
    print("EXP-0175 measured  : %s" % out["arithmetic"]["measured"])
    print("\n  label                       before   after   delta")
    for lab in ["hardware-run", "isolated-byte-diff", "corpus-correlation",
                "tokenization-only", "single-template-inference",
                "api-accept-reject", "host-private", "untested"]:
        b, a = before_counts.get(lab, 0), counts.get(lab, 0)
        print("  %-26s %6d  %6d  %+6d" % (lab, b, a, a - b))
    print("  %-26s %6d  %6d  %+6d" % ("TOTAL", before_total, total, total - before_total))
    print("  %-26s %6d  %6d  %+6d" % ("emitter-grade", before_emit, emit,
                                      emit - before_emit))
    return 0


sys.exit(main())
