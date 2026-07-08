#!/usr/bin/env python3
# pairdiff.py — compile two of OUR OWN MSL kernels and byte-diff their _agc.main.
# Prints both hex strings, length, and a per-instruction-ish diff. When lengths
# match it lists differing byte offsets; when they differ it prints both and does
# a simple longest-common-prefix / suffix so appended instructions are visible.
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compdump import compile_main

def hx(b): return b.hex()

def diff(a, b):
    n = min(len(a), len(b))
    offs = [i for i in range(n) if a[i] != b[i]]
    # common prefix / suffix
    pre = 0
    while pre < n and a[pre] == b[pre]: pre += 1
    suf = 0
    while suf < n and a[len(a)-1-suf] == b[len(b)-1-suf]: suf += 1
    return offs, pre, suf

def run(pairs, fast_math=True, func="k"):
    for name, sa, sb in pairs:
        A = compile_main(sa, func, fast_math)
        B = compile_main(sb, func, fast_math)
        offs, pre, suf = diff(A, B)
        print(f"### {name}  (fast_math={fast_math})")
        print(f"  A[{len(A)}] {hx(A)}")
        print(f"  B[{len(B)}] {hx(B)}")
        if len(A) == len(B):
            if not offs:
                print("  IDENTICAL")
            else:
                for i in offs:
                    print(f"  @0x{i:02x}: {A[i]:02x} -> {B[i]:02x}  (xor {A[i]^B[i]:02x})")
        else:
            print(f"  LEN DIFF: A={len(A)} B={len(B)}  common_prefix={pre} common_suffix={suf}")
            # show the region of B that is 'extra'
            extra = B[pre:len(B)-suf]
            base_removed = A[pre:len(A)-suf]
            print(f"  A_middle[{len(base_removed)}] {hx(base_removed)}")
            print(f"  B_middle[{len(extra)}] {hx(extra)}")
        print()

if __name__ == "__main__":
    # Usage: pairdiff.py NAME A.metal B.metal [--no-fast-math] [-f func]
    args = sys.argv[1:]
    fm = True; func = "k"
    if "--no-fast-math" in args: fm = False; args.remove("--no-fast-math")
    if "-f" in args:
        i = args.index("-f"); func = args[i+1]; del args[i:i+2]
    name, sa, sb = args[0], args[1], args[2]
    run([(name, sa, sb)], fast_math=fm, func=func)
