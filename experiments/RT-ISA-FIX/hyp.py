#!/usr/bin/env python3
"""Hypothesis tokenizer: import the current isadb.instr_length but override the
0x0f family + 0x07 fence lengths with the hypothesis under test, then tokenize all
CF kernels and report clean/dirty + list every 0f/07/32 op."""
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

def hyp_len(buf, off):
    b0 = buf[off]
    b1 = buf[off+1] if off+1 < len(buf) else -1
    b2 = buf[off+2] if off+2 < len(buf) else -1
    b4 = buf[off+4] if off+4 < len(buf) else -1
    # ---- 0x0f exec-mask family (hypothesis) ----
    if b0 == 0x0f:
        if b1 == 0x00: return 10          # jump (unconditional / back-edge)
        if b1 == 0x01: return 10          # conditional forward jump / else / loop-guard
        if b1 == 0x05:
            if b4 == 0x8f: return 14      # direct CALL
            return 4                       # mask push (if-enter)
        if b1 == 0x06: return 6           # reconverge / pop
        if b1 == 0x80: return 6           # break/predication mask op (hypothesis)
        if b1 == 0x04: return 6           # ? (hypothesis)
        if b1 == 0x8a: return 6           # ? (hypothesis)
        return None
    # ---- 0x07 fence family: byte+2 non-0x54 variants (hypothesis) ----
    if b0 == 0x07:
        if b2 == 0x54: return isadb.instr_length(buf, off)  # existing handling
        return 4                           # fence byte+2 in {0x00,0x02,0x80,...}
    return isadb.instr_length(buf, off)

def toks(hx):
    b = bytes.fromhex(hx)
    off = 0; out = []
    while off < len(b):
        n = hyp_len(b, off)
        if n is None or n <= 0:
            out.append((off, None, b[off:off+2].hex())); off += 2; continue
        out.append((off, n, b[off:off+n].hex())); off += n
    return out, len(b)

hexes = {}
with open(os.path.join(os.path.dirname(__file__), "raw/all_hex.txt")) as f:
    for line in f:
        p = line.split()
        if len(p) == 2: hexes[p[0]] = p[1]

focus = sys.argv[1] if len(sys.argv) > 1 else None
for name, hx in sorted(hexes.items()):
    if not name.startswith("cf"): continue
    if focus and focus not in name: continue
    tk, total = toks(hx)
    consumed = sum(n for _,n,_ in tk if n)
    nones = sum(1 for _,n,_ in tk if not n)
    clean = (consumed == total and nones == 0)
    print(f"\n===== {name} ===== total={total} clean={clean} NONEs={nones}")
    for off, n, tok in tk:
        b0 = tok[:2]
        flag = ""
        if b0 == "0f": flag = f"  <0F b1={tok[2:4]}>"
        elif b0 == "07": flag = f"  <07 b2={tok[4:6] if len(tok)>=6 else '?'}>"
        elif b0 == "32": flag = "  <32 CARRY>"
        elif b0 == "8f": flag = "  <8F cf>"
        ls = str(n) if n else "NONE"
        print(f"  +0x{off:03x} len={ls:>4} {tok}{flag}")
