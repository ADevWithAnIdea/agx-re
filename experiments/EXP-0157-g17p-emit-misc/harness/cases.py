#!/usr/bin/env python3
"""EXP-0157 case construction.

The ARM TABLE below is frozen (PRE_REGISTRATION.md section 5); the splice
OFFSETS are not, and must not be: they are resolved on the target by
tokenizing our own compiled carrier, because G17P's compiler lays code out
differently from G16G's and a hard-coded M4 offset would be an automatic stop.

Every case is one value of one field (or one named raw byte of a multi-byte
field) at one resolved anchor. Coverage follows FIELD-SWEEP-PROTOCOL section 3:
a field of width <= 8 is swept over all 2^w values; a wider field gets
boundaries, every power of two, and >= 24 interior samples, plus a DENSE
byte-level sweep of its first two constituent bytes.

CLEAN-ROOM: bytes are produced by mutating the compiled form of our own MSL.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import anchors as A  # noqa: E402  (puts tools/agx-isa on sys.path)

# ---------------------------------------------------------------------------
# The frozen arm table: (arm, carrier, mnemonic, max_anchors)
# ---------------------------------------------------------------------------
ARMS = [
    # -- arm R: the ray-query / ray-marshalling cluster, in the AS carriers --
    ("R", "rq_cdist",  "sr_read_wide",   2),
    ("R", "rq_cprim",  "sr_read_wide",   2),
    ("R", "rq_cdist",  "rtq_dualsrc",    2),
    ("R", "rq_cdist",  "rtq_pred",       2),
    ("R", "rq_cdist",  "rtq_state_move", 2),
    ("R", "rq_cdist",  "ray_move",       2),
    ("R", "rq_cdist",  "ray_move_copy6", 2),
    ("R", "rq_cdist",  "ray_move_zero6", 2),
    ("R", "rq_ccount", "ray_move_zinit", 2),
    ("R", "rq_mprim",  "op04_len8",      2),
    ("R", "rq_mdist",  "op04_len8",      2),
    ("R", "rq_mprim",  "sr_read_wide",   1),
    ("R", "rq_mtype",  "rtq_state_move", 1),
    # -- arm S: SFU / integer-misc, the G17P revalidation of EXP-0146 --------
    ("S", "sfusin",  "n2_op6",           2),
    ("S", "sfusin",  "sfu_marker",       1),
    ("S", "sfumix",  "n2_op6",           2),
    ("S", "sfumix",  "sfu_marker",       2),
    ("S", "sfumix",  "scoreboard_fence", 1),
    ("S", "sfucos",  "n2_op6",           1),
    ("S", "sfucos",  "sfu_marker",       1),
    ("S", "u64eq",   "n2_op6",           1),
    ("S", "u64eq",   "n3_mov",           1),
    ("S", "u64eq",   "scoreboard_fence", 1),
    ("S", "roundm",  "n2_op10",          2),
    # -- arm H: the half-coordinate pair ------------------------------------
    ("H", "h4fma",   "h_coord_hi",       2),
    ("H", "h3mix",   "h_coord_hi",       1),
    ("H", "h3mix",   "h_coord_hi_ext",   2),
]

# POST-FREEZE EXPLORATORY EXTENSION (recorded as a deviation in RESULTS.md).
# `EXTRA_ARMS="X:rq_all:compute_fence_scoped:6,..."` appends arms that were not
# in the frozen table. Their records carry their own arm letter so they can
# never be confused with the pre-registered arms R/S/H, and their verdicts are
# reported separately.
import os as _os
for _e in filter(None, _os.environ.get("EXTRA_ARMS", "").split(",")):
    _a, _c, _m, _n = _e.split(":")
    ARMS.append((_a, _c, _m, int(_n)))

# Descriptors with NO fields in db.json (rtq_pred, sfu_marker). db.json models
# them as byte-invariant tokens; EXP-0146 already refuted that for sfu_marker on
# M4. For these we sweep every byte of the instruction as `byte+N`, which is
# both the emittability question and the db-defect question.
BYTE_CENSUS = {"rtq_pred": 4, "sfu_marker": 2}


def field_values(width):
    """FIELD-SWEEP-PROTOCOL section 3.3."""
    if width <= 8:
        return list(range(1 << width))
    hi = (1 << width) - 1
    vals = {0, 1, 2, hi - 1, hi, hi >> 1, (hi >> 1) + 1}
    b = 1
    while b <= hi:
        vals.add(b)
        vals.add(b - 1)
        b <<= 1
    step = max(1, hi // 25)
    for k in range(1, 26):
        vals.add((k * step) ^ 0x5A5A5A5A5A5A & hi)
        vals.add(k * step)
    return sorted(v & hi for v in vals)


def byte_span(mnemonic, field):
    """If `field` is byte-aligned and wider than 8 bits, return the list of its
    constituent byte indices; else []."""
    start, width = A.field_span(mnemonic, field)
    if width <= 8 or start % 8 or width % 8:
        return []
    return [start // 8 + k for k in range(width // 8)]


def instr_fields(mnemonic):
    import isadb
    for ins in isadb.DB:
        if ins["mnemonic"] == mnemonic:
            return [(f["name"], f["start"], f["width"]) for f in ins["fields"]]
    raise LookupError(mnemonic)


def instr_length(mnemonic):
    import isadb
    for ins in isadb.DB:
        if ins["mnemonic"] == mnemonic:
            return ins["length"]
    raise LookupError(mnemonic)


def liveness_cases(mnemonic, anchor_off, ibytes):
    """The two pre-registered anchor controls (PRE_REGISTRATION section 5.2).
    L1 changes the opcode group; L2 erases the instruction. An anchor is LIVE
    iff either changes the output away from the carrier's own baseline."""
    l1 = bytes([ibytes[0] ^ 0x01]) + ibytes[1:]
    l2 = b"\x00" * len(ibytes)
    return [
        {"field": "_L1_opcode_group", "value": ibytes[0] ^ 0x01,
         "splice": [(anchor_off, l1.hex())], "ibytes": l1.hex(),
         "expect_match": False,
         "note": "liveness control L1: byte0 ^= 0x01 (different opcode group)"},
        {"field": "_L2_erase", "value": 0,
         "splice": [(anchor_off, l2.hex())], "ibytes": l2.hex(),
         "expect_match": False,
         "note": "liveness control L2: every byte of the instruction -> 0x00"},
    ]


