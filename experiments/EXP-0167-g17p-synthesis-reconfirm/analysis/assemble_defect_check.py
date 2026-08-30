#!/usr/bin/env python3
"""EXP-0167 offline check: did DEF-0166-1 (the `assemble()` stuck-bit defect,
fixed at commit 4b16d0b4) corrupt any field value in this corpus?

THE DEFECT.  `isadb.assemble()` OR-ed the descriptor's `match` constant bits
into the word and then OR-ed each field's value on top, with no clear step:

    v |= (val & mask) << f["start"]          # cannot clear a bit

So any bit that a `match` constant sets which also lies inside a field's span
was STUCK AT 1 for every caller. 53 of db.json's fields overlap their own
descriptor's match that way. A sweep driving such a field through `assemble()`
counts 256 dispatched values while the hardware only ever sees a fraction of
them. The fix adds `v &= ~(mask << f["start"])` before the OR.

WHY IT MATTERS HERE.  EXP-0158's headline is "233 programs in which every field
was COMPUTED, none copied". Its `assert_round_trip()` disassembles a program and
re-assembles it *from the disassembled fields*, so a stuck bit is present on
both sides and the round trip passes regardless — it does NOT check that an
emitted field equals the value the provenance ledger says was chosen. If the
defect bit this corpus, some field would carry a value its ledger did not
choose, and the provenance claim would be weaker than stated.

THE CHECK.  Wrap the PINNED (pre-fix) `assemble` so every call made while
building the corpus is recorded, then re-assemble each call with the CORRECTED
algorithm over the SAME pinned descriptors, and diff the bytes. Any difference
is a field the generator asked for and did not get.

No GPU, no device, no Apple binary. Reads only this experiment's own pinned
snapshot and its own generator.
"""
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP))
sys.dont_write_bytecode = True

import synth as S           # noqa: E402  (loads the PINNED isadb)
isadb = S.isadb


def fixed_assemble(mnemonic, fields):
    """The corrected algorithm (DEF-0166-1), over the PINNED descriptors."""
    desc = isadb._BY_MNEM[mnemonic]
    length = desc["length"]
    v = 0
    for (start, width, value) in desc["match"]:
        v |= (value & ((1 << width) - 1)) << start
    for f in desc["fields"]:
        val = fields.get(f["name"], 0)
        mask = (1 << f["width"]) - 1
        v &= ~(mask << f["start"])          # the fix
        v |= (val & mask) << f["start"]
    return isadb._bytes_from_int(v, length)


def main():
    orig = isadb.assemble
    calls = []

    def recording(mnemonic, fields):
        out = orig(mnemonic, fields)
        calls.append((mnemonic, dict(fields), out))
        return out

    isadb.assemble = recording
    import casematrix as CM   # noqa: E402  (imported AFTER the patch)
    cases = CM.build_cases()
    isadb.assemble = orig

    diffs = []
    seen = set()
    seen_decode = set()
    for mnemonic, fields, got in calls:
        key = (mnemonic, tuple(sorted(fields.items())))
        if key in seen:
            continue
        seen.add(key)
        want = fixed_assemble(mnemonic, fields)
        if want != got:
            stuck = int.from_bytes(got, "little") & ~int.from_bytes(want, "little")
            diffs.append({"mnemonic": mnemonic, "fields": fields,
                          "pinned_bytes": got.hex(), "fixed_bytes": want.hex(),
                          "bits_stuck_at_1": "0x%x" % stuck})

    # ---- the stronger test: does the EMITTED instruction DECODE back to the
    # exact field values the ledger says the generator chose?  This is what
    # `assert_round_trip()` cannot answer, because it re-assembles from the
    # DISASSEMBLED fields -- a stuck bit sits on both sides of its comparison.
    # Here the requested value is compared against the decoded value, so any
    # bit the tooling smuggled in (from any cause, not only DEF-0166-1) shows
    # up as a field the generator asked for and did not get.
    ledger_mismatch = []
    for mnemonic, fields, got in calls:
        key = (mnemonic, tuple(sorted(fields.items())))
        if key not in seen_decode:
            seen_decode.add(key)
            recs, leftover = isadb.disassemble(got)
            if leftover or len(recs) != 1 or recs[0]["mnemonic"] != mnemonic:
                ledger_mismatch.append({"mnemonic": mnemonic, "fields": fields,
                                        "bytes": got.hex(), "why": "did not decode as one %s (%d recs, %d leftover)"
                                        % (mnemonic, len(recs), len(leftover))})
                continue
            dec = recs[0]["fields"]
            bad = dict((k, {"requested": v, "decoded": dec.get(k)})
                       for k, v in fields.items() if dec.get(k) != v)
            if bad:
                ledger_mismatch.append({"mnemonic": mnemonic, "bytes": got.hex(),
                                        "fields_not_delivered": bad})

    hexes = [c["hex"] for c in cases]
    dup = {}
    for c in cases:
        dup.setdefault(c["hex"], []).append(c["name"])
    duplicate_groups = [v for v in dup.values() if len(v) > 1]
    out = {
        "n_ledger_fields_checked": len(seen_decode),
        "n_ledger_value_mismatches": len(ledger_mismatch),
        "ledger_mismatches": ledger_mismatch[:200],
        "ledger_verdict": ("CLEAN -- every field value the generator requested is the "
                           "value the emitted instruction decodes back to, across all "
                           "distinct (mnemonic, field-values) pairs in the corpus"
                           if not ledger_mismatch else
                           "AFFECTED -- see `ledger_mismatches`"),
        "duplicate_program_groups": duplicate_groups,
        "n_cases": len(cases),
        "n_distinct_program_hex": len(set(hexes)),
        "n_assemble_calls": len(calls),
        "n_distinct_assemble_calls": len(seen),
        "mnemonics_used": dict(Counter(m for m, _, _ in calls)),
        "n_field_values_corrupted_by_DEF_0166_1": len(diffs),
        "corrupted": diffs[:200],
        "verdict": ("CLEAN -- the pinned (pre-fix) assembler produced, for every "
                    "(mnemonic, field-values) pair this corpus uses, exactly the "
                    "bytes the corrected assembler produces; DEF-0166-1 did not "
                    "alter any emitted field in EXP-0158's / EXP-0167's programs"
                    if not diffs else
                    "AFFECTED -- see `corrupted`: these field values were requested "
                    "by the generator and NOT delivered by the pre-fix assembler"),
    }
    (HERE / "assemble_defect_check.json").write_text(
        json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(json.dumps(dict((k, v) for k, v in out.items() if k != "corrupted"),
                     indent=2, sort_keys=True))
    for d in diffs[:20]:
        print("  CORRUPTED", d["mnemonic"], d["bits_stuck_at_1"], d["fields"])


if __name__ == "__main__":
    main()
