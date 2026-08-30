#!/usr/bin/env python3
"""EXP-0173: per emittable instruction, can an implementer generate an encoding
from documented rules alone -- and if not, which donor does it need?

This is the heart of the acceptance gate. `CLAUDE.md` requires proof that "no
required field or supported operation depends on captured Apple templates".

Three populations are compared, and they are NOT the same population:

  E  EMITTABLE      validation.json's 35 mnemonics: every field labelled
                    hardware-run or isolated-byte-diff. This is a LABEL
                    property. It says the fields were measured; it does NOT say
                    anybody ever built a whole instruction and ran it.
  G  GENERATED      mnemonics that actually appear in EXP-0167's generator
                    ledger, i.e. instructions assembled from rules with ZERO
                    copied tokens and executed against a host oracle on G17P.
                    Source: EXP-0167 analysis/assemble_defect_check.json.
  D  DONOR-BOUND    families EXP-0167 records as still needing a captured
                    donor: the 12 CF cases and the 12 immediate-mode iadd2.

Per-mnemonic verdict:

  GENERATED-AND-EMITTABLE  in E and G: measured fields AND a program built from
                           rules ran correctly. The strongest state.
  GENERATED-NOT-EMITTABLE  in G but not E: a generated program ran correctly,
                           yet some field is still unlabelled. Under-counted.
  EMITTABLE-NOT-GENERATED  in E but not G: every field is labelled, but no
                           generated program of this instruction has ever run.
                           Rule 1 ("generated, not merely decoded") is NOT
                           established for it by EXP-0167.
  DONOR-DEPENDENT          in D: cannot be built without a captured template.

    python3 experiments/EXP-0173-closure-audit/analysis/template_dependency.py
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(EXP))
ISA = os.path.join(ROOT, "tools", "agx-isa")
E167 = os.path.join(ROOT, "experiments", "EXP-0167-g17p-synthesis-reconfirm")
EMIT = {"hardware-run", "isolated-byte-diff"}

# Donor dependency is read from EXP-0167's OWN machine-readable ledger, not
# restated by hand: analysis/summary.json donor_tokens_still_required is the
# exact (mnemonic.field -> number of cases) map of tokens still lifted verbatim.
SUMMARY = os.path.join(E167, "analysis", "summary.json")
RESULTS_JSONL = os.path.join(E167, "raw", "g17p-20260830-iso01", "01_results.jsonl")


def main():
    db = json.load(open(os.path.join(ISA, "db.json")))
    val = json.load(open(os.path.join(ISA, "validation.json")))
    ledger = json.load(open(os.path.join(E167, "analysis", "assemble_defect_check.json")))
    summ = json.load(open(SUMMARY))
    donor_tokens = summ["donor_tokens_still_required"]
    donor_fields = {}
    for k, ncases in donor_tokens.items():
        mn, fn = k.split(".", 1)
        donor_fields.setdefault(mn, {})[fn] = ncases
    # PILOT provenance, per case, straight out of the immutable raw record
    pilot_fields, pilot_cases, seen = {}, 0, set()
    for line in open(RESULTS_JSONL):
        r = json.loads(line)
        if r.get("name") in seen:
            continue
        seen.add(r["name"])
        pl = (r.get("prov") or {}).get("pilot", [])
        if pl:
            pilot_cases += 1
        for f in pl:
            pilot_fields[f] = pilot_fields.get(f, 0) + 1

    emittable = set(val["coverage"]["emittable_mnemonics"])
    generated = set(ledger["mnemonics_used"])
    by_mnem = {i["mnemonic"]: i for i in db["instructions"]}

    donor_of = {m: sorted(d.items()) for m, d in donor_fields.items()}
    # Which mnemonics are ever built OUTSIDE the copied-token module? cf.py builds
    # every CF instruction with _copied(); synth/families/generator/casematrix build
    # from RULE/FREE/PILOT. Grepping the mnemonic string in each is directly auditable.
    def _srcs(fn):
        return open(os.path.join(E167, fn)).read()
    cf_src = _srcs("cf.py")
    other_src = "".join(_srcs(f) for f in ("synth.py", "families.py",
                                           "generator.py", "casematrix.py"))
    rule_generated_somewhere = {m for m in generated if ('"%s"' % m) in other_src}
    donor_only = {m for m in generated
                  if ('"%s"' % m) in cf_src and m not in rule_generated_somewhere}

    rows = []
    for m in sorted(emittable | generated):
        i = by_mnem.get(m, {})
        entry = val["instructions"].get(m, {})
        covered = 0
        for (s, w, _v) in i.get("match", []):
            covered |= ((1 << w) - 1) << s
        fields = []
        for f in i.get("fields", []):
            span = ((1 << f["width"]) - 1) << f["start"]
            free = bin(span & ~covered).count("1")
            row = entry.get(f["name"], {})
            lab = row.get("label", "MISSING")
            if free == 0:
                kind = "MATCH-PINNED (no choice; part of the opcode, not a field)"
            elif lab in EMIT:
                kind = "FREE (implementer chooses; measured)"
            else:
                kind = "UNMEASURED (label %s)" % lab
            fields.append({"name": f["name"], "free_bits": free, "label": lab,
                           "kind": kind, "range": row.get("range", ""),
                           "target": row.get("target", "")})
        n_free = sum(1 for f in fields if f["kind"].startswith("FREE"))
        n_pin = sum(1 for f in fields if f["kind"].startswith("MATCH-PINNED"))
        n_un = sum(1 for f in fields if f["kind"].startswith("UNMEASURED"))

        in_e, in_g = m in emittable, m in generated
        donors = donor_of.get(m, [])
        # a mnemonic is donor-BOUND when EVERY field it uses is still lifted verbatim;
        # if it is also rule-generated elsewhere in the corpus, say so instead.
        if m in donor_only:
            verdict = "DONOR-DEPENDENT"
            can = False
            why = ("this mnemonic is built ONLY inside EXP-0167's cf.py, whose every field is "
                   "_copied() verbatim from the EXP-0090 P3 skeleton; it appears nowhere in the "
                   "rule-driven generator modules. Donor tokens: "
                   + ", ".join("%s x%d cases" % (f, n) for f, n in donors))
        elif donors:
            verdict = "PARTLY-DONOR"
            can = True
            why = ("rule-generated elsewhere in the corpus (it appears in the rule-driven "
                   "generator modules), but %d of its fields are still lifted verbatim in the "
                   "12 CF programs: %s" % (len(donors), ", ".join(f for f, _ in donors)))
        elif in_e and in_g:
            verdict = "GENERATED-AND-EMITTABLE"
            can = True
            why = ("every field labelled emitter-grade AND a zero-copied program using this "
                   "mnemonic ran correctly against a host oracle on G17P (EXP-0167)")
        elif in_g and not in_e:
            verdict = "GENERATED-NOT-EMITTABLE"
            can = True
            why = ("a zero-copied generated program using this mnemonic ran correctly on G17P, "
                   "but %d field(s) are still unlabelled, so the emittable metric excludes it "
                   "— the METRIC under-counts this instruction" % n_un)
        else:
            verdict = "EMITTABLE-NOT-GENERATED"
            can = None
            why = ("all %d fields carry an emitter-grade label, but NO generated program "
                   "containing this instruction has ever been executed. Closure rule 1 "
                   "(generated, not merely decoded) is not established for it by EXP-0167."
                   % len(fields))
        rows.append({
            "mnemonic": m, "verdict": verdict,
            "in_emittable_set": in_e, "in_generated_corpus": in_g,
            "generator_assemble_calls": ledger["mnemonics_used"].get(m, 0),
            "donor_fields": {f: n for f, n in donors},
            "pilot_fields_used": {k.split(".", 1)[1]: v for k, v in pilot_fields.items()
                                  if k.startswith(m + ".")},
            "can_generate_from_documented_rules_alone": can,
            "why": why,
            "n_fields": len(fields), "n_free_measured": n_free,
            "n_match_pinned": n_pin, "n_unmeasured": n_un,
            "fields": fields,
        })

    cnt = {}
    for r in rows:
        cnt[r["verdict"]] = cnt.get(r["verdict"], 0) + 1
    out = {"_meta": {
        "experiment": "EXP-0173",
        "question": "for how much of the emittable set can an implementer generate an encoding "
                    "without a captured Apple template",
        "emittable_set_size": len(emittable),
        "generated_corpus_size": len(generated),
        "intersection": sorted(emittable & generated),
        "intersection_size": len(emittable & generated),
        "emittable_but_never_generated": sorted(emittable - generated),
        "generated_but_not_emittable": sorted(generated - emittable),
        "verdict_counts": cnt,
        "donor_only_mnemonics": sorted(donor_only),
        "donor_only_that_are_labelled_EMITTABLE": sorted(donor_only & emittable),
        "donor_token_pairs_total": len(donor_tokens),
        "EXP0167_headline": {
            "zero_copied_and_correct": summ["HEADLINE_N_zero_copied_and_correct"],
            "of_those_resting_on_PUBLISHED_RULES_ONLY":
                summ["HEADLINE_N0_zero_copied_zero_pilot_and_correct"],
            "of_those_containing_at_least_one_PILOT_field":
                summ["HEADLINE_N_zero_copied_and_correct"]
                - summ["HEADLINE_N0_zero_copied_zero_pilot_and_correct"],
            "cases_still_needing_a_donor": summ["cases_still_needing_a_donor"],
            "pilot_field_census": pilot_fields,
            "reading": "PILOT means EXP-0167 measured the field's accepted set itself in its "
                       "own pre-freeze pilot, because NO PRIOR RULE EXISTED. So only 60 of the "
                       "233 rest on rules an implementer could have read out of earlier work; "
                       "the other 173 rest on a value this experiment had to measure, and for "
                       "163 of them that value is ONE field, falu2.mod_hi.",
        },
        "sources": {"emittable": "tools/agx-isa/validation.json coverage.emittable_mnemonics",
                    "generated": "experiments/EXP-0167-g17p-synthesis-reconfirm/analysis/"
                                 "assemble_defect_check.json mnemonics_used",
                    "donor": "EXP-0167 RESULTS.md sections 5.7 and 6"},
        "limitation": "membership in the generated corpus is per MNEMONIC. It does not mean "
                      "every field of that mnemonic was swept inside a generated program; "
                      "EXP-0167 used 2,396 distinct (mnemonic, field-values) pairs across 18 "
                      "mnemonics, not the full operand space of any of them.",
    }, "instructions": rows}
    p = os.path.join(HERE, "template_dependency.json")
    json.dump(out, open(p, "w"), indent=1)
    print(json.dumps(out["_meta"], indent=1))
    print("\n%-24s %-26s %-6s %-6s %s" % ("mnemonic", "verdict", "emit?", "gen?", "unmeasured"))
    for r in sorted(rows, key=lambda r: (r["verdict"], r["mnemonic"])):
        print("%-24s %-26s %-6s %-6s %d" % (
            r["mnemonic"], r["verdict"], "E" if r["in_emittable_set"] else "-",
            "G" if r["in_generated_corpus"] else "-", r["n_unmeasured"]))
    print("\nwrote", p)


if __name__ == "__main__":
    sys.exit(main())