def sweep_cases(mnemonic, anchor_off, ibytes, dense_bytes=2):
    """All field cases for one LIVE anchor."""
    out = []
    flds = instr_fields(mnemonic)
    for name, start, width in flds:
        for v in field_values(width):
            nb = A.set_field(ibytes, mnemonic, name, v)
            if nb == ibytes:
                continue                       # value is the baseline itself
            out.append({"field": name, "value": v,
                        "splice": [(anchor_off, nb.hex())], "ibytes": nb.hex(),
                        "expect_match": None, "note": ""})
        for k, bi in enumerate(byte_span(mnemonic, name)[:dense_bytes]):
            for v in range(256):
                b = bytearray(ibytes)
                if bi >= len(b):
                    break
                if b[bi] == v:
                    continue
                b[bi] = v
                out.append({"field": "%s.byte+%d" % (name, bi), "value": v,
                            "splice": [(anchor_off, bytes(b).hex())],
                            "ibytes": bytes(b).hex(), "expect_match": None,
                            "note": "raw byte %d of multi-byte field %s" % (bi, name)})
    if not flds and mnemonic in BYTE_CENSUS:
        for bi in range(BYTE_CENSUS[mnemonic]):
            for v in range(256):
                b = bytearray(ibytes)
                if b[bi] == v:
                    continue
                b[bi] = v
                out.append({"field": "byte+%d" % bi, "value": v,
                            "splice": [(anchor_off, bytes(b).hex())],
                            "ibytes": bytes(b).hex(), "expect_match": None,
                            "note": "db.json declares NO fields for this "
                                    "descriptor; every byte is swept instead"})
    return out


def baseline_case(carrier):
    return {"field": "_baseline", "value": 0, "splice": [], "ibytes": "",
            "expect_match": True, "note": "unmutated carrier"}
