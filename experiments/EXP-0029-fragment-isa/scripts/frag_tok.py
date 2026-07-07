#!/usr/bin/env python3
# Fragment-aware tokenizer. Hypothesized lengths for the fragment-only groups,
# validated by requiring 0 leftover across every fragment _agc.main we compiled.
import sys, os, glob

def flen(buf, off):
    n = len(buf)
    b0 = buf[off]
    b1 = buf[off+1] if off+1 < n else -1
    b2 = buf[off+2] if off+2 < n else -1
    lo = b0 & 0x0f
    if b0 == 0x0e:  return 4                      # stop
    if lo == 0x0c:  return 4                      # preamble/get_sr
    # fragment color store: 0xe7 byte+1==0x06 -> 12; compute device store -> 14
    if b0 == 0xe7:  return 12 if b1 == 0x06 else 14
    # fragment tilebuffer READ (programmable blend / [[color(n)]] input): 0x67 byte+1==0x0e
    if b0 == 0x67:  return 12 if b1 == 0x0e else 14
    # fragment depth / small store 0xd7 byte+1==0x14 (byte+2==0x54) -> 6; else tex write 16
    if b0 == 0xd7:  return 6 if (b1 == 0x14 and b2 == 0x54) else 16
    # fragment memory/attribute family (low-nibble 7): 0x87/0x07 6B, 0x97/0xa7 10B
    if b0 == 0x87 and b2 == 0x54: return 6
    if b0 == 0x07 and b2 == 0x54: return 6
    if b0 == 0x97: return 10
    if b0 == 0xa7 and b2 == 0x54: return 10
    b6 = buf[off+6] if off+6 < n else -1
    # interpolation / coefficient family (low-nibble f), byte+2==0x54 in fragment:
    #   0x2f/0xaf/0x3f = interpolate/perspective; the 8-byte form (byte+6==0x0a) is
    #   the interpolate-at setup (centroid/sample barycentric compute); else 10B.
    if b0 in (0x2f, 0xaf, 0x3f) and b2 == 0x54:
        return 8 if b6 == 0x0a else 10
    if b0 in (0x1f, 0x9f) and b2 == 0x54: return 6
    # fragment sample-position / sample-id preamble reads
    if b0 == 0x04 and b1 != 0xea: return 8       # centroid-position read
    if b0 == 0x03: return 10                      # sample-id / sample-position read
    # float ALU (low-nibble 9): 4 if byte+2==0x38, else 8 if byte+2&2 else 6
    if lo == 0x09:
        if b2 == 0x38: return 4
        return 8 if (b2 & 0x02) else 6
    # texture sample companion (low-nibble 5 + 0x80 0x0c)
    if lo == 0x05 and b1 == 0x80 and b2 == 0x0c: return 14
    if b0 == 0x37:
        return 8 if b2 == 0x56 else 10            # quad-reduce vs derivative
    if b0 in (0x38, 0x39, 0x90, 0x92, 0xb0, 0x18): return 10  # deriv/sample helpers (approx)
    return None

def tok(h):
    buf = bytes.fromhex(h.strip()); off = 0; out = []
    while off < len(buf):
        L = flen(buf, off)
        if not L or off + L > len(buf):
            out.append((off, 2, buf[off:off+2].hex(), "UNK b0=%02x" % buf[off])); off += 2; continue
        out.append((off, L, buf[off:off+L].hex(), "%02x" % buf[off])); off += L
    return out, len(buf)

if __name__ == "__main__":
    paths = sys.argv[1:] or sorted(glob.glob(os.path.join(os.path.dirname(__file__), "..", "raw", "*.frag.hex")))
    total_leftover = 0
    for path in paths:
        h = open(path).read().strip()
        if not h: continue
        recs, nbytes = tok(h)
        unks = [r for r in recs if r[3].startswith("UNK")]
        tail = recs[-1][3] if recs else "-"
        status = "CLEAN" if not unks else "UNK=%d" % len(unks)
        print("%-28s %3dB  %s  last=%s" % (os.path.basename(path).replace('.frag.hex',''), nbytes, status, recs[-1][2] if recs else '-'))
        for r in unks:
            print("     UNK +%03d %s" % (r[0], r[2]))
        total_leftover += len(unks)
    print("\nTOTAL UNKNOWN units:", total_leftover)
