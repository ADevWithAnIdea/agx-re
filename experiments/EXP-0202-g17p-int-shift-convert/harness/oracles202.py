#!/usr/bin/env python3
"""EXP-0202 per-value HOST oracles.

FIELD-SWEEP-PROTOCOL §3.4 and the dispatch's own words: *a DISCRIMINATING oracle
-- host-computed expected values that differ per field value. A constant oracle
is NOT evidence about the field.* `tools/agx-isa/wave_audit.py` enforces the same
thing mechanically (`distinct oracles <= 1` -> "predicts the instruction, not the
field").

So every target arm carries a rule that turns a FIELD VALUE into a PREDICTION,
before the run:

  exact_iff_compiled   The field is modelled LIVE: the program reproduces the
                       carrier's host-computed vector IFF the field holds the
                       value the compiler chose, and is broken otherwise. This
                       is the hypothesis under test written as an oracle, so the
                       data can REFUTE it -- if a field turns out to be reserved,
                       255 of 256 predictions fail and that is the result.
  rot_amount           `irotate`'s immediate-amount byte: the prediction is the
                       EXACT rotate-by-k vector the host computes for the amount
                       the byte encodes, for every value the census's byte-diff
                       model covers, and `unmodelled` elsewhere. Up to 32 distinct
                       predictions in one arm.
  control              A field already at emitter grade, swept to prove the arm
                       can see a difference at all. Same shape as
                       exact_iff_compiled.

CLEAN-ROOM: pure host arithmetic over our own MSL's semantics.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import carriers202 as C     # noqa: E402


def predict(arm, carrier, value):
    """-> (oracle_dict, expect_vector_or_None). `expect` is compared bit-exactly
    against the value region; None means no exact vector is predicted."""
    rule = arm.get("oracle_rule", "exact_iff_compiled")
    base = arm.get("baseline_field_value")
    ovec = C.CARRIERS[carrier]["oracle"]
    if rule == "rot_amount":
        amt = arm.get("value_to_amount", {}).get(str(value))
        if amt is None:
            return ({"class": "unmodelled", "rule": rule}, None)
        vec = [C.rotl(a, amt) for a in C.A_ROT]
        post = arm.get("post")
        if post == "alu":                       # rot_alu: (rot*3 + 7)
            vec = [((x * 3) + 7) & C.M32 for x in vec]
        return ({"class": "exact", "rule": rule, "amount": amt, "vals": vec}, vec)
    if rule in ("exact_iff_compiled", "control"):
        if base is not None and value == base:
            return ({"class": "exact", "rule": rule, "vals": ovec}, ovec)
        return ({"class": "broken", "rule": rule,
                 "why": "the field is modelled live, so any value the compiler "
                        "did not choose is predicted NOT to reproduce the "
                        "carrier's vector"}, None)
    return ({"class": "none", "rule": rule}, None)


def score(carrier, words, oracle, expect, unwritten_n, nvals):
    """-> outcome string. `expect is None` means the prediction is 'broken', so a
    case that reproduces the carrier vector REFUTES the prediction and is
    recorded as `unexpected_ok`, never silently as a pass."""
    reproduces = C.match_oracle(carrier, words)
    if expect is not None:
        if C.match_vector(carrier, words, expect):
            return "ok", True
    if reproduces and expect is None:
        return "unexpected_ok", False
    if unwritten_n == nvals:
        return "not_written", False
    vals = [words[i] for i in C.CARRIERS[carrier]["val_words"] if i < len(words)]
    if vals and all(v == 0 for v in vals):
        return "silent_zero", False
    return "wrong_value", False
