#!/usr/bin/env python3
"""EXP-0206 FROZEN target table: per field, the DIMENSION it would control, the
carrier axis built to differ in it, the detection-power control, and the value
list. Frozen by PRE_REGISTRATION.md sections 4-6 and hashed into
CAPTURE_CONTRACT.json.

The standing rule this file exists to satisfy: **eight arms that cannot express a
field are one arm.** Every one of the seven refusals this experiment attacks has
the same shape -- the arm could not express the dimension, or the gate could not
come out the other way -- so each entry names the dimension explicitly and the
arm generator selects occurrences to maximise its spread.

`occ_dimension_field` names a field of the SAME instruction whose compiled value
identifies the dimension of an INDIVIDUAL OCCURRENCE (as opposed to of a whole
carrier). For `if_push` that is `scope_kind`, which is exactly the axis EXP-0184
could not reach.
"""

# ---------------------------------------------------------------- value lists
DENSE8 = list(range(256))


def wide_values(width):
    """FIELD-SWEEP-PROTOCOL section 3 for w > 8: boundaries {0,1,2,max-1,max},
    EVERY power of two, and >= 16 ASYMMETRIC interior samples. Never only 0/1."""
    mx = (1 << width) - 1
    vals = {0, 1, 2, mx - 1, mx}
    for b in range(width):
        vals.add(1 << b)                      # every single-bit value
        vals.add(mx ^ (1 << b))               # every single-bit HOLE
    # asymmetric interior samples: nothing symmetric, nothing round
    for k in (3, 5, 7, 0x2A, 0x55, 0x7F, 0x81, 0xA5, 0xC3, 0xF0, 0x1234, 0x8001,
              0xABCD, 0xBEEF, 0xDEAD, 0x5A5A, 0x0F0F, 0x3C3C, 0x123456, 0xA5A5A5,
              0xFEDCBA, 0x800001, 0x7FFFFE):
        if k <= mx:
            vals.add(k)
    return sorted(vals)


# 16 values: boundaries, both parities, both halves, and the documented enum
# points where one exists. Used for every CONTROL arm.
CTRL16 = [0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x08, 0x0F,
          0x12, 0x1A, 0x20, 0x24, 0x54, 0x56, 0x80, 0xFF]

# `stop` termination-dimension positive control: byte 0 replaced by non-`0x0e`
# values. This is a MATCH byte and is offered ONLY as a control on the
# TERMINATION dimension, never as a field verdict (PRE_REGISTRATION H6).
STOP_B0 = [0x00, 0x01, 0x0f, 0x0c, 0x8f, 0x0d, 0x2e, 0xff]

# `call.offset` perturbation control: the target is call_addr + 4 + offset
# (EXP-0035/EXP-0179, taken as given). Perturbations are PARCEL-ALIGNED and small,
# so the branch lands on a real instruction boundary rather than mid-instruction.
CALL_OFF_DELTAS = [-8, -6, -4, -2, 2, 4, 6, 8]


