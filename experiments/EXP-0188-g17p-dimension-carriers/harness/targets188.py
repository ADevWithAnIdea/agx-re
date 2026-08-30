#!/usr/bin/env python3
"""EXP-0188 targets: for each field, THE DIMENSION IT PLAUSIBLY CONTROLS and the
carrier axis built to differ in it. Frozen in PRE_REGISTRATION.md section 4.

The standing rule this file exists to satisfy: **eight arms that cannot express a
field are one arm**. A null result is only worth recording if the carriers span
the dimension the field controls, so each entry names that dimension explicitly
and the arm generator selects occurrences to maximise its spread.

`occ_dimension_fields` names fields of the SAME instruction whose compiled value
identifies the dimension of an individual OCCURRENCE (as opposed to of a whole
carrier). For `if_push` that is `scope_kind`, which is exactly the axis EXP-0184
could not reach.
"""

TARGETS = [
    {
        "group": "cf",
        "mnemonic": "if_push",
        "field": "scope",
        "dimension": "REGION KIND: conditional-skip (scope_kind 0x01) vs "
                     "loop-iteration (scope_kind 0x1a). EXP-0184 swept 10 "
                     "occurrences over nesting depth 1..3 and every one was "
                     "`0f 05 54 01`; db.json's 0x54/0x56 nesting-parity claim "
                     "comes from LOOP-iteration pushes it never reached.",
        "carriers": ["cf_nl2", "cf_nl3", "cf_nlif", "cf_wbrk", "cf_ifnl",
                     "cf_lcont"],
        "dimension_values": {"cf_nl2": "2 nested memory-bounded loops",
                             "cf_nl3": "3 nested memory-bounded loops",
                             "cf_nlif": "if inside 2 nested loops",
                             "cf_wbrk": "while(true)+break, nested twice",
                             "cf_ifnl": "2 nested loops inside an if/else",
                             "cf_lcont": "nested loops with a continue edge"},
        "occ_dimension_fields": ["scope_kind"],
        "max_occ_per_carrier": 6,
    },
    {
        "group": "sdb",
        "mnemonic": "simd_ballot",
        "field": "cache",
        "dimension": "EXECUTION-MASK BANK / divergence depth. Four control-flow "
                     "descriptors in this ISA put a mask-BANK selector at byte+2 "
                     "in the same low form (if_push 0x54/0x56, jump_cond "
                     "0x54/0x64, mask_op 0x04/0x24, pop_reconverge 0x04/0x24). "
                     "EXP-0163 spanned the reuse/last-use dimension the NAME "
                     "suggests (k_scache) and reached divergence depth 1 only "
                     "(k_sdiv). Two mask banks are indistinguishable in a "
                     "program that is never more than one region deep.",
        "carriers": ["sd_flat", "sd_n1", "sd_n2", "sd_n3", "sd_loop"],
        "dimension_values": {"sd_flat": "depth 0 (no divergence)",
                             "sd_n1": "depth 1", "sd_n2": "depth 2",
                             "sd_n3": "depth 3",
                             "sd_loop": "loop-iteration region, shrinking mask"},
        "occ_dimension_fields": [],
        "max_occ_per_carrier": 3,
    },
    {
        "group": "sds",
        "mnemonic": "simd_shuffle",
        "field": "cache",
        "dimension": "same as simd_ballot.cache. NOTE the width: this `cache` is "
                     "ONE BIT of a byte that is 0x54 in every occurrence ever "
                     "observed, so a null covers TWO values of ONE bit and must "
                     "not be reported as 'byte+2 of simd_shuffle is inert'.",
        "carriers": ["sd_flat", "sd_n1", "sd_n2", "sd_n3", "sd_loop"],
        "dimension_values": {"sd_flat": "depth 0 (no divergence)",
                             "sd_n1": "depth 1", "sd_n2": "depth 2",
                             "sd_n3": "depth 3",
                             "sd_loop": "loop-iteration region, shrinking mask"},
        "occ_dimension_fields": [],
        "max_occ_per_carrier": 3,
    },
    {
        "group": "ia",
        "mnemonic": "iadd2",
        "field": "b2_fmt",
        "dimension": "OPERAND FORMAT / WIDTH. EXP-0171 swept all 64 sub-values "
                     "dense and inert on ONE carrier, a 32-bit unsigned "
                     "register+register add. Nothing has varied width (16/32/64), "
                     "the srcB register-vs-immediate type, or a uniform operand -- "
                     "the three format distinctions db.json's own semantics "
                     "already documents for this encoding.",
        "carriers": ["ia_u32", "ia_s32", "ia_u16", "ia_u64", "ia_imm",
                     "ia_uni", "ia_chain"],
        "dimension_values": {"ia_u32": "32-bit unsigned reg+reg",
                             "ia_s32": "32-bit signed reg+reg",
                             "ia_u16": "16-bit unsigned",
                             "ia_u64": "64-bit register pair",
                             "ia_imm": "32-bit with inline immediate srcB",
                             "ia_uni": "32-bit with a uniform operand",
                             "ia_chain": "two dependent adds, ALU-consumed"},
        "occ_dimension_fields": [],
        "max_occ_per_carrier": 2,
    },
]

# Detection-power controls: a field of the SAME instruction at the SAME
# occurrence that is ALREADY KNOWN LIVE. An arm whose control never moves has no
# detection power and is BARRED from supporting any verdict, inert or live
# (EXP-0172 gate rule 3). None of these is a MATCH byte: changing a match byte
# changes which instruction the bytes ARE, which is how a false "inert" was
# produced on the M4 today and how two fields were withdrawn.
CONTROLS = {
    "if_push": [
        ("scope_kind", [0, 1, 2, 4, 5, 8, 16, 26, 32, 33, 37, 64, 128, 160, 224, 255],
         "hardware-run (EXP-0140); fired on all 10 arms of EXP-0184 at 32 lanes. "
         "0x01 vs 0x1a is the region KIND itself."),
    ],
    "simd_ballot": [
        ("dst", list(range(0, 64, 2)),
         "the result register: db.json R8 tracked it moving 00/02/04 with the "
         "destination. Sampled over r0..r31 only -- the high end of an 8-bit "
         "register byte is a known fault region in other families (EXP-0139)."),
    ],
    "simd_shuffle": [
        ("lane", list(range(0, 64, 2)),
         "HW-proven `index<<1` lane selector (db.json R9): changing it changes "
         "WHICH lane's value is read, so it must move on any live shuffle."),
    ],
    "iadd2": [
        ("store_en", [0, 1],
         "byte+2 bit 1. EXP-0171 measured byte+2 moving 128/256 via bits 0..1 on "
         "its NAT carrier -- this is the direct demonstration that the BYTE the "
         "target field lives in is live on this carrier."),
        ("srcB_imm", list(range(0, 256, 8)),
         "EXP-0154 (G17P, HW-VALIDATED 128/128): this is a register selector in "
         "reg<<2 packing, not an immediate; values selecting an unseeded "
         "register read 0."),
    ],
}
