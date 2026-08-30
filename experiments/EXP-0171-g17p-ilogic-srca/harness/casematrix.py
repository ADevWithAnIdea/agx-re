#!/usr/bin/env python3
"""EXP-0171 FROZEN case matrix.

The sweep plan is BYTE-dense and FIELD-decomposed:

  * every case mutates exactly ONE BYTE of the lifted instruction, densely over
    0..255, with every other byte at its compiler-emitted anchor value;
  * db FIELDS are recovered OFFLINE by the A5 decomposition (EXP-0166): a field's
    sub-values are the swept byte values whose OTHER bits equal the anchor's.

Why bytes and not fields: `isadb.assemble()` ORs the match constant before the
field values and an OR cannot clear a bit, so 53 fields in db.json are silently
under-swept when driven through it (EXP-0166 DEF-0166-1; `irotate.b2` reached 32
of 256 encodings while reporting 256). Splicing raw bytes cannot under-cover, and
`analysis/coverage.py` proves it by counting DISTINCT `bytes` strings rather than
trusting the dispatched-value count.

Fields wider than one byte additionally get the FIELD-SWEEP-PROTOCOL section 3.3
multi-byte set: {0, 1, 2, max-1, max}, every power of two, and 16 asymmetric
interior samples, written across all of the field's bytes at once.

Ladder rule (binding, FIELD-SWEEP-PROTOCOL section 7 / EXP-0164): every
(arm, carrier) sweeps at least one byte ALREADY established live on G17P before
any inertness verdict from that carrier is admitted. A carrier that cannot show
its ladder is discarded, not reported as evidence of inertness.

CLEAN-ROOM: pure planning over our own db.json and our own compiled anchors.
"""
import hashlib
import json

# --------------------------------------------------------------------------
# Kernel table: buffer index -> element type, for the NAT carriers.
#   0 = out (read back, poisoned)  1 = a  2 = b  3 = c  4 = sent (read back)
# --------------------------------------------------------------------------
KERNELS = {
    "k_and":       {"t": "uint",   "bufs": [1, 2]},
    "k_or":        {"t": "uint",   "bufs": [1, 2]},
    "k_xor":       {"t": "uint",   "bufs": [1, 2]},
    "k_andn":      {"t": "uint",   "bufs": [1, 2]},
    "k_nand":      {"t": "uint",   "bufs": [1, 2]},
    "k_and_sel":   {"t": "uint",   "bufs": [1, 2]},
    "k_and_if":    {"t": "uint",   "bufs": [1, 2]},
    "k_popcnt":    {"t": "uint",   "bufs": [1, 2]},
    "k_clz":       {"t": "uint",   "bufs": [1, 2]},
    "k_bfe":       {"t": "uint",   "bufs": [1, 2]},
    "k_bfe_s":     {"t": "uint",   "bufs": [1, 2]},
    "k_rsqrt":     {"t": "float",  "bufs": [1, 2]},
    "k_rsqrt_fast": {"t": "float", "bufs": [1, 2]},
    "k_recip_fast": {"t": "float", "bufs": [1, 2]},
    "k_u32add":    {"t": "uint",   "bufs": [1, 2]},
    "k_half2":     {"t": "half",   "bufs": [1, 2]},
    "k_cmpsel":    {"t": "uint",   "bufs": [1, 2]},
    "k_bfadd":     {"t": "bfloat", "bufs": [1, 2]},
    "k_bfmul":     {"t": "bfloat", "bufs": [1, 2]},
    "k_bffma":     {"t": "bfloat", "bufs": [1, 2, 3]},
}

# --------------------------------------------------------------------------
# The arm table. `target_bytes` are the bytes containing the BLOCKING fields;
# `ladder_bytes` are bytes whose liveness on G17P is already committed in
# tools/agx-isa/validation.json and which therefore prove detection power.
# `multi` lists (field, [byte offsets]) needing the section 3.3 wide-field set.
# --------------------------------------------------------------------------
ARMS = [
    # ---- ARM A: close `ilogic` (5 blocking fields) ----------------------
    {"arm": "ILOGIC", "instr": "ilogic", "stage": 1,
     "kernels": ["k_and"], "pred_kernels": ["k_and_sel", "k_and_if"],
     "target_bytes": [4, 6, 7, 8, 9],
     "ladder_bytes": [1, 5],
     "blocking": ["lut_a_free", "z6", "outmod", "z8", "z9"],
     "carriers": ["NAT", "PRED", "FRAME"],
     "kind": "int", "multi": []},

    # ---- ARM B tier 1 ---------------------------------------------------
    {"arm": "IBITCOUNT", "instr": "ibitcount", "stage": 2,
     "kernels": ["k_popcnt", "k_clz"],
     "target_bytes": [7],
     "ladder_bytes": [3, 5],
     "blocking": ["tail"],
     "carriers": ["FRAME", "NAT"],
     "kind": "int", "multi": []},

    {"arm": "FSPECIAL_EST", "instr": "fspecial_est", "stage": 2,
     "kernels": ["k_rsqrt_fast", "k_recip_fast", "k_rsqrt"],
     "target_bytes": [1, 3],
     "ladder_bytes": [4, 5],
     "blocking": ["srcA", "subop"],
     "carriers": ["FRAME", "NAT"],
     "kind": "float", "multi": []},

    {"arm": "IBFE", "instr": "ibfe", "stage": 2,
     "kernels": ["k_bfe", "k_bfe_s"],
     "target_bytes": [8, 2, 6],
     "ladder_bytes": [3, 5],
     "blocking": ["srcA", "b2_bit0", "sign_ext"],
     "carriers": ["FRAME", "NAT"],
     "kind": "int", "multi": []},

    {"arm": "IADD2", "instr": "iadd2", "stage": 2,
     "kernels": ["k_u32add"],
     "target_bytes": [7, 2],
     "ladder_bytes": [3, 4],
     "blocking": ["srcA", "b2_fmt"],
     "carriers": ["FRAME", "NAT"],
     "kind": "int", "multi": []},

    # ---- ARM B tier 2 (anchor-dependent) --------------------------------
    {"arm": "PACKED_HALF2_HI", "instr": "packed_half2_hi", "stage": 3,
     "kernels": ["k_half2"],
     "target_bytes": [1, 3, 4, 5],
     "ladder_bytes": [2],
     "blocking": ["srcA", "srcB", "mods"],
     "carriers": ["FRAME", "NAT"],
     "kind": "float", "multi": [("mods", [4, 5])]},

    {"arm": "BF_ALU", "instr": "bf_alu", "stage": 3,
     "kernels": ["k_bfadd", "k_bfmul"],
     "target_bytes": [3, 4, 5, 6, 7],
     "ladder_bytes": [2],
     "blocking": ["srcA", "srcB", "tail"],
     "carriers": ["FRAME", "NAT"],
     "kind": "float", "multi": [("tail", [5, 6, 7])]},

    {"arm": "BF_FMA_DST", "instr": "bf_fma_dst", "stage": 3,
     "kernels": ["k_bffma"],
     "target_bytes": [6, 7, 8, 9],
     "ladder_bytes": [3, 4],
     "blocking": ["tail"],
     "carriers": ["FRAME", "NAT"],
     "kind": "float", "multi": [("tail", [6, 7, 8, 9])]},
]

