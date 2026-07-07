#!/usr/bin/env python3
"""RT-ISA-FIX census: quantify the 0x0f exec-mask family fix on the CF corpus.
Tokenizes each kernel BOTH with a reconstructed pre-fix length rule (0f05=8,
no 0f01/0f04, no 0x07 non-0x54 fence) and with the current (fixed) DB, and
reports byte-coverage + 0x0f-family op decode counts."""
import sys, os
sys.path.insert(0, "/Users/user/cleanroom_gpu/tools/agx-isa")
import isadb

HEX = dict(l.split() for l in open(os.path.join(os.path.dirname(__file__), "raw/all_hex.txt"))
           if len(l.split()) == 2)

def prefix_len(buf, off):
    """Reconstruct the PRE-RT-ISA-FIX length behaviour for the 0f/07 families."""
    b0 = buf[off]; b1 = buf[off+1] if off+1 < len(buf) else -1
    b2 = buf[off+2] if off+2 < len(buf) else -1
    if b0 == 0x0f:
        if b1 == 0x00: return 10
        if b1 == 0x05:
            if off+4 < len(buf) and buf[off+4] == 0x8f: return 14
            return 8               # old (wrong) push length
        if b1 == 0x80: return 6
        if b1 == 0x06: return 6
        return None                # 0f01/0f04 unhandled
    if b0 == 0x07 and b2 != 0x54:
        return None                # non-0x54 fence unhandled pre-fix
    return isadb.instr_length(buf, off)

def cover(buf, lenfn, decode=True):
    off = 0; named = 0; f0 = 0; f0dec = 0
    while off < len(buf):
        b0 = buf[off]
        n = lenfn(buf, off)
        if not n or n <= 0 or off+n > len(buf):
            off += 2; continue
        if b0 == 0x0f: f0 += 1
        if decode:
            try:
                isadb.decode_one(buf, off); named += n
                if b0 == 0x0f: f0dec += 1
            except Exception:
                pass
        else:
            named += n
        off += n
    return named, f0, f0dec

print(f"{'kernel':13s} {'B':>5} | pre-fix named% | post-fix named%  0f-ops 0f-decoded")
tot=preN=postN=0; TOTf0=0; TOTf0dec=0
for name, hx in sorted(HEX.items()):
    if not name.startswith("cf"): continue
    b = bytes.fromhex(hx)
    pn,_,_ = cover(b, prefix_len)
    qn,f0,f0dec = cover(b, isadb.instr_length)
    tot += len(b); preN += pn; postN += qn; TOTf0 += f0; TOTf0dec += f0dec
    print(f"{name:13s} {len(b):>5} |  {100*pn/len(b):5.1f}%        |  {100*qn/len(b):5.1f}%         {f0:>4}   {f0dec:>4}")
print("-"*72)
print(f"{'CF CORPUS':13s} {tot:>5} |  {100*preN/tot:5.1f}%        |  {100*postN/tot:5.1f}%         {TOTf0:>4}   {TOTf0dec:>4}")
print(f"\n0x0f exec-mask ops decoded: {TOTf0dec}/{TOTf0} (pre-fix: only 0f00/0f05-call/0f06/0f80 had descriptors)")
