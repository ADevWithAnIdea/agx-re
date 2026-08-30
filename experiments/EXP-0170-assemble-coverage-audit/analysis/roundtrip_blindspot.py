#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0170 Arm C, part 2 -- DEMONSTRATE the blind spot instead of asserting it.

Re-implements the PRE-fix (OR-only) `isadb.assemble()` locally -- five lines, taken
from the code comment the fix left behind in tools/agx-isa/isadb.py -- and re-runs
the project's own round-trip suite against it.

Three questions:

  Q1  Does `tools/agx-isa/roundtrip_test.py` test (A), `asm(disasm(bytes)) == bytes`,
      still pass under the DEFECTIVE assembler?   (If yes: symmetric-blind.)
  Q2  Does test (B), `disasm(asm(fields)) == fields`, still pass under the DEFECTIVE
      assembler?  (B) compares against the CALLER's field values, so it is the one
      check in the repo that could have caught DEF-0166-1 -- but only if its corpus
      happens to supply a value that clears an overlapping bit.
  Q3  Constructively: for each of the 53 overlapping fields, is there a field value
      that (B) would have caught?  (Always yes by construction; the point is that the
      committed corpus never contains one.)

Nothing is written to tools/.  READ-ONLY except analysis/roundtrip_blindspot.json.
Usage: python3 analysis/roundtrip_blindspot.py
"""
import importlib.util, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(EXP, "..", ".."))
ISA = os.path.join(ROOT, "tools", "agx-isa")
sys.path.insert(0, ISA)

import isadb                                          # noqa: E402
_spec = importlib.util.spec_from_file_location("rt_suite",
                                               os.path.join(ISA, "roundtrip_test.py"))
RT = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(RT)                          # defines the corpora; no side effects


def assemble_old(mnemonic, fields):
    """The PRE-DEF-0166-1 assembler: match bits OR-ed in, then field values OR-ed in.
    Identical to the current isadb.assemble() except for the missing
    `v &= ~(mask << start)` clear."""
    desc = isadb._BY_MNEM[mnemonic]
    v = 0
    for (start, width, value) in desc["match"]:
        v |= (value & ((1 << width) - 1)) << start
    for f in desc["fields"]:
        val = fields.get(f["name"], 0)
        mask = (1 << f["width"]) - 1
        v |= (val & mask) << f["start"]                # <-- the defect: no clear
    return isadb._bytes_from_int(v, desc["length"])


def main():
    static = json.load(open(os.path.join(HERE, "static_overlap.json")))
    ov = static["overlapping_fields"]
    ovkeys = {(r["mnemonic"], r["field"]): r for r in ov}

    # ---- Q1: test (A) under the defective assembler -----------------------
    a_fail, a_rows = 0, []
    for label, h in RT.REAL_INSTRS.items():
        raw = bytes.fromhex(h)
        rec, _ = isadb.decode_one(raw, 0)
        got = assemble_old(rec["mnemonic"], rec["fields"])
        ok = got == raw
        a_fail += not ok
        a_rows.append({"label": label, "mnemonic": rec["mnemonic"], "ok": ok})

    # ---- Q2: test (B) under the defective assembler -----------------------
    b_fail, b_rows = 0, []
    for mnem, fields in RT.SYNTH:
        raw = assemble_old(mnem, fields)
        rec, _ = isadb.decode_one(raw, 0)
        ok = (rec["mnemonic"] == mnem and rec["fields"] == fields)
        b_fail += not ok
        touched = [f for f in fields if (mnem, f) in ovkeys]
        # would this case have caught the defect?  only if a supplied value clears a
        # bit the descriptor's own match sets inside that field's span.
        catching = []
        for f in touched:
            r = ovkeys[(mnem, f)]
            m = r["match_bits_in_span"]
            if (~fields[f]) & m & ((1 << r["width"]) - 1):
                catching.append(f)
        b_rows.append({"mnemonic": mnem, "ok": ok,
                       "fields_with_match_overlap": touched,
                       "fields_that_would_catch": catching})

    # ---- Q3: the corpus's coverage of the 53 -------------------------------
    synth_mnems = {m for m, _ in RT.SYNTH}
    real_mnems = set()
    for h in RT.REAL_INSTRS.values():
        try:
            rec, _ = isadb.decode_one(bytes.fromhex(h), 0)
            real_mnems.add(rec["mnemonic"])
        except Exception:
            pass
    ov_mnems = {r["mnemonic"] for r in ov}
    exercised = sorted(ov_mnems & synth_mnems)
    catchable = sorted({r["mnemonic"] for row in b_rows for r in [row]
                        if row["fields_that_would_catch"]})

    out = {
        "_meta": {"generated_by": "EXP-0170/analysis/roundtrip_blindspot.py",
                  "suite": "tools/agx-isa/roundtrip_test.py",
                  "assembler_under_test": "locally re-implemented PRE-DEF-0166-1 "
                                          "(OR-only) isadb.assemble()"},
        "Q1_test_A_asm_of_disasm_equals_bytes": {
            "cases": len(a_rows), "failures_under_defective_assembler": a_fail,
            "verdict": ("BLIND -- passes unchanged with the defective assembler"
                        if a_fail == 0 else "would have caught it"),
        },
        "Q2_test_B_disasm_of_asm_equals_fields": {
            "cases": len(b_rows), "failures_under_defective_assembler": b_fail,
            "cases_touching_an_overlapping_field":
                len([r for r in b_rows if r["fields_with_match_overlap"]]),
            "cases_that_would_have_caught_it":
                len([r for r in b_rows if r["fields_that_would_catch"]]),
            "verdict": ("BLIND -- passes unchanged with the defective assembler"
                        if b_fail == 0 else "would have caught it"),
        },
        "Q3_corpus_coverage_of_the_53": {
            "instructions_with_an_overlapping_field": len(ov_mnems),
            "of_those_present_in_the_SYNTH_corpus": exercised,
            "of_those_present_in_the_REAL corpus": sorted(ov_mnems & real_mnems),
            "synth_cases_that_could_have_caught_it": catchable,
        },
        "test_A_rows": a_rows,
        "test_B_rows": b_rows,
    }
    json.dump(out, open(os.path.join(HERE, "roundtrip_blindspot.json"), "w"), indent=1)
    print("Q1  test (A) asm(disasm(b))==b : %d cases, %d failures under the DEFECTIVE "
          "assembler -> %s" % (len(a_rows), a_fail, out["Q1_test_A_asm_of_disasm_equals_bytes"]["verdict"]))
    print("Q2  test (B) disasm(asm(f))==f : %d cases, %d failures under the DEFECTIVE "
          "assembler -> %s" % (len(b_rows), b_fail, out["Q2_test_B_disasm_of_asm_equals_fields"]["verdict"]))
    print("    cases touching one of the 53 overlapping fields: %d ; cases whose value "
          "would have caught it: %d"
          % (out["Q2_test_B_disasm_of_asm_equals_fields"]["cases_touching_an_overlapping_field"],
             out["Q2_test_B_disasm_of_asm_equals_fields"]["cases_that_would_have_caught_it"]))
    print("Q3  %d instructions carry an overlapping field; SYNTH corpus covers %d of them: %s"
          % (len(ov_mnems), len(exercised), ", ".join(exercised) or "(none)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