# Explicitly OUT of scope, and why -- naming them is part of the result.
OUT_OF_SCOPE = {
    "icmp_pred": "4 blocking fields (`srcA`,`neg`,`srcB`,`opclass`) and the "
                 "predicate is observable only through a divergent block. "
                 "EXP-0169 is concurrently building exactly that carrier "
                 "(`NAT_kcmp`) for `icmp_pred.cond`; duplicating it would put "
                 "two experiments on one instrument for no extra coverage.",
    "funary": "6 blocking fields, and `funary.op` overlaps a set `match` bit "
              "(DEF-0166-1), so its descriptor needs repair before a sweep "
              "means anything.",
    "h_alu_hi_ext / icmpsel / tex_coord_setup / b_alu10_*":
        "8-11 blocking fields each; no single carrier closes them, so they are "
        "not this experiment's lever.",
    "*.dst": "owned by EXP-0168. `dst` bytes ARE swept here as LADDER bytes "
             "(which register slot changed is the detection instrument), but "
             "NO verdict is emitted for any `.dst` field.",
}

# FIELD-SWEEP-PROTOCOL section 3.3 wide-field sample set.
INTERIOR = [0x03, 0x05, 0x0B, 0x17, 0x2D, 0x3B, 0x55, 0x6F,
            0x97, 0xA3, 0xC7, 0xDB, 0xE5, 0xF1, 0xF9, 0xFD]


def wide_values(width):
    mx = (1 << width) - 1
    vals = {0, 1, 2, mx - 1, mx}
    for i in range(width):
        vals.add(1 << i)
    for i, seed in enumerate(INTERIOR):
        v = 0
        for b in range(0, width, 8):
            v |= ((seed + 17 * i + 5 * (b // 8)) & 0xFF) << b
        vals.add(v & mx)
    return sorted(vals)


def build_cases(anchors, stages=(1, 2, 3)):
    """anchors: {arm_carrier_key: {...}} produced by harness/anchors.py.

    Returns a deterministic, frozen-order list of case dicts. A missing anchor
    is NOT an error -- the arm is skipped and reported `not_anchored`, which is
    an honest bound rather than a half-swept arm."""
    cases = []
    idx = 0
    for spec in ARMS:
        if spec["stage"] not in stages:
            continue
        for carrier in spec["carriers"]:
            key = "%s@%s" % (spec["arm"], carrier)
            anc = anchors.get(key)
            if not anc:
                continue
            blk_len = len(bytes.fromhex(anc["block_hex"]))
            tgt = anc["target_off"]          # instruction offset inside block
            ilen = anc["instr_len"]
            for role, blist in (("ladder", spec["ladder_bytes"]),
                                ("target", spec["target_bytes"])):
                for bi in blist:
                    if bi >= ilen:
                        continue
                    for v in range(256):
                        cases.append({
                            "idx": idx, "arm": spec["arm"], "carrier": carrier,
                            "key": key, "instr": spec["instr"],
                            "kind": spec["kind"], "role": role,
                            "mut": [[tgt + bi, v]], "byte_index": bi,
                            "value": v, "blk_len": blk_len,
                        })
                        idx += 1
            for fname, blist in spec["multi"]:
                width = 8 * len(blist)
                for v in wide_values(width):
                    mut = [[tgt + bi, (v >> (8 * k)) & 0xFF]
                           for k, bi in enumerate(blist)]
                    cases.append({
                        "idx": idx, "arm": spec["arm"], "carrier": carrier,
                        "key": key, "instr": spec["instr"],
                        "kind": spec["kind"], "role": "multi",
                        "mut": mut, "byte_index": None,
                        "value": v, "wide_field": fname, "blk_len": blk_len,
                    })
                    idx += 1
    return cases


def matrix_sha256(cases):
    h = hashlib.sha256()
    for c in cases:
        h.update(json.dumps(c, sort_keys=True).encode())
    return h.hexdigest()
