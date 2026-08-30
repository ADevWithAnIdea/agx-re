#!/usr/bin/env python3
"""EXP-0162: every byte0==0x57 occurrence in the OWN-MSL corpus with 12 bytes of
context, so the 6-vs-8 byte question can be adjudicated statically before any
splice. CLEAN-ROOM: our own corpus only."""
import collections, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools" / "agx-isa"))
import isadb  # noqa: E402
HEX = REPO / "experiments" / "EXP-M4-13-full-corpus" / "hex"

rows = collections.Counter()
ctxfile = {}
for p in sorted(HEX.glob("*.hex")):
    buf = bytes.fromhex("".join(p.read_text().split()))
    off = 0
    while off < len(buf):
        L = isadb.instr_length(buf, off)
        if not L:
            break
        if buf[off] == 0x57:
            ctx = buf[off:off + 12]
            key = ctx.hex()
            rows[key] += 1
            ctxfile.setdefault(key, p.stem)
        off += L
print("distinct 12-byte contexts: %d" % len(rows))
b5 = collections.Counter()
for k, n in rows.items():
    b5[k[10:12]] += n
print("byte+5:", dict(b5))
print()
print("--- contexts whose byte+5 is NOT 0x40/0x41 (candidate 6-byte fragment op) ---")
for k, n in sorted(rows.items(), key=lambda x: -x[1]):
    if k[10:12] not in ("40", "41"):
        print("  %-24s +6..11=%-12s n=%-4d %s" % (k[:12], k[12:], n, ctxfile[k]))
print()
print("--- byte+6/+7 histogram for byte+5==0x40/0x41 (the VS form) ---")
h = collections.Counter()
for k, n in rows.items():
    if k[10:12] in ("40", "41"):
        h[k[12:16]] += n
for k, n in sorted(h.items(), key=lambda x: -x[1])[:20]:
    print("   +6+7 = %s  n=%d" % (k, n))
print()
print("--- byte+1 low nibble vs byte+5 ---")
cross = collections.Counter()
for k, n in rows.items():
    cross[(int(k[2:4], 16) & 0x0f, k[10:12])] += n
for k, n in sorted(cross.items()):
    print("   b1_lo=%x b5=%s : %d" % (k[0], k[1], n))
