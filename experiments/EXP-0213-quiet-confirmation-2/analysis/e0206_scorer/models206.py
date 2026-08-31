#!/usr/bin/env python3
"""EXP-0206 COMPETING SEMANTIC MODELS -- Gate C of
`RE_EXPERIMENT_PROCESS_CORRECTIONS.md` section 3.

> "Pre-register the competing semantic models and a prediction for every case
>  before seeing the output. ... A difference from baseline is not a semantic
>  oracle. Cross-run agreement proves repeatability, not meaning. ...
>  `sem_checked == 0` can never produce `hardware-run`."

Every model here is a total function from (arm, requested value) to one of the
FIVE required buckets, computed on the HOST from the compiled occurrence's own
bytes -- never from a GPU result:

    correct   the oracle vector exactly (the program still does what the MSL says)
    coherent  a different but COHERENT effect (deterministic, non-oracle output)
    dead      silent zero / no write / dead path
    reject    rejected, faulted, or hung
    None      this model makes no prediction for this case

`coherent_or_reject` is deliberately NOT a bucket: a model that predicts "something
will go wrong" without saying WHICH way is not a semantic model, and the gate
scores it as an unpredicted case.

These models were frozen in `PRE_REGISTRATION_A2.md` **before the first dispatch of
the gated pair**, and after the pilot (calibration). Where a model was suggested by
pilot calibration that is stated in its docstring; the pilot cannot confirm it, and
the gated pair is what selects among them.

CLEAN-ROOM: pure host-side prediction over our own compiled bytes.
"""

BUCKETS = ("correct", "coherent", "dead", "reject")


# --------------------------------------------------------------------------- #
# if_push.scope  (byte+2 of `0f 05 <scope> <scope_kind>`)
# --------------------------------------------------------------------------- #
def ifp_M1_bank_parity(arm, v):
    """M1 -- BANK SELECTOR, bit 1 must MATCH the compiled bank.

    db.json models `scope` as the reconvergence mask BANK and says it "ping-pongs
    0x54/0x56 with nesting parity". If that is a real semantic, the push's bank
    must agree with the bank its matching `pop_reconverge` restores, so the
    correct set is exactly the values whose bit 1 equals the COMPILED value's
    bit 1, at occurrences where the bank is actually in use (loop-iteration
    pushes, `scope_kind == 0x1a`). Elsewhere the field is predicted inert.

    Suggested by pilot p01 calibration: at cf_nl2+106 (compiled 0x56) every
    bit-1-clear value faulted, while at cf_nl3+182 (compiled 0x54) bit-1-clear
    values were correct. EXP-0188's literal "bit 1 must be SET" (M2 below) cannot
    explain the second observation.
    """
    cf, dim = arm.get("compiled_field"), arm.get("occ_dim")
    if cf is None:
        return None
    if dim != 0x1a:
        return "correct"
    return "correct" if (v & 0x02) == (cf & 0x02) else "reject"


def ifp_M2_bit1_set(arm, v):
    """M2 -- EXP-0188's literal reading: at a loop-iteration push the program is
    correct iff bit 1 of `scope` is SET, regardless of the compiled value."""
    if arm.get("occ_dim") != 0x1a:
        return "correct"
    return "correct" if (v & 0x02) else "reject"


def ifp_M3_inert(arm, v):
    """M3 -- the field is inert: every value is correct."""
    return "correct"


def ifp_M4_exact(arm, v):
    """M4 -- only the compiled value is accepted; everything else is rejected."""
    cf = arm.get("compiled_field")
    return None if cf is None else ("correct" if v == cf else "reject")


# --------------------------------------------------------------------------- #
# pop_reconverge.scope  (byte+2 of `0f 06 <scope> <scope_kind> <reserved16>`)
# --------------------------------------------------------------------------- #
def pop_M1_bank_bit5(arm, v):
    """M1 -- BANK SELECTOR: db.json documents exactly two values, 0x04 (bankA)
    and 0x24 (bankB), which differ in bit 5 (0x20). Correct iff bit 5 matches the
    compiled bank. Our own carriers emit BOTH (0x04 in every loop carrier, 0x24
    in cl_atomic), so the compiler itself spans this dimension."""
    cf = arm.get("compiled_field")
    if cf is None:
        return None
    return "correct" if (v & 0x20) == (cf & 0x20) else "reject"


