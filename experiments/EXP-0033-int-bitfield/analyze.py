#!/usr/bin/env python3
# analyze.py -- host-side: parse raw/hex_dump.log, tokenize each _agc.main with
# the READ-ONLY agx-isa length rule + decoder, print a compact instruction view
# focused on the novel ALU op(s). Uses instr_length() to step past ops the DB
# does not yet name, so we can locate new opcodes/lengths.
import os, sys, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
ISA = os.path.abspath(os.path.join(HERE, "..", "..", "tools", "agx-isa"))
sys.path.insert(0, ISA)
import isadb  # READ-ONLY

BORING = {"get_sr", "device_load", "device_store", "stop", "uniform_mov"}

# Local length overrides for EXP-0033-discovered forms the shipped rule mislengths.
def local_len(main, off):
    b0 = main[off]
    b1 = main[off+1] if off+1 < len(main) else -1
    b2 = main[off+2] if off+2 < len(main) else -1
    # 0x27/0xa7 count/reverse/convert family: length is a per-byte+1 FORM field.
    if b0 == 0xa7:
        if b1 in (0x04, 0x05, 0x07): return 8   # revbits(04)/count(05)/i2f(07)
        return 10 if (b1 & 1) else 12
    if b0 == 0x27:
        if b1 == 0x07: return 10                 # f2i
        if b1 in (0x00, 0x10): return 12
        return 8                                  # popcount/count/unary
    # 0x2b shift/bit prep stage (ctz, register shifts). 10 bytes observed.
    if b0 == 0x2b:
        return 10
    # native-half ALU 0x10 group (mirror of 0x11), same length bit as 0x09.
    if b0 == 0x10:
        return 8 if (b2 & 0x02) else 6
    return None

def tokenize(main):
    out = []
    off = 0; n = len(main)
    while off < n:
        L = local_len(main, off)
        if L is None:
            try:
                L = isadb.instr_length(main, off)
            except Exception:
                L = None
        if L is None:
            out.append((off, None, "?", main[off:].hex())); break
        raw = main[off:off+L]
        name = "<unk>"
        opm = None
        try:
            rec, _ = isadb.decode_one(main, off)
            name = rec["mnemonic"]; opm = rec.get("op_mnemonic")
        except Exception:
            name = "<unk>"
        out.append((off, L, name + (f"[{opm}]" if opm else ""), raw.hex()))
        off += L
    return out

def load_dump(path):
    kernels = {}
    name = None; cur = {}
    for line in open(path):
        line = line.rstrip("\n")
        if line.startswith("KERNEL "):
            name = line[7:]; cur = {}
        elif line.startswith("STATUS "):
            cur["status"] = line[7:]
        elif line.startswith("MAIN "):
            cur["main"] = bytes.fromhex(line[5:])
        elif line.startswith("CONST "):
            cur["const"] = bytes.fromhex(line[6:])
        elif line == "ENDK":
            kernels[name] = cur
    return kernels

def main():
    path = os.path.join(HERE, "raw", "hex_dump.log")
    kernels = load_dump(path)
    only = sys.argv[1:] if len(sys.argv) > 1 else None
    for name, k in kernels.items():
        if only and name not in only:
            continue
        if k.get("status") != "OK" or "main" not in k:
            print(f"### {name}: {k.get('status')}")
            continue
        toks = tokenize(k["main"])
        # novel = non-boring ops
        novel = [t for t in toks if t[2].split("[")[0] not in BORING]
        print(f"### {name}  ({len(k['main'])}B, {len(toks)} instrs)")
        for off, L, nm, hx in toks:
            star = "  " if nm.split("[")[0] in BORING else "* "
            print(f"  {star}+{off:#04x} {str(L):>4}  {nm:24s} {hx}")
        print()

if __name__ == "__main__":
    main()
