#!/usr/bin/env python3
import sys, os
HEXDIR="/Users/user/asahi_re/public/gpu/experiments/EXP-M5-19-rt-as-load/hex"
def load(fn):
    with open(os.path.join(HEXDIR, fn+".hex")) as f:
        return bytes.fromhex(f.read().strip())

fn=sys.argv[1]
b=load(fn)
print(f"# {fn}: {len(b)} bytes")

# 1. rt_intersect ops: byte+1 == 0xea (any byte0 low-nibble 0x4)
print("## rt_intersect (byte+1==0xea):")
for i in range(len(b)-1):
    if b[i+1]==0xea and (b[i]&0x0f)==0x4:
        print(f"  @{i:#06x}: {b[i:i+8].hex()}")

# 2. m5_addr_gen: byte+2==0x03 with byte0 low-nibble 0xf (?f .. 03 ..)
print("## m5_addr_gen candidates (byte0 lo-nib 0xf, byte+2==0x03):")
for i in range(len(b)-3):
    if (b[i]&0x0f)==0x0f and b[i+2]==0x03:
        print(f"  @{i:#06x}: {b[i:i+4].hex()}  (byte0={b[i]:#04x} slot_b1={b[i+1]:#04x} idx_b3={b[i+3]:#04x})")

# 3. m5_load leaders: byte0 in {0x18,0x38,0x58,0x78} and byte+2==0x10
print("## m5_load candidates (byte0 in 18/38/58/78, byte+2==0x10):")
for i in range(len(b)-3):
    if b[i] in (0x18,0x38,0x58,0x78) and b[i+2]==0x10:
        print(f"  @{i:#06x}: {b[i:i+10].hex()}")