def pop_M2_low_nibble(arm, v):
    """M2 -- the low nibble is the real operand and must be 0x4; the high nibble
    is free."""
    return "correct" if (v & 0x0F) == 0x04 else "reject"


def pop_M3_inert(arm, v):
    return "correct"


def pop_M4_exact(arm, v):
    cf = arm.get("compiled_field")
    return None if cf is None else ("correct" if v == cf else "reject")


# --------------------------------------------------------------------------- #
# ret_luse.linkmode / (same byte on ret)
# --------------------------------------------------------------------------- #
def luse_M1_link(arm, v):
    """M1 -- LEAF vs NON-LEAF LINK. db.json: 0x02 leaf, 0x12 non-leaf
    restore-link, 0x04/0x05 CF merge. If that is a real semantic then at a
    NON-LEAF return the link must be restored, so substituting the leaf value
    0x02 must NOT produce the oracle -- the return goes somewhere else, which is
    a COHERENT wrong result if it lands on real code and a REJECT if it does not.
    The model predicts the one thing it can commit to: the compiled value is
    correct, and the OTHER documented link mode is not.

    Note a pre-run refutation of the folklore from our own compiled code: EXP-0156
    reported the accepted set as `v & 7 == 4`, but this experiment's census finds
    the compiler itself emitting `ret_luse` with linkmode 0x12 (`8f 12 56 00`, the
    `m_at` callee of cl_atomic), and `ret` with 0x02. Both have `v & 7 != 4`."""
    cf, dim = arm.get("compiled_field"), arm.get("occ_dim")
    if cf is None:
        return None
    if v == cf:
        return "correct"
    if dim == 0x12 and v == 0x02:
        return "coherent"
    if dim == 0x02 and v == 0x12:
        return "coherent"
    return None


def luse_M2_accepted_set(arm, v):
    """M2 -- EXP-0156's rule: the accepted set is exactly `v & 7 == 4`."""
    return "correct" if (v & 0x07) == 0x04 else "reject"


def luse_M3_exact(arm, v):
    cf = arm.get("compiled_field")
    return None if cf is None else ("correct" if v == cf else "reject")


def luse_M4_inert(arm, v):
    return "correct"


# --------------------------------------------------------------------------- #
# ret.scoreboard  (byte+3 of `8f <linkmode> 54 <scoreboard>`)
# --------------------------------------------------------------------------- #
def sb_M1_wait_mask(arm, v):
    """M1 -- EXECUTION/MEMORY-ORDERING WAIT MASK (db.json: bit5 0x20 = wait-set
    present, bit2 0x04 = second slot). Prediction, and the reason the ORDERING
    carrier axis exists: on a carrier with NOTHING outstanding at the return
    (`cl_pure`, a callee with no memory access at all) no value can matter, so
    every value is correct. On a carrier with an outstanding hazard spanning the
    return, ADDING a wait for a slot that was never issued must either be
    harmless or stall -- but REMOVING an ordering constraint the program needs
    yields a stale/unordered value, i.e. COHERENT. Since the compiler emits 0x00
    here on every one of our callees, this model predicts `correct` everywhere on
    `cl_pure` and makes no prediction off the compiled value on hazard carriers.
    That asymmetry IS the test: if the hazard carriers behave exactly like
    `cl_pure`, M1 is refuted in this envelope."""
    if arm.get("carrier") == "cl_pure":
        return "correct"
    cf = arm.get("compiled_field")
    return "correct" if (cf is not None and v == cf) else None


def sb_M2_inert(arm, v):
    return "correct"


def sb_M3_exact(arm, v):
    cf = arm.get("compiled_field")
    return None if cf is None else ("correct" if v == cf else "reject")


# --------------------------------------------------------------------------- #
# call.tail  (byte+13 of the 14-byte direct call)
# --------------------------------------------------------------------------- #
def tail_M1_inert(arm, v):
    """M1 -- inert. The prior promotion was WITHHELD because the gate that made it
    could not fail; this model is registered so that the inert reading can now
    win or lose on prediction rather than on the absence of a conjunct."""
    return "correct"


