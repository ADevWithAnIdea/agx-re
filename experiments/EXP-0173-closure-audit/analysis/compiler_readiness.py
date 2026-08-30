#!/usr/bin/env python3
"""EXP-0173: what can a compiler engineer with NO hardware emit today, and what
is the first thing that stops them?

docs/compiler-readiness.md's standing headline is "the first thing that stops a
general back end is nir_op_mov -- there is no validated GPR-to-GPR move". That
predates today's withdrawals. This re-tests it against the CURRENT
validation.json rather than restating it.

Method: for each candidate instruction that could implement a GPR-to-GPR move,
report every field's label, and say whether the instruction is emittable AND
whether a generated program containing it has ever run.

    python3 experiments/EXP-0173-closure-audit/analysis/compiler_readiness.py
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(EXP))
ISA = os.path.join(ROOT, "tools", "agx-isa")
E167 = os.path.join(ROOT, "experiments", "EXP-0167-g17p-synthesis-reconfirm")
EMIT = {"hardware-run", "isolated-byte-diff"}

# every descriptor in db.json whose committed semantics describe moving a value
# between registers. Collected by scanning the semantics text, not hand-listed.
MOVE_WORDS = ("register move", "gpr", "move", "mov/zero-extend", "copy")

# the minimum a back end needs before it can lower anything at all
NIR_NEEDS = [
    ("nir_op_mov (GPR->GPR)", "a plain register-to-register copy: phi lowering, "
     "parallel copy, RA coalescing, spill reload all bottom out here"),
    ("nir_op_fadd / fmul (2-src float)", "falu2 family"),
    ("nir_op_iadd (2-src int)", "iadd2 family"),
    ("nir_load_global / store_global", "device_load / device_store"),
    ("control flow (if/loop)", "icmp_pred + if_push + jump_cond + pop_reconverge"),
]


def main():
    db = json.load(open(os.path.join(ISA, "db.json")))
    val = json.load(open(os.path.join(ISA, "validation.json")))
    ledger = json.load(open(os.path.join(E167, "analysis",
                                         "assemble_defect_check.json")))
    emittable = set(val["coverage"]["emittable_mnemonics"])
    generated = set(ledger["mnemonics_used"])

    cands = []
    for i in db["instructions"]:
        sem = (i.get("semantics") or i.get("desc") or "").lower()
        if not any(w in sem for w in MOVE_WORDS):
            continue
        entry = val["instructions"].get(i["mnemonic"], {})
        fields = []
        for f in i.get("fields", []):
            lab = entry.get(f["name"], {}).get("label", "MISSING")
            fields.append({"name": f["name"], "label": lab, "emitter_grade": lab in EMIT})
        blocking = [f["name"] + " (" + f["label"] + ")" for f in fields
                    if not f["emitter_grade"]]
        cands.append({
            "mnemonic": i["mnemonic"], "length": i.get("length"),
            "semantics_head": (i.get("semantics") or i.get("desc") or "")[:180],
            "emittable": i["mnemonic"] in emittable,
            "ever_generated_and_run": i["mnemonic"] in generated,
            "n_fields": len(fields), "blocking_fields": blocking,
            "fields": fields})

    # the specific claim under test
    true_moves = [c for c in cands
                  if c["mnemonic"] in ("n3_mov", "reg_move_c0", "reg_move_cb",
                                       "reg_move_c2var", "uniform_mov", "shift_amt_move",
                                       "mov_zext16", "n2_op6", "ray_move")]
    emittable_moves = [c for c in true_moves if c["emittable"]]
    # A candidate only counts as a usable GPR->GPR move if its own committed
    # semantics describe moving one register to a DIFFERENT register AND the
    # descriptor does not say the operand maps are unresolved.
    def usable(c):
        d = next((x for x in db["instructions"] if x["mnemonic"] == c["mnemonic"]), {})
        blob = ((d.get("semantics") or "") + " " + (d.get("provenance") or "")).lower()
        if "in place" in blob or "both source and destination" in blob:
            return False, "operates IN PLACE on one register — cannot express a copy"
        if "uniform" in c["mnemonic"]:
            return False, "reads the uniform file, not a GPR"
        for w in ("needs-splice", "needs splice", "not hw-dispatch validated",
                  "value maps are mixed", "catch-all"):
            if w in blob:
                return False, ("descriptor's own text says the operand value maps are "
                               "unresolved (%r), so no rule exists for WHICH value moves "
                               "which register" % w)
        return True, ""
    gpr_to_gpr_emittable = []
    rejected = []
    for c in emittable_moves:
        ok, why = usable(c)
        (gpr_to_gpr_emittable if ok else rejected).append(dict(c, rejection=why))

    out = {"_meta": {
        "experiment": "EXP-0173",
        "claim_under_test": "docs/compiler-readiness.md: the first blocker is nir_op_mov, "
                            "because there is no validated GPR-to-GPR move",
        "verdict": None, "move_candidates": len(cands),
        "emittable_move_candidates": [c["mnemonic"] for c in emittable_moves],
        "emittable_move_candidates_REJECTED": [
            {"mnemonic": c["mnemonic"], "why": c["rejection"]} for c in rejected],
        "generated_and_run": sorted(generated),
        "emittable_total": len(emittable),
    }, "nir_minimum": NIR_NEEDS, "move_candidates": cands}

    # ---- the emittability rule ignores the _instruction label ---------------
    # validate_labels.py / merge_verdicts.py decide "emittable" from the FIELD
    # labels plus the EMITTABLE VETO note. They never consult `_instruction`,
    # which is where the instruction's own identity/semantics evidence lives.
    WARN = ("needs-splice", "needs splice", "not hw", "compile-only", "unresolved",
            "catch-all", "unknown")
    weak = []
    for m in sorted(emittable):
        inst = (val["instructions"][m].get("_instruction") or {})
        lab = inst.get("label")
        d = next((x for x in db["instructions"] if x["mnemonic"] == m), {})
        blob = ((d.get("semantics") or "") + " " + (d.get("provenance") or "")).lower()
        hits = sorted({w for w in WARN if w in blob})
        if lab not in EMIT or hits:
            weak.append({"mnemonic": m, "_instruction_label": lab,
                         "instruction_label_is_emitter_grade": lab in EMIT,
                         "descriptor_self_warnings": hits})
    out["emittability_rule_defect"] = {
        "defect": "the emittable rule reads only FIELD labels; it never reads the "
                  "`_instruction` label, so an instruction whose own identity/semantics "
                  "evidence is weaker than emitter-grade still counts as emittable",
        "emittable_with_non_emitter_grade_instruction_label":
            sorted(w["mnemonic"] for w in weak if not w["instruction_label_is_emitter_grade"]),
        "count": sum(1 for w in weak if not w["instruction_label_is_emitter_grade"]),
        "of_which_tokenization_only":
            sorted(w["mnemonic"] for w in weak
                   if w["_instruction_label"] == "tokenization-only"),
        "emittable_whose_own_descriptor_text_warns":
            sorted(w["mnemonic"] for w in weak if w["descriptor_self_warnings"]),
        "rows": weak,
    }

    # decide
    if not gpr_to_gpr_emittable:
        out["_meta"]["verdict"] = (
            "CLAIM STILL HOLDS. No descriptor that moves one GPR to a DIFFERENT GPR is "
            "emittable. `mov_zext16` is emittable but its own committed semantics say it "
            "operates IN PLACE on ONE register used as both source and destination, so it "
            "cannot implement a copy. `uniform_mov` reads the uniform file, not a GPR, and is "
            "not emittable anyway. `n3_mov` is the real candidate and is blocked.")
    else:
        out["_meta"]["verdict"] = ("CLAIM REFUTED — these are emittable GPR->GPR moves: "
                                   + ", ".join(c["mnemonic"] for c in gpr_to_gpr_emittable))
    p = os.path.join(HERE, "compiler_readiness.json")
    json.dump(out, open(p, "w"), indent=1)
    print(json.dumps(out["_meta"], indent=1))
    print("\n%-20s %-6s %-6s %-4s %s" % ("mnemonic", "emit?", "ran?", "flds", "blocking fields"))
    for c in sorted(true_moves, key=lambda c: c["mnemonic"]):
        print("%-20s %-6s %-6s %-4d %s" % (
            c["mnemonic"], "YES" if c["emittable"] else "-",
            "YES" if c["ever_generated_and_run"] else "-",
            c["n_fields"], ", ".join(c["blocking_fields"]) or "(none)"))
    print("\nwrote", p)


if __name__ == "__main__":
    sys.exit(main())
