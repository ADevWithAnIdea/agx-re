#!/usr/bin/env python3
"""EXP-0148 -- print a raw byte window and the baseline tokenization around a
given offset of a corpus hex file, so a candidate instruction boundary can be
read directly off the evidence.

Usage: python3 dump_context.py <hexfile-basename> <offset> [window]
"""
import sys, os
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "work", "isa_copy"))
import isadb
HEXDIR = os.path.join(REPO, "experiments", "EXP-M4-13-full-corpus", "hex")

fn, off = sys.argv[1], int(sys.argv[2])
w = int(sys.argv[3]) if len(sys.argv) > 3 else 40
buf = bytes.fromhex(open(os.path.join(HEXDIR, fn)).read().strip())
lo, hi = max(0, off - w), min(len(buf), off + w)
print("file=%s len=%d  window [%d,%d)" % (fn, len(buf), lo, hi))
print("bytes:", " ".join("%02x" % b for b in buf[lo:hi]))
print("marker:", " " * (3 * (off - lo)) + "^^ off=%d" % off)
print("-- baseline tokenization from 0 --")
o = 0
while o < len(buf):
    try:
        rec, L = isadb.decode_one(buf, o)
    except Exception as e:
        print("  @%-5d <GAP> %s  %s" % (o, buf[o:o+8].hex(), str(e)[:70]))
        o += 2
        continue
    mark = "  <<<" if o <= off < o + L else ""
    print("  @%-5d %-22s %s%s" % (o, rec["mnemonic"], rec["hex"], mark))
    o += L
