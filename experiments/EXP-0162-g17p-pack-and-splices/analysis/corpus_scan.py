#!/usr/bin/env python3
"""EXP-0162 desk scan of the OWN-MSL corpus (EXP-M4-13-full-corpus/hex, 1080
files compiled from MSL we wrote).  Purely a design aid + A/B evidence base:
histograms the two byte0 groups whose db.json descriptors are contested.

  group A: byte0 == 0x07  (threadgroup_barrier / mem_fence / pixel_order)
  group B: byte0 == 0x57  (vary_store vs the 6-byte fragment kill/mask op)

CLEAN-ROOM: PUBLIC/OWN-SHADER -- reads only this repository's own committed
corpus of shaders compiled from our own MSL. No Apple binary is inspected.
"""
import collections, json, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools" / "agx-isa"))
import isadb  # noqa: E402

HEX = REPO / "experiments" / "EXP-M4-13-full-corpus" / "hex"

def tokens(buf):
    off = 0
    out = []
    while off < len(buf):
        L = isadb.instr_length(buf, off)
        if not L:
            break
        recs, _ = isadb.disassemble(buf[off:off + L])
        m = recs[0]["mnemonic"] if recs else "<none>"
        out.append((off, L, m, buf[off:off + L]))
        off += L
    return out, off

def main():
    g07 = collections.Counter()
    g57 = collections.Counter()
    g57_mn = collections.Counter()
    g07_mn = collections.Counter()
    files07, files57 = collections.Counter(), collections.Counter()
    for p in sorted(HEX.glob("*.hex")):
        buf = bytes.fromhex("".join(p.read_text().split()))
        toks, stop = tokens(buf)
        stage = p.stem.split("__")[-1]
        for (off, L, m, b) in toks:
            if b[0] == 0x07 and len(b) >= 6:
                key = (b[1], b[2], b[3], b[4], b[5], m, stage)
                g07[key] += 1
                g07_mn[m] += 1
                files07[p.stem] += 1
            if b[0] == 0x57 and len(b) >= 6:
                key = (b[1], b[2], b[3], b[4], b[5], m, L, stage)
                g57[key] += 1
                g57_mn[m] += 1
                files57[p.stem] += 1
    print("### byte0 == 0x07 : %d tokens, %d files" % (sum(g07.values()), len(files07)))
    print("  mnemonics:", dict(g07_mn))
    print("  b1   b2   b3   b4   b5   mnemonic              stage        count")
    for k, n in sorted(g07.items(), key=lambda x: -x[1]):
        print("  %02x   %02x   %02x   %02x   %02x   %-20s  %-11s  %d" % (k[0], k[1], k[2], k[3], k[4], k[5], k[6], n))
    print()
    print("### byte0 == 0x57 : %d tokens, %d files" % (sum(g57.values()), len(files57)))
    print("  mnemonics:", dict(g57_mn))
    print("  b1   b2   b3   b4   b5   mnemonic     len  stage        count")
    for k, n in sorted(g57.items(), key=lambda x: -x[1]):
        print("  %02x   %02x   %02x   %02x   %02x   %-12s %2d   %-11s  %d" % (k[0], k[1], k[2], k[3], k[4], k[5], k[6], k[7], n))
    # the discriminator questions
    b2_hist = collections.Counter()
    b5_hist = collections.Counter()
    for k, n in g57.items():
        b2_hist[k[1]] += n
        b5_hist[k[4]] += n
    print("\n0x57 byte+2 histogram:", {("%02x" % k): v for k, v in sorted(b2_hist.items())})
    print("0x57 byte+5 histogram:", {("%02x" % k): v for k, v in sorted(b5_hist.items())})
    b3_hist = collections.Counter()
    b4_hist = collections.Counter()
    for k, n in g07.items():
        b3_hist[k[2]] += n
        b4_hist[k[3]] += n
    print("0x07 byte+3 histogram:", {("%02x" % k): v for k, v in sorted(b3_hist.items())})
    print("0x07 byte+4 histogram:", {("%02x" % k): v for k, v in sorted(b4_hist.items())})

main()
