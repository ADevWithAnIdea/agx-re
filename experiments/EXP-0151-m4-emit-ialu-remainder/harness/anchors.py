#!/usr/bin/env python3
"""EXP-0139 anchor resolution.

An "anchor" is one instruction inside a program compiled from OUR OWN MSL
(`kernels/ialu_probes.metal`), identified by (function, mnemonic, occurrence)
and resolved AT RUN TIME by tokenizing `_agc.main` with `tools/agx-isa`
(read-only). Offsets are never hard-coded: if a compiler revision moves the
instruction, resolution moves with it and the frozen contract's recorded
anchor bytes are what the run is gated on.

CLEAN-ROOM: the only machine code inspected is the compiled form of our own
MSL. No Apple binary is disassembled.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "tools" / "agx-isa"))
import isadb  # noqa: E402


def tokenize(main_bytes):
    recs, leftover = isadb.disassemble(main_bytes)
    out = []
    off = 0
    for r in recs:
        out.append((off, r["mnemonic"], r["length"], dict(r["fields"])))
        off += r["length"]
    return out, leftover


def find(main_bytes, mnemonic, occurrence=0):
    """Return (offset, length, fields) of the `occurrence`-th `mnemonic`."""
    toks, leftover = tokenize(main_bytes)
    n = 0
    for off, mn, ln, fl in toks:
        if mn == mnemonic:
            if n == occurrence:
                return off, ln, fl
            n += 1
    raise LookupError("anchor %s#%d not found (leftover=%d)" % (mnemonic, occurrence, len(leftover)))


def field_span(mnemonic, field):
    """(start_bit, width) of `field` in db.json's descriptor for `mnemonic`."""
    for ins in isadb.DB:
        if ins["mnemonic"] == mnemonic:
            for f in ins["fields"]:
                if f["name"] == field:
                    return f["start"], f["width"]
            raise LookupError("field %s.%s not in db.json" % (mnemonic, field))
    raise LookupError("mnemonic %s not in db.json" % mnemonic)


def set_field(instr_bytes, mnemonic, field, value):
    """Return a copy of `instr_bytes` with `field` set to `value`.

    Bit numbering follows db.json's own convention (start = bit index into the
    little-endian byte string, bit i = byte i//8, bit i%8), the same convention
    `isadb` itself uses -- verified by the round-trip assertion in
    `casematrix.check_field_setter()`."""
    start, width = field_span(mnemonic, field)
    b = bytearray(instr_bytes)
    for k in range(width):
        bit = start + k
        byte, sh = bit // 8, bit % 8
        if byte >= len(b):
            raise ValueError("field %s.%s bit %d past instruction length %d"
                              % (mnemonic, field, bit, len(b)))
        b[byte] = (b[byte] & ~(1 << sh)) | (((value >> k) & 1) << sh)
    return bytes(b)


def get_field(instr_bytes, mnemonic, field):
    start, width = field_span(mnemonic, field)
    v = 0
    for k in range(width):
        bit = start + k
        v |= ((instr_bytes[bit // 8] >> (bit % 8)) & 1) << k
    return v