TARGETS = [
    {
        "key": "if_push.scope",
        "region_select": "main",
        "group": "cf",
        "mnemonic": "if_push", "field": "scope",
        "dimension": "REGION KIND: conditional-skip (scope_kind 0x01) vs "
                     "LOOP-ITERATION (scope_kind 0x1a). EXP-0184 swept 10 "
                     "occurrences over nesting depth 1..3, every one of them "
                     "`0f 05 54 01`; db.json's 0x54/0x56 nesting-parity claim "
                     "comes from loop-iteration pushes it never reached.",
        # Four of the six loop shapes, chosen after the census (which is
        # pre-freeze calibration): together they reach scope_kind 0x1a, 0x21,
        # 0x25 AND 0x29, and compiled `scope` 0x54 AND 0x56. Two carriers are
        # dropped purely for device-time budget, and they add no dimension value
        # the four do not already carry.
        "carriers": ["cf_nl2", "cf_nl3", "cf_nlif", "cf_ifnl"],
        "occ_dimension_field": "scope_kind",
        "max_occ_per_carrier": 2,
        "values": DENSE8,
        "control": {"field": "scope_kind", "values": CTRL16,
                    "why": "hardware-run (EXP-0140); and it IS the region-kind "
                           "axis, so it is live in the same dimension"},
        "predict": "match iff (value & 0x02) at occurrences whose compiled "
                   "scope_kind == 0x1a; match for all values elsewhere",
    },
    {
        "key": "pop_reconverge.scope",
        "region_select": "main",
        "group": "cf",
        "mnemonic": "pop_reconverge", "field": "scope",
        "dimension": "the reconvergence MASK BANK popped. db.json documents two "
                     "values, 0x04 (bankA) and 0x24 (bankB) -- they differ in "
                     "bit 5.",
        # cl_atomic is included deliberately: the census shows its compiled pop
        # is `0f 06 24 02 00 00` -- scope 0x24, the OTHER documented bank -- while
        # every loop carrier emits 0x04. The compiler itself therefore spans the
        # dimension across this carrier set, which is the strongest possible
        # answer to "can these arms express the field".
        "carriers": ["cf_nl2", "cf_nl3", "cf_ifnl", "cl_atomic"],
        "occ_dimension_field": "scope_kind",
        "max_occ_per_carrier": 2,
        "values": DENSE8,
        "control": {"field": "scope_kind", "values": CTRL16,
                    "why": "hardware-run (EXP-0140), same word, same occurrence"},
        "predict": "movement at >=1 occurrence, concentrated in bit 5 (0x20)",
    },
    {
        "key": "pop_reconverge.reserved",
        "region_select": "main",
        "group": "cf",
        "mnemonic": "pop_reconverge", "field": "reserved",
        "dimension": "the remaining operand space of the 6-byte reconvergence "
                     "word. Withheld on DEF-0190-1 because the INERT bucket "
                     "returned moved=0 BY CONSTRUCTION.",
        "carriers": ["cf_nl2", "cf_nl3", "cf_nlif", "cf_wbrk", "cf_ifnl",
                     "cf_lcont", "cl_atomic"],
        "occ_dimension_field": "scope_kind",
        "max_occ_per_carrier": 2,
        "values": wide_values(16),
        "control": {"field": "scope_kind", "values": CTRL16,
                    "why": "hardware-run (EXP-0140), same word, same occurrence "
                           "-- the section 9.1 positive control"},
        "predict": "inert (baseline payload for every sampled value)",
    },
    {
        "key": "call.tail",
        "region_select": "main",
        "group": "cl",
        "mnemonic": "call", "field": "tail",
        "dimension": "unknown. Swept across BOTH dimensions this experiment "
                     "builds (link and ordering). No prediction is registered: "
                     "the prior promotion was withheld precisely because 'it "
                     "reproduces perfectly' was treated as evidence.",
        "carriers": ["cl_leaf", "cl_chain", "cl_deep", "cl_spill",
                     "cl_ldret", "cl_ldacross", "cl_stacross", "cl_atomic"],
        "occ_dimension_field": None,
        "max_occ_per_carrier": 1,
        "values": DENSE8,
        "control": {"field": "b6", "values": CTRL16,
                    "why": "EXP-0179 arm S proved bit 1 of b6 load-bearing on a "
                           "real compiler-emitted call"},
        "control2": {"field": "offset", "deltas": CALL_OFF_DELTAS,
                     "why": "target = call_addr + 4 + offset (EXP-0035, taken as "
                            "given): changing it MUST change where control goes"},
        "predict": None,
    },
    {
        "key": "ret.scoreboard",
        "region_select": "callee",
        "group": "cl",
        "mnemonic": "ret", "field": "scoreboard",
        "dimension": "MEMORY/EXECUTION ORDERING -- how much unretired memory "
                     "traffic exists when the ret executes. EXP-0179 declined "
                     "this field as pre-registered because both of its carriers "
                     "returned from a leaf callee with nothing to wait on.",
        # cl_chain and cl_spill each carry BOTH a leaf return (linkmode 0x02)
        # and a NON-LEAF return (linkmode 0x12); cl_atomic is dropped because its
        # callee ends in a real `ret_luse`, not a `ret` (it feeds the ret_luse
        # target instead).
        "carriers": ["cl_pure", "cl_ldret", "cl_ldacross", "cl_stacross",
                     "cl_chain", "cl_spill"],
        "occ_dimension_field": "linkmode",
        "max_occ_per_carrier": 2,
        "values": DENSE8,
        "control": {"field": "linkmode", "values": CTRL16,
                    "why": "hardware-run (EXP-0179/EXP-0192 Case A)"},
        "predict": "on the hazard carriers, clearing 0x20 (wait-set present) or "
                   "0x04 (second slot) yields a stale/unordered value or a fault; "
                   "cl_pure shows nothing",
    },
    {
        "key": "ret_luse.linkmode",
        "region_select": "callee",
        "group": "cl",
        "mnemonic": "ret_luse", "field": "linkmode",
        "dimension": "the LINK -- whether a saved return address must be "
                     "restored. EXP-0192 Case C: 1 distinct VALID payload across "
                     "32 LEGAL values, on leaf-only carriers that cannot tell "
                     "leaf from non-leaf apart.",
        # SYNTHESIZED occurrence: a real compiled `ret` with byte+2 forced
        # 0x54 -> 0x56. EXP-0156 ran exactly this as a pre-registered identity
        # control and it matched in both gated runs. The arm carries a
        # `luse_baseline` case so the construction is measured, not assumed.
        "from_mnemonic": "ret",
        "force": [(16, 8, 0x56)],
        # cl_atomic is FIRST and needs no synthesis at all: the census found its
        # callee `m_at` ends with a REAL compiler-emitted `ret_luse`,
        # `8f 12 56 00` -- byte+2 0x56 AND linkmode 0x12, the non-leaf
        # restore-link value the withdrawn measurement's leaf-only carriers could
        # never reach. The remaining carriers supply the synthesized form so the
        # real and synthesized occurrences can be compared directly.
        "carriers": ["cl_atomic", "cl_leaf", "cl_pure", "cl_chain", "cl_spill"],
        "occ_dimension_field": "linkmode",
        "max_occ_per_carrier": 2,
        "values": DENSE8,
        "control": {"field": "tail", "values": CTRL16,
                    "why": "hardware-run (EXP-0156), same word, same occurrence"},
        "predict": "at a non-leaf return (compiled linkmode 0x12), the leaf value "
                   "0x02 fails to restore the link -> a DIFFERENT valid payload "
                   "or a fault; at a leaf return 0x02 is correct",
    },
    {
        "key": "stop.reserved",
        "region_select": "all",
        "group": "both",
        "mnemonic": "stop", "field": "reserved",
        "dimension": "program TERMINATION. EXP-0003/EXP-0010 corrupted the FINAL "
                     "stop and saw a no-op; that says nothing about a MID-PROGRAM "
                     "stop, which in a kernel with an out-of-line callee must "
                     "genuinely terminate or execution falls into the callee.",
        "carriers": ["cf_nl2", "cf_nlif", "cf_ifnl",
                     "cl_leaf", "cl_chain", "cl_deep", "cl_ldacross",
                     "cl_stacross", "cl_atomic"],
        "occ_dimension_field": None,          # classified by follows_code
        "max_occ_per_carrier": 1,
        "values": wide_values(24),
        "control": {"byte0": STOP_B0,
                    "why": "the terminator itself. A MATCH byte, offered ONLY as "
                           "a TERMINATION-DIMENSION positive control and never as "
                           "a field verdict (PRE_REGISTRATION H6). If the "
                           "observable cannot detect that the terminator stopped "
                           "being one, the arm has no power over that word and "
                           "the verdict is UNRESOLVED."},
        "predict": "inert at both positions; the positive control fires at a "
                   "`mid` stop and does not fire at a `final` stop",
    },
]

