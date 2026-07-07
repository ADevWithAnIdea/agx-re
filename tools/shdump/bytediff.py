#!/usr/bin/env python3
# bytediff.py — differential-compilation helper for AGX byte localization.
#
# Given two hex byte strings (the extracted AGX code of two minimal-pair
# shaders that differ in exactly one source-level thing), align them and report
# which byte offsets changed and the bit-level delta. This is the mechanical
# core of the "compile a minimal pair, diff the bytes, localize the field"
# method (ROADMAP 0.3).
#
# CLEAN-ROOM: operates only on OUR OWN compiled shader bytes.
#
# Usage:
#   python3 bytediff.py A.hex B.hex [labelA labelB]
#   python3 bytediff.py --hex 1ca0.. 1ca1.. [labelA labelB]

import sys


def load(arg):
    if len(arg) and all(c in "0123456789abcdefABCDEF" for c in arg.strip()):
        return bytes.fromhex(arg.strip())
    with open(arg) as f:
        return bytes.fromhex(f.read().strip())


def diff(a, b, la="A", lb="B"):
    out = []
    out.append(f"len({la})={len(a)}  len({lb})={len(b)}")
    if len(a) != len(b):
        out.append("** lengths differ — byte offsets past the first insertion "
                   "may be misaligned; showing positional diff up to min length **")
    n = min(len(a), len(b))
    changed = [i for i in range(n) if a[i] != b[i]]
    if not changed and len(a) == len(b):
        out.append("IDENTICAL")
        return "\n".join(out), changed
    out.append(f"{len(changed)} differing byte position(s) in the common prefix:")
    for i in changed:
        xor = a[i] ^ b[i]
        bits = [str(k) for k in range(8) if (xor >> k) & 1]
        out.append(f"  off 0x{i:04x} ({i:3d}): {a[i]:02x} -> {b[i]:02x}   "
                   f"xor={xor:02x}  bit(s)={','.join(bits)}")
    return "\n".join(out), changed


def main():
    args = sys.argv[1:]
    if args and args[0] == "--hex":
        a = bytes.fromhex(args[1]); b = bytes.fromhex(args[2]); rest = args[3:]
    else:
        a = load(args[0]); b = load(args[1]); rest = args[2:]
    la = rest[0] if len(rest) > 0 else "A"
    lb = rest[1] if len(rest) > 1 else "B"
    text, _ = diff(a, b, la, lb)
    print(text)


if __name__ == "__main__":
    main()
