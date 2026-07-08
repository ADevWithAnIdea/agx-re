#!/usr/bin/env python3
# tp.py — test length-rule overrides against the corpus census (M4 + A18).
# Overrides are predicate functions run BEFORE the original instr_length.
import sys
sys.path.insert(0, '/Users/user/cleanroom_gpu/tools/agx-isa')
import isadb, ab

_orig = isadb.instr_length
def b(buf, off, k): return buf[off+k] if off+k < len(buf) else -1

# ---- unified low-nibble-2 integer compare/minmax/select/carry group ----------
# high nibble of byte0 = destination register (r0..r15); length keyed on byte+2
# (op-select) with byte+3 disambiguation for the 0x27 coord/quotient split.
def low2_len(buf, off):
    b1=b(buf,off,1); b2=b(buf,off,2); b3=b(buf,off,3); b4=b(buf,off,4)
    if b2==0x27 and b3==0x81 and b4==0x22:
        return 10                     # rt_transform_test (existing)
    ln = b2 & 0x0f
    if ln == 0x0d:  return 14          # icmpsel const-select (0x1d,0x2d)
    if b2 in (0x1e,0x2e,0x3e,0x26,0x36,0x35): return 6   # iminmax / carry_gen
    if b2 == 0x27:  return 10 if b3==0x80 else 8          # coord-madd(10) / quotient-select(8)
    if ln in (0x07,0x0f,0x05):  return 10                # register-select cmpsel/fcmpsel
    if ln == 0x0e:  return 6
    return 6                            # default short

def patched(buf, off=0):
    b0=buf[off]
    if (b0 & 0x0f)==0x02:
        return low2_len(buf, off)
    return _orig(buf, off)

if __name__ == '__main__':
    isadb.instr_length = patched
    ab.report('low2   ')
    isadb.instr_length = _orig
    ab.report('baseline')