# region_select: which SYMBOL REGION of the shader __text section an arm may be
# placed in. A kernel with an out-of-line callee puts the callee in its OWN
# region; `_agc.main` holds the CALL but not the callee's RETURN, which is why
# this experiment's first census found `ret` in zero carriers.
#   "main"   -> `_agc.main` only
#   "callee" -> every code region that is NOT `_agc.main*`
#   "all"    -> every code region (constant_program blobs excluded: they are data)

TARGETS.append({
    "key": "stop.reserved@synth_mid",
    "region_select": "main",
    "group": "cl",
    "mnemonic": "stop", "field": "reserved",
    "dimension": "program TERMINATION, measured at a CONSTRUCTED MID-PROGRAM "
                 "terminator. This entry exists because the census refuted H6's "
                 "assumption that one occurs naturally.",
    # THE POSITIVE CONTROL THE CENSUS SAID WE HAD TO BUILD.
    #
    # H6 assumed a kernel with an out-of-line callee would place the callee AFTER
    # the main body's `stop`, giving a mid-program terminator for free. The census
    # refuted that: the callee lives in its OWN symbol region, `_agc.main` ends at
    # its `stop`, and `follows_code` is False in all nine carriers. There is no
    # naturally occurring mid-program stop anywhere in this corpus.
    #
    # So one is CONSTRUCTED, over the 4-byte `frame_marker` (`43 00 00 01`) that
    # sits immediately before the call. The frame marker is an ESTABLISHED
    # OPTIONAL instruction (EXP-0179: the reconverge after a call is REQUIRED, the
    # frame marker is OPTIONAL) -- so replacing it with `0e 00 00 00` changes
    # exactly one thing, the presence of a terminator, and nothing else that is
    # load-bearing. The arm's `_force_baseline` case IS the positive control:
    #
    #   * program truncates (sentinel written, all 32 value words still POISON)
    #     -> a mid-program `stop` DOES terminate, the arm has termination
    #        detection power, and the swept 24-bit body is then a real inertness
    #        measurement at a LIVE terminator;
    #   * program still computes the correct answer -> a mid-program `stop` does
    #     NOT terminate, which is a first-class hardware fact in its own right and
    #     means NO arm in this experiment has termination detection power ->
    #     `stop.reserved` is reported UNRESOLVED, never "inert".
    "carriers": ["cl_leaf", "cl_chain", "cl_ldacross"],
    "from_mnemonic": "frame_marker",
    "force_always": True,
    "force": [(0, 8, 0x0e)],
    "force_note": "frame_marker (4 B, OPTIONAL per EXP-0179) overwritten with a "
                  "synthesized `stop`: byte0 0x43 -> 0x0e",
    "occ_dimension_field": None,
    "max_occ_per_carrier": 1,
    "values": wide_values(24),
    "control": {"field": "_synth_word", "values": [0x0000000e, 0x01000043, 0x00000000],
                "why": "the whole 32-bit word: a synthesized `stop`, the ORIGINAL "
                       "frame marker (identity), and all zeros. The three "
                       "together say whether the observable can see a terminator "
                       "appear where there was none."},
    "predict": "if the synthesized stop terminates, the 24-bit body is inert at a "
               "LIVE terminator; if it does not, stop.reserved is UNRESOLVED",
})

