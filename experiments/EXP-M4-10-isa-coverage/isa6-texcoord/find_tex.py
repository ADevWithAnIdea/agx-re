#!/usr/bin/env python3
# Locate the tex_sample bundle in an _agc.main hex string. The bundle is 14 bytes:
#   [companion 4B: b0(low3=5) 0x80 0x0c <result_desc>] [sampler-op 10B ...]
# Task naming: sampler-op byte+K == bundle byte+(4+K).
#   op+2 (dim/variant) = bundle byte+6 ; op+3 (index operand) = bundle byte+7.
# Only inspects OUR OWN compiled shader bytes.
import sys

def find_bundles(mainhex):
    b = bytes.fromhex(mainhex)
    res = []
    for i in range(len(b) - 13):
        if b[i+1] == 0x80 and b[i+2] == 0x0c and (b[i] & 0x07) == 5:
            res.append((i, b[i:i+14]))
    return res

if __name__ == "__main__":
    name = sys.argv[1]
    mainhex = sys.argv[2].strip()
    bs = find_bundles(mainhex)
    if not bs:
        print(f"{name}: NO tex_sample bundle found")
    for off, bb in bs:
        variant = bb[6]   # op+2
        idxop   = bb[7]   # op+3
        rdesc   = bb[3]
        tex_slot = bb[8]
        print(f"{name}: bundle@+0x{off:02x} companion+3(result_desc)=0x{rdesc:02x} "
              f"op+2(variant/dim)=0x{variant:02x} op+3(index)=0x{idxop:02x} "
              f"tex_slot=0x{tex_slot:02x} "
              f"abs_op2_off=0x{off+6:02x} abs_op3_off=0x{off+7:02x} bundle={bb.hex()}")
