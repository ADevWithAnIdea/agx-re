#!/usr/bin/env python3
"""EXP-0202 AMENDMENT (v3) oracles: a PREDICTED OUTCOME BUCKET per case.

`harness/oracles202.py` is NOT edited (run02's frozen hash). This module adds
what `RE_EXPERIMENT_PROCESS_CORRECTIONS.md` Gate C requires:

    "Pre-register the competing semantic models and a prediction for every case
     before seeing the output. The predictor must be independent of the GPU
     result and must distinguish at least: correct value/effect; a different but
     coherent effect; silent zero/no write/dead path; rejected/faulted/hung
     execution; invalid measurement or contamination.
     ...
     A difference from baseline is not a semantic oracle."

So every case now carries `predicted_bucket`, and the record carries
`sem_match` = (predicted bucket == observed bucket). `sem_checked` counts the
cases where a bucket was predicted at all; a field with `sem_checked == 0` can
never reach `hardware-run` (section 2).

BUCKETS, and what each model predicts:

  ok        the carrier's host vector is reproduced exactly
  not_ok    the program runs but does not reproduce it (a different coherent
            value, a silent zero, or no write). The models below cannot separate
            those three a priori, so they predict the union and the observed
            sub-bucket is reported.
  rejected  the command buffer faults or hangs

MODELS, pre-registered, per field:

  shift_amt_move.src_flag  SOURCE-CLASS SELECT: at the compiled value the amount
                           comes from the file the compiler chose -> ok; at the
                           other value it comes from the OTHER file, whose
                           contents at that index we did not put there -> not_ok.
  ibitcount.cache          WRITEBACK-ENABLE: ok at the compiled value, not_ok at
                           the other.
  ibitcount.dst            dst = reg<<1 selects the destination register. The
                           following store still reads the compiled register, so
                           ok iff value == compiled. AND a CROSS-TARGET TRANSFER
                           TEST: `iunary.dst`, the same byte, faults reproducibly
                           at 192-241 and 243-255 on M4 (EXP-0139); those values
                           are predicted `rejected` here. G17P is a different
                           target, so this prediction can fail -- which is the
                           point of making it.
  iunary.b1 / opsel        FUNCTION / DATAPATH SELECT: ok at the synthesized base
                           value, not_ok elsewhere.
  cvt_f2i.b9               THE LIVE MODEL: ok at the compiled value, not_ok
                           elsewhere. If byte+9 is genuinely reserved this model
                           is refuted at 255 of 256 values, and that refutation is
                           the result.
  irotate.operands b6      THE STRONGEST FORM: an EXACT host-computed vector per
                           value, rotate-left by K where byte+6 = 4*(32-K), from
                           the census byte-diff over amounts {1,5,7,13,19,31}.
  cvt_f2i.signflag         bit 6 selects signed vs unsigned; scored by comparing
                           lane 7 (2^31+2^8, outside int32) against the arm's own
                           unmutated baseline.

CLEAN-ROOM: pure host arithmetic.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import carriers202 as C     # noqa: E402
import carriers202b         # noqa: E402,F401  (registers the amendment carriers)

# The M4 `iunary.dst` fault region (EXP-0139), transferred as a prediction.
M4_DST_FAULT = set(range(192, 242)) | set(range(243, 256))

BUCKET_OF = {
    "ok": "ok",
    "unexpected_ok": "ok",
    "wrong_value": "not_ok",
    "silent_zero": "not_ok",
    "not_written": "not_ok",
    "fault": "rejected",
    "hang": "rejected",
    "nondeterministic": "invalid",
    "invalid_run": "invalid",
    "measurement_failure": "invalid",
}


def predict(arm, carrier, value):
    """-> (oracle_dict, expect_vector_or_None). The oracle dict always carries
    `predicted_bucket`, which is what Gate C scores."""
    rule = arm.get("oracle_rule", "exact_iff_compiled")
    base = arm.get("baseline_field_value")
    ovec = C.CARRIERS[carrier]["oracle"]
    key = "%s.%s" % (arm.get("instr"), arm.get("field"))

    if rule == "rot_amount":
        amt = arm.get("value_to_amount", {}).get(str(value))
        if amt is None:
            return ({"class": "unmodelled", "rule": rule,
                     "predicted_bucket": None}, None)
        vec = [C.rotl(a, amt) for a in C.A_ROT]
        if arm.get("post") == "alu":
            vec = [((x * 3) + 7) & C.M32 for x in vec]
        return ({"class": "exact", "rule": rule, "amount": amt, "vals": vec,
                 "predicted_bucket": "ok"}, vec)

    if rule in ("exact_iff_compiled", "control"):
        if key == "ibitcount.dst" and value in M4_DST_FAULT:
            return ({"class": "rejected", "rule": rule,
                     "why": "EXP-0139 (M4) found `iunary.dst` -- the same byte -- "
                            "reproducibly faulting at 192-241 and 243-255; this "
                            "arm transfers that as a G17P prediction",
                     "predicted_bucket": "rejected"}, None)
        if base is not None and value == base:
            return ({"class": "exact", "rule": rule, "vals": ovec,
                     "predicted_bucket": "ok"}, ovec)
        return ({"class": "broken", "rule": rule,
                 "why": "the field is modelled live, so a value the compiler did "
                        "not choose is predicted NOT to reproduce the carrier's "
                        "host vector",
                 "predicted_bucket": "not_ok"}, None)
    return ({"class": "none", "rule": rule, "predicted_bucket": None}, None)


def score(carrier, words, oracle, expect, unwritten_n, nvals):
    reproduces = C.match_oracle(carrier, words)
    if expect is not None and C.match_vector(carrier, words, expect):
        return "ok", True
    if reproduces and expect is None:
        return "unexpected_ok", False
    if unwritten_n == nvals:
        return "not_written", False
    vals = [words[i] for i in C.CARRIERS[carrier]["val_words"] if i < len(words)]
    if vals and all(v == 0 for v in vals):
        return "silent_zero", False
    return "wrong_value", False


def sem_check(oracle, outcome):
    """-> (sem_checked, sem_match). `invalid` observations are never scored."""
    pb = (oracle or {}).get("predicted_bucket")
    if pb is None:
        return False, None
    ob = BUCKET_OF.get(outcome)
    if ob in (None, "invalid"):
        return False, None
    return True, (pb == ob)
