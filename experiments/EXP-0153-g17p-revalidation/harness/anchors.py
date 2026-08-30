#!/usr/bin/env python3
"""EXP-0153 anchor resolution + generic field setter.

Verbatim in behaviour from `EXP-0139-m4-emit-ialu/harness/anchors.py` (same
project, same rules), with the tools path made relocatable for the neo.

An "anchor" is one instruction inside a program compiled from OUR OWN MSL,
identified by (function, mnemonic, occurrence) and resolved AT RUN TIME by
tokenizing `_agc.main` with `tools/agx-isa` (read-only). Offsets are never
hard-coded: if a compiler revision -- or a different target's compiler --
moves the instruction, resolution moves with it, and the frozen contract's
recorded anchor bytes are what the run is gated on. That property is exactly
what makes this file safe to reuse against G17P's compiler.

CLEAN-ROOM: the only machine code inspected is the compiled form of our own
MSL. No Apple binary is disassembled.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import isa_helpers as H  # noqa: E402  (puts tools/agx-isa on sys.path)
import isadb  # noqa: E402


def tokenize(main_bytes):
    """Tokenize with tools/agx-isa. `isadb.disassemble` terminates with an
    `<unknown>` record (mnemonic `<unknown>`, `length` None, no `fields`) when
    it cannot decode; that record is returned as a token with length None so a
    caller can SEE where tokenization stopped. A carrier that does not tokenize
    end-to-end is a recorded observation about this target's compiler output,
    not a harness error -- the splice anchors we need all precede the stop."""
    recs, leftover = isadb.disassemble(main_bytes)
    out = []
    off = 0
    for r in recs:
        ln = r.get("length")
        out.append((off, r["mnemonic"], ln, dict(r.get("fields") or {})))
        if not ln:
            break
        off += ln
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
    raise LookupError("anchor %s#%d not found (leftover=%d)"
                      % (mnemonic, occurrence, len(leftover)))


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
    `isadb` itself uses -- verified by `check_field_setter()` below, which the
    gated run calls before its first case."""
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


def check_field_setter(instr_bytes, mnemonic):
    """Round-trip assertion: for every field of `mnemonic`, setting it to its
    own current value must be a no-op, and setting it to ~value must read
    back. Raises on any disagreement between our setter and isadb."""
    for ins in isadb.DB:
        if ins["mnemonic"] != mnemonic:
            continue
        for f in ins["fields"]:
            name, w = f["name"], f["width"]
            cur = get_field(instr_bytes, mnemonic, name)
            if set_field(instr_bytes, mnemonic, name, cur) != instr_bytes:
                raise AssertionError("setter not idempotent on %s.%s" % (mnemonic, name))
            alt = (~cur) & ((1 << w) - 1)
            if get_field(set_field(instr_bytes, mnemonic, name, alt),
                         mnemonic, name) != alt:
                raise AssertionError("setter/getter disagree on %s.%s" % (mnemonic, name))
        return True
    raise LookupError("mnemonic %s not in db.json" % mnemonic)
