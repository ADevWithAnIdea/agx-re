#!/usr/bin/env python3
# EXP-0016 in-place byte splicer: copy a serialized archive and overwrite bytes at
# absolute file offsets (OFF=HEX ...), for splice-and-observe HW validation of our
# own compiled shader. CLEAN-ROOM: operates only on our own shdump-produced archive.
import sys, shutil
src, dst = sys.argv[1], sys.argv[2]
shutil.copy(src, dst)
with open(dst, 'r+b') as f:
    for pair in sys.argv[3:]:
        off, val = pair.split('=')
        f.seek(int(off)); f.write(bytes([int(val, 16)]))
print("spliced", dst, sys.argv[3:])
