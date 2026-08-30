#!/usr/bin/env python3
"""tok.py -- EXP-0199 tokenizer helper.  Walks OUR OWN compiled shader bytes with
tools/agx-isa/isadb.py and prints the instruction boundaries, so the frozen
anchor offsets in PRE_REGISTRATION.md are derived mechanically rather than by
hand.  Clean-room: operates only on bytes compiled from our own MSL."""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "..", "tools", "agx-isa"))
import isadb


def walk(b):
    out, off = [], 0
    while off < len(b):
        L = isadb.instr_length(b, off)
        if L is None:
            out.append(dict(off=off, len=None, hex=b[off:off + 8].hex(),
                            mnemonic="LEN_UNKNOWN", fields={}))
            break
        try:
            rec, _ = isadb.decode_one(b, off)
            m, f = rec["mnemonic"], rec["fields"]
        except Exception as e:
            m, f = "NO_DESC(%s)" % e, {}
        out.append(dict(off=off, len=L, hex=b[off:off + L].hex(), mnemonic=m, fields=f))
        off += L
    return out


if __name__ == "__main__":
    hx = sys.argv[1]
    if os.path.exists(hx):
        hx = open(hx).read().strip()
    b = bytes.fromhex(hx)
    recs = walk(b)
    print("total %d bytes, %d instructions" % (len(b), len(recs)))
    for r in recs:
        print("  %4d +%-3s %-34s %s %s" % (r["off"], r["len"], r["hex"], r["mnemonic"],
                                           json.dumps(r["fields"]) if r["fields"] else ""))