def tail_M2_exact(arm, v):
    cf = arm.get("compiled_field")
    return None if cf is None else ("correct" if v == cf else "reject")


def tail_M3_low_bit(arm, v):
    """M3 -- the byte carries a live low bit (a length/framing or link flag), so
    only even values are accepted. Registered as the simplest LIVE alternative
    that the corpus cannot already rule out."""
    return "correct" if (v & 1) == 0 else "reject"


# --------------------------------------------------------------------------- #
# reserved fields:  pop_reconverge.reserved (16 b), stop.reserved (24 b)
# --------------------------------------------------------------------------- #
def rsv_M1_inert(arm, v):
    """M1 -- inert: the arm's BASELINE bucket for every value. For a natural stop
    or a reconverge the baseline is `correct`; for the SYNTHESIZED mid-program
    stop the baseline is `dead` (the program terminates there and writes no value
    words), and predicting `correct` for it would be predicting the wrong thing."""
    return arm.get("baseline_bucket", "correct")


def rsv_M2_exact(arm, v):
    cf = arm.get("compiled_field")
    if cf is None:
        return None
    return arm.get("baseline_bucket", "correct") if v == cf else "reject"


def rsv_M3_any_live(arm, v):
    """M3 -- some bit in the reserved span is live, so a value differing from the
    compiled one changes the outcome. Deliberately the WEAKEST live model: it
    only has to be right once to beat M1."""
    cf = arm.get("compiled_field")
    if cf is None:
        return None
    return arm.get("baseline_bucket", "correct") if v == cf else "coherent"


MODELS = {
    "if_push.scope": {"M1_bank_parity": ifp_M1_bank_parity,
                      "M2_bit1_set": ifp_M2_bit1_set,
                      "M3_inert": ifp_M3_inert,
                      "M4_exact": ifp_M4_exact},
    "pop_reconverge.scope": {"M1_bank_bit5": pop_M1_bank_bit5,
                             "M2_low_nibble": pop_M2_low_nibble,
                             "M3_inert": pop_M3_inert,
                             "M4_exact": pop_M4_exact},
    "pop_reconverge.reserved": {"M1_inert": rsv_M1_inert,
                                "M2_exact": rsv_M2_exact,
                                "M3_any_live": rsv_M3_any_live},
    "call.tail": {"M1_inert": tail_M1_inert,
                  "M2_exact": tail_M2_exact,
                  "M3_low_bit": tail_M3_low_bit},
    "ret.scoreboard": {"M1_wait_mask": sb_M1_wait_mask,
                       "M2_inert": sb_M2_inert,
                       "M3_exact": sb_M3_exact},
    "ret_luse.linkmode": {"M1_link": luse_M1_link,
                          "M2_accepted_set": luse_M2_accepted_set,
                          "M3_exact": luse_M3_exact,
                          "M4_inert": luse_M4_inert},
    "stop.reserved": {"M1_inert": rsv_M1_inert,
                      "M2_exact": rsv_M2_exact,
                      "M3_any_live": rsv_M3_any_live},
    "stop.reserved@synth_mid": {"M1_inert": rsv_M1_inert,
                                "M2_exact": rsv_M2_exact,
                                "M3_any_live": rsv_M3_any_live},
}


def predict(key, arm, values):
    """-> {model_name: {str(value): bucket}} for every model of `key`."""
    out = {}
    for mname, fn in MODELS.get(key, {}).items():
        out[mname] = {str(v): fn(arm, v) for v in values}
    return out


# The observed bucket, derived from the run's own outcome classification. Kept
# here so prediction and observation share one vocabulary.
OUTCOME_BUCKET = {
    "ok": "correct",
    "wrong_value": "coherent",
    "silent_zero": "dead",
    "not_written": "dead",
    "fault": "reject",
    "hang": "reject",
    "invalid_run": None,            # invalid measurement -- never scored
    "measurement_failure": None,    # a malformed runner response is NOT a hardware outcome
    "nondeterministic": None,
    "carrier_start_failed": None,
}
