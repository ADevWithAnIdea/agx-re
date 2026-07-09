#!/usr/bin/env python3
# tokenize_trace.py -- detailed single-stream tokenization using the shared
# tools/agx-isa DB, printed inline (named / length-only / UNDECODED per position).
# Used to reverse-engineer residue: compile an ISOLATED single-op shader, extract
# its AGX bytes, and trace here to see the mystery op cleanly bracketed by
# known-length ops (the byte count between anchors gives the op's true length).
#
# Usage:
#   tokenize_trace.py <stage-name>          # trace a corpus hex/ stage
#   tokenize_trace.py --hex <file.hex>      # trace an arbitrary extracted hexfile
#
# CLEAN-ROOM: every byte traced is the compiled form of MSL we wrote (OWN-SHADER).
import sys, os
# --- portable repo root (repo was relocated; anchor to a sentinel, not a hardcoded path) ---
import os
def _repo_root(start):
    d = os.path.abspath(start)
    while d != os.path.dirname(d):
        if os.path.isfile(os.path.join(d, 'CLAUDE.md')) and os.path.isdir(os.path.join(d, 'tools', 'agx-isa')):
            return d
        d = os.path.dirname(d)
    raise RuntimeError('repo root not found from ' + start)
_REPO = _repo_root(os.path.dirname(os.path.abspath(__file__)))
# --- end portable repo root ---
sys.path.insert(0, os.path.join(_REPO, 'tools', 'agx-isa'))
import isadb

HEXDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hex')

def trim_padding(b):
    while len(b) >= 2 and b[-2:] == b'\x06\x00':
        b = b[:-2]
    return b

def _named_at(buf, off, n):
    L = isadb.instr_length(buf, off)
    if L is None or off + L > n:
        return None, None
    try:
        rec, _ = isadb.decode_one(buf, off)
        return L, rec['mnemonic']
    except ValueError:
        return L, None

def trace(b):
    b = trim_padding(b)
    n = len(b)
    off = 0
    while off < n:
        L, mn = _named_at(b, off, n)
        if L is not None:
            tag = mn if mn else '<len%d>' % L
            note = '' if mn else '   (length-only, no descriptor)'
            print(f"{off:4x}: {b[off:off+L].hex(' '):42s} {tag}{note}")
            off += L
            continue
        start = off
        off += 2
        while off < n:
            L2, mn2 = _named_at(b, off, n)
            if mn2 is not None:
                break
            off += 2
        print(f"{start:4x}: {b[start:off].hex(' '):42s} *** UNDECODED {off-start}B ***")

def main():
    if len(sys.argv) >= 3 and sys.argv[1] == '--hex':
        h = open(sys.argv[2]).read().strip()
    else:
        h = open(os.path.join(HEXDIR, sys.argv[1] + '.hex')).read().strip()
    trace(bytes.fromhex(h))

if __name__ == '__main__':
    main()
