#!/usr/bin/env python3
"""EXP-0183 -- SIMULATE applying analysis/validation_updates.json, without writing
tools/agx-isa/validation.json (which the orchestrator owns).

Produces work/validation_simulated.json and reports which instructions cross the
emittability line, using merge_verdicts.py's own rule. Answers the dispatch's question:
"which of the 22 one-field-away instructions do these changes unblock, and which stay
blocked and why."

  python3 analysis/simulate_merge.py
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
REPO = os.path.abspath(os.path.join(EXP, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "work"))

DB = json.load(open(os.path.join(REPO, "tools", "agx-isa", "db.json")))
VAL = json.load(open(os.path.join(REPO, "tools", "agx-isa", "validation.json")))
UPD = json.load(open(os.path.join(HERE, "validation_updates.json")))["updates"]
EMIT_OK = {"hardware-run", "isolated-byte-diff"}
KEEP = ("label", "range", "target", "evidence", "note", "values_dispatched",
        "distinct_bytes", "encodable_range", "start", "width")


def emittable(val):
    dbf = {i["mnemonic"]: [f["name"] for f in i.get("fields", [])] for i in DB["instructions"]}
    out, why = [], {}
    for i in DB["instructions"]:
        m = i["mnemonic"]
        names = dbf[m]
        e = val["instructions"].get(m, {})
        missing = [n for n in names if n not in e]
        weak = [(n, e[n]["label"]) for n in names if n in e and e[n]["label"] not in EMIT_OK]
        inst = e.get("_instruction") or {}
        veto = "EMITTABLE VETO" in (inst.get("note") or "")
        instr_weak = inst.get("label") not in EMIT_OK
        ok = bool(names) and not missing and not weak and not veto and not instr_weak
        if ok:
            out.append(m)
        else:
            why[m] = {"missing_rows": missing, "fields_below_bar": weak,
                      "descriptor_veto": veto,
                      "descriptor_label": inst.get("label") if instr_weak else None}
    return sorted(out), why


before, why_before = emittable(VAL)

after = json.loads(json.dumps(VAL))
for m, spec in UPD.items():
    for kind in ("replace", "create"):
        for f, r in spec[kind].items():
            after["instructions"][m][f] = {k: r[k] for k in KEEP if k in r}
    for f in spec["delete"]:
        after["instructions"][m].pop(f, None)
after_l, why_after = emittable(after)

os.makedirs(os.path.join(EXP, "work"), exist_ok=True)
json.dump(after, open(os.path.join(EXP, "work", "validation_simulated.json"), "w"), indent=1)

gained = [m for m in after_l if m not in before]
lost = [m for m in before if m not in after_l]
lab = {}
for m, e in after["instructions"].items():
    for f, r in e.items():
        if f != "_instruction":
            lab[r["label"]] = lab.get(r["label"], 0) + 1
grade = sum(lab.get(k, 0) for k in EMIT_OK)

print("emittable BEFORE: %d   AFTER: %d" % (len(before), len(after_l)))
print("  GAINED:", gained or "(none)")
print("  LOST:  ", lost or "(none)")
print("emitter-grade field rows AFTER (all descriptors):", grade)
worklist = ["copysign", "cubearray_coord_const", "cvt_f2i", "dev_scoreboard_fence",
            "falu2_uni", "frag_color_store", "half_alu", "half_alu_fma12", "iadd2",
            "if_push", "imageblock_store", "iter", "iter_at", "mesh_out_src",
            "n4_cf_word", "n4_rt_word", "reg_move_cb", "ret", "rt_query_traverse",
            "simd_ballot", "simd_shuffle", "vtx_out_pos"]
print("\nthe 22 ONE-FIELD-AWAY instructions:")
for m in worklist:
    st = "EMITTABLE" if m in after_l else "blocked"
    extra = ""
    if m not in after_l:
        w = why_after.get(m, {})
        extra = "  missing=%s below_bar=%s veto=%s descr_label=%s" % (
            w.get("missing_rows"), w.get("fields_below_bar"), w.get("descriptor_veto"),
            w.get("descriptor_label"))
    print("  %-24s %-10s%s" % (m, st, extra))
json.dump({"before": before, "after": after_l, "gained": gained, "lost": lost,
           "why_after": why_after, "emitter_grade_rows": grade,
           "labels": lab},
          open(os.path.join(HERE, "emittability_simulation.json"), "w"), indent=1)
