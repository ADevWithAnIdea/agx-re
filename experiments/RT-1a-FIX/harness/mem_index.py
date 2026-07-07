#!/usr/bin/env python3
# RT-1a-FIX item 1: INDEPENDENT HW re-validation of the memory-op index register.
# Claim under test (from RT-1a): for device_load/store (0x67/0xe7), the INDEX
# register that supplies a[idx] is byte+5 (NOT byte+1, NOT byte+6); byte+6 is
# inert; byte+1 is the address-space bit; and there is an additive immediate
# index-offset field at ~byte+9 bit7 / byte+10 / byte+11.
#
# Method: bank.metal loads out[gid]=a[i0] where i0..i3 come from idxbuf. We fill
# a[j]=100*j+3 (so an INDEX change shows as a[k]=100k+3 and de-confounds a
# dest/store-register change, which would show raw small register contents), and
# idxbuf={40,3,77,12} (so r0=i0=40,r1=i1=3,r2=i2=77,r3=i3=12). Sweeping one byte
# of the a[i0] load and reading out0 tells us exactly what that byte controls.
import sys, os, subprocess, struct, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from persistrun import PersistRunner

SRC = "bank.metal"; ARCH = "bank.bin"
MAIN_OFF = int(subprocess.check_output(
    ["python3", "agxparse.py", ARCH, "--locate", "_agc.main"], text=True).split()[0])

# locate the a[i0] load: byte0==0x67 and byte+4 (base_slot)==0x02 (buffer 2 = a)
base = open(ARCH, "rb").read()
def find_load():
    # walk from MAIN_OFF using a tiny length rule for the ops we care about
    return None
# We know from tokenization it is at MAIN+0x1c; assert base_slot byte is 0x02.
INSN_OFF = 0x1c
assert base[MAIN_OFF + INSN_OFF] == 0x67, "not a load at +0x1c"
assert base[MAIN_OFF + INSN_OFF + 4] == 0x02, "base_slot != buffer2(a)"

# inputs
NA = 128
open("a_ramp.bin", "wb").write(struct.pack("<%dI" % NA, *[100*j+3 for j in range(NA)]))
open("idx.bin", "wb").write(struct.pack("<4I", 40, 3, 77, 12))
ins = {2: "a_ramp.bin", 3: "idx.bin"}
outs = {0: 4, 1: 4}

def a_index(v):
    if v >= 3 and (v - 3) % 100 == 0:
        return (v - 3) // 100
    return None

r = PersistRunner(source=SRC, function="k", fast_math=False,
                  agxrun_persist="./agxrun_persist")
results = {}
def sweep(name, byteoff, values):
    print(f"\n## sweep {name}: a[i0]-load byte+{byteoff} (abs +0x{INSN_OFF+byteoff:x})")
    rows = []
    for v in values:
        sp = bytearray(base); sp[MAIN_OFF + INSN_OFF + byteoff] = v
        open("sp.bin", "wb").write(sp)
        resp = r.request(archive="sp.bin", grid=1, tg=1, ins=ins, outs=outs, timeout=6)
        if resp["status"] != "OK":
            print(f"  0x{v:02x} {resp['status']}")
            rows.append((v, resp["status"], None, None))
            continue
        o0 = struct.unpack("<I", resp["outs"][0])[0]
        k = a_index(o0)
        note = f"a[{k}]" if k is not None else ("RAW/dest?" if o0 < 256 else "other")
        print(f"  0x{v:02x} OK  o0={o0:<8d} {note}")
        rows.append((v, "OK", o0, k))
    results[name] = rows
    return rows

try:
    sweep("byte+5 (index reg)", 5, list(range(0, 6)) + [0x80, 0x81, 0x82])
    sweep("byte+6 (inert?)", 6, [0x00, 0x01, 0x02, 0x10, 0x20, 0x40, 0x80, 0xff])
    sweep("byte+1 (space)", 1, [0x00, 0x01, 0x02, 0x03, 0x04])
    # immediate index-offset field: original byte+9/10/11 = 01/00/40 for this load.
    sweep("byte+9 (offset bit7?)", 9, [0x01, 0x81])
    sweep("byte+10 (offset?)", 10, [0x00, 0x01, 0x02, 0x03])
    sweep("byte+11 (offset?)", 11, [0x40, 0x41, 0x42, 0x44])
finally:
    r.close()

open("mem_index_results.json", "w").write(json.dumps(results, indent=0))
print("\nWROTE mem_index_results.json")
