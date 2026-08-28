#!/usr/bin/env python3
"""tok.py -- EXP-0143 tokenizer helper. Wraps tools/agx-isa/isadb.py so every
byte offset used for splicing is derived from the shared DB, never hand-computed.
CLEAN-ROOM: operates only on bytes compiled from OUR OWN MSL."""
import sys, os, json
_ISA = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'tools', 'agx-isa')
sys.path.insert(0, os.path.abspath(_ISA))
import isadb  # noqa: E402


def tokenize(buf):
    """Return (records, leftover). Each record gains 'off'."""
    recs = []
    off = 0
    while off < len(buf):
        try:
            rec, L = isadb.decode_one(buf, off)
        except ValueError as e:
            return recs, (off, bytes(buf[off:]), str(e))
        rec['off'] = off
        recs.append(rec)
        off += L
    return recs, None


def find(recs, mnemonic):
    return [r for r in recs if r['mnemonic'] == mnemonic]


def field_byte_span(mnemonic, field):
    """Byte offset + length inside the instruction for a whole-byte field."""
    desc = isadb._BY_MNEM[mnemonic]
    for f in desc['fields']:
        if f['name'] == field:
            if f['start'] % 8 or f['width'] % 8:
                return None  # sub-byte field: caller must do a read-modify-write
            return f['start'] // 8, f['width'] // 8
    raise KeyError(f'{mnemonic}.{field}')


def set_field(mnemonic, raw, field, value):
    """Return a copy of `raw` (one instruction) with `field` set to `value`."""
    desc = isadb._BY_MNEM[mnemonic]
    L = desc['length']
    assert len(raw) == L, (len(raw), L)
    v = int.from_bytes(raw, 'little')
    for f in desc['fields']:
        if f['name'] == field:
            mask = ((1 << f['width']) - 1) << f['start']
            v = (v & ~mask) | ((value << f['start']) & mask)
            return v.to_bytes(L, 'little')
    raise KeyError(f'{mnemonic}.{field}')


def main():
    hexs = open(sys.argv[1]).read().strip()
    buf = bytes.fromhex(hexs)
    recs, left = tokenize(buf)
    for r in recs:
        print(f"{r['off']:4d} +{r['length']:2d} {r['hex']:32s} {r['mnemonic']:20s} "
              f"{json.dumps(r['fields'])}")
    if left:
        print(f"LEFTOVER at {left[0]}: {left[1].hex()}  ({left[2]})")
    else:
        print("clean tokenization, 0 leftover")


if __name__ == '__main__':
    main()
