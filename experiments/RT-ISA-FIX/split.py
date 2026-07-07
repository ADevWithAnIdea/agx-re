#!/usr/bin/env python3
"""Hand-splitter: given a hex string and an explicit list of byte-lengths,
print the tokenization. Used to hand-align CF kernels and derive 0f sub-op lengths."""
import sys

def show(hx, lens):
    b = bytes.fromhex(hx)
    off = 0
    for n in lens:
        tok = b[off:off+n]
        print(f"  +0x{off:03x} len={n:>3} {tok.hex()}")
        off += n
    if off != len(b):
        print(f"  !!! consumed {off} of {len(b)} bytes (leftover {b[off:].hex()})")
    else:
        print(f"  === clean: {off} bytes ===")

if __name__ == "__main__":
    hx = sys.argv[1]
    lens = [int(x) for x in sys.argv[2:]]
    show(hx, lens)
