#!/usr/bin/env python3
# Tokenize a fragment/vertex _agc.main hex with the current agx-isa DB length rule,
# printing each instruction (byte0 group, length, decode) and flagging UNKNOWN groups.
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "tools", "agx-isa"))
import isadb

def tok(h):
    buf = bytes.fromhex(h.strip())
    off = 0
    out = []
    while off < len(buf):
        L = isadb.instr_length(buf, off)
        if L is None or L <= 0 or off + L > len(buf):
            # unknown: emit the leader byte and advance by 2 (parcel) to keep scanning
            out.append((off, 2, buf[off:off+2].hex(), "UNKNOWN(b0=%02x)" % buf[off]))
            off += 2
            continue
        chunk = buf[off:off+L]
        try:
            rec = isadb.decode_one(buf, off)
            m = rec.get("mnemonic", "?") if rec else "?"
        except Exception as e:
            m = "decodeERR"
        out.append((off, L, chunk.hex(), m))
        off += L
    return out

if __name__ == "__main__":
    for path in sys.argv[1:]:
        h = open(path).read().strip()
        print("== %s (%d bytes) ==" % (os.path.basename(path), len(h)//2))
        for off, L, hx, m in tok(h):
            flag = "  <<<" if m.startswith("UNKNOWN") else ""
            print("  +%03d %2dB  %-28s %s%s" % (off, L, hx, m, flag))
        print()