# ---------------------------------------------------------------- ARM SELECTION
# FROZEN SUBSET, added as contract amendment 5 after run01 was killed at 152 cases.
#
# WHY: the pilot measured 0.234 s/case on a quiet machine; run01 measured
# **1.756 s/case with 46% faults**, because two SIBLING EXPERIMENTS (EXP-0202 and
# one other) were sweeping the same GPU. Each `ErrorHang` resets the device, and
# each reset costs seconds plus a train of `InnocentVictim` retries. The full
# 12,173-case arm set would have taken about SIX HOURS per run, i.e. twelve for
# the gated pair. Run01 is RETAINED at 152 cases as a partial capture, is never
# topped up, and is not cited by any verdict.
#
# WHAT IS KEPT: for every field, occurrence classes that span the dimension under
# test, and for the inertness targets at least THREE structurally different
# carrier classes (RE_EXPERIMENT_PROCESS_CORRECTIONS section 7). Value coverage
# per arm is UNCHANGED -- the reduction is in occurrences, never in the swept
# range, because protocol section 3 coverage is a statement about the field's
# value space.
SELECT = {
    "if_push.scope": [
        ("cf_nl2", 106),    # scope_kind 0x1a (LOOP-ITERATION), compiled scope 0x56
        ("cf_nl3", 182),    # scope_kind 0x1a, compiled scope 0x54  <- the M1/M2 discriminator
        ("cf_nl2", 140),    # scope_kind 0x25 (NOT loop-iteration)  <- region-kind contrast
        ("cf_ifnl", 126),   # scope_kind 0x1a in a third loop shape
    ],
    "pop_reconverge.scope": [
        ("cf_nl2", 216),    # scope_kind 0x02 (loop body), compiled scope 0x04
        ("cf_nl2", 222),    # scope_kind 0x01 (guard/outermost)
        ("cl_atomic", 66),  # compiled scope 0x24 -- THE OTHER BANK, compiler-emitted
    ],
    "pop_reconverge.reserved": [
        ("cf_nl2", 216),    # loop carrier
        ("cf_ifnl", 184),   # loops inside an if/else
        ("cl_atomic", 66),  # call carrier, other bank -- 3 structurally different classes
    ],
    "call.tail": [
        ("cl_leaf", 54),    # leaf callee
        ("cl_chain", 54),   # NON-LEAF callee (c_mid)
        ("cl_atomic", 52),  # callee doing an atomic RMW and ending in a real ret_luse
    ],
    "ret.scoreboard": [
        ("cl_pure", 32),     # ordering NEGATIVE: callee has no memory access at all
        ("cl_stacross", 32), # SAME callee bytes, store->load hazard spanning the ret
        ("cl_ldret", 34),    # different callee: the load is inside it
        ("cl_chain", 104),   # NON-LEAF return, linkmode 0x12
    ],
    "ret_luse.linkmode": [
        ("cl_atomic", 32),  # REAL compiler-emitted `8f 12 56 00` -- no synthesis
        ("cl_leaf", 30),    # synthesized from a LEAF ret (linkmode 0x02)
        ("cl_chain", 104),  # synthesized from a NON-LEAF ret (linkmode 0x12)
    ],
    "stop.reserved": [
        ("cf_nl2", 268),    # loop carrier, final stop
        ("cl_leaf", 88),    # leaf-call carrier, final stop
        ("cl_atomic", 124), # atomic carrier, final stop
    ],
    "stop.reserved@synth_mid": [
        ("cl_leaf", 50),
        ("cl_chain", 50),
    ],
}

BY_KEY = {t["key"]: t for t in TARGETS}
