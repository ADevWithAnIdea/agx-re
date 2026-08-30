#!/usr/bin/env python3
"""EXP-0201 HOST-SIDE ORACLE DISCRIMINATION CHECK -- runs before the freeze.

    python3 analysis/oracle_check.py

`copysign.operands` has already been swept dense on the M4 -- 256 legal values,
256 DISTINCT encodings, no faults, 100 % cross-run agreement -- and it stayed
`untested`, because the sweep produced ONE distinct valid payload against ONE
constant oracle. The binding constraint on that arm is the ORACLE, not the range.

So before any device time this script proves, on the host, that every carrier's
candidate library is actually DISCRIMINATING: that the named functions are
pairwise-distinct 8-lane vectors under the inputs we chose, after any saturation
the carrier applies. If two members collide the inputs are wrong and must be
changed and re-frozen -- a collision means the hardware could produce a
different function and we would score it as the expected one.

It also asserts the two traps that this design is most exposed to:
  * `copysign(a,b)` must differ from `-a` (the naive all-signs-opposite choice
    collides them, and then the library cannot tell "copied the sign" from
    "negated");
  * no library member may be the all-zero vector except `zero` itself, because
    on Apple9 a wrong field value usually yields a SILENT ZERO and a zero-valued
    expectation would score that silent zero as a pass.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "harness"))
import carriers201 as C          # noqa: E402


def check(name, lib):
    errs = []
    seen = {}
    for k, v in sorted(lib.items()):
        key = tuple(v)
        if key in seen:
            errs.append("%s: library members %r and %r are the SAME vector %r"
                        % (name, seen[key], k, v))
        seen[key] = k
        if k != "zero" and all(x == 0.0 for x in v):
            errs.append("%s: member %r is the all-zero vector -- a silent zero "
                        "would score as a pass" % (name, k))
    return errs


def main():
    errs = []
    for cname, spec in sorted(C.CARRIERS.items()):
        errs += check(cname, spec["library"])
        if spec["oracle"] is None or len(spec["oracle"]) != 8:
            errs.append("%s: carrier oracle is not an 8-lane vector" % cname)
    cs = C.copysign_library(C.CS_A, C.CS_B)
    if tuple(cs["copysign(a,b)"]) == tuple(cs["-a"]):
        errs.append("copysign inputs: copysign(a,b) == -a; the library cannot "
                    "distinguish a sign copy from a negation")
    if tuple(cs["copysign(a,b)"]) == tuple(cs["copysign(b,a)"]):
        errs.append("copysign inputs: the two operand ROLE assignments collide")
    if not any(str(x) == "-0.0" for x in C.CS_B):
        errs.append("copysign inputs: no -0.0 sign source")
    for cname in ("f3e_sat", "f3e_chain"):
        lib = C.CARRIERS[cname]["library"]
        if len({tuple(v) for v in lib.values()}) != len(lib):
            errs.append("%s: saturation collapsed the library" % cname)
    fs = C.fspecial_library(C.FS_A, C.FS_B)
    ra, rb = fs["rsqrt(a)"], fs["rsqrt(b)"]
    if any(abs(x - y) <= 1e-3 * max(1.0, abs(x)) for x, y in zip(ra, rb)):
        errs.append("fspecial inputs: rsqrt(a) and rsqrt(b) are too close in "
                    "some lane -- a wrong-register seed could be rescued by the "
                    "Newton-Raphson refinement and read as correct")

    for cname, spec in sorted(C.CARRIERS.items()):
        n = len({tuple(v) for v in spec["library"].values()})
        print("  %-10s library members=%-3d distinct vectors=%-3d %s"
              % (cname, len(spec["library"]), n,
                 "OK" if n == len(spec["library"]) else "<-- COLLISION"))
    if errs:
        print("\nORACLE CHECK FAILED (%d):" % len(errs))
        for e in errs:
            print("  " + e)
        return 3
    print("\noracle_check: all carriers discriminate; inputs may be frozen.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
