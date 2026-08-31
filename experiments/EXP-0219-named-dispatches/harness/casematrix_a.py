#!/usr/bin/env python3
"""EXP-0219 part-A case matrix (the four `imad` dispatches EXP-0218 named).

Every case is the 12-byte `imad` anchor lifted verbatim from the compiled form
of OUR OWN `kernels/probes_imad.metal`, with ONE OR TWO named bytes replaced:

  byte+7 = (K << 3) | mode        mode is held at 0 (keep the product) in every
                                  case; (b7 & 3) == 3 is the known reproducible
                                  fault and is never dispatched
  byte+8 = 0xd0 | hi3             high nibble held at 0xd (low-32 multiply);
                                  low three bits are the immediate's high bits
                                  in immediate mode and the candidate high bits
                                  of the fetch index in fetch mode
  byte+9                          the addend-source-class selector byte

ARMS

  cross   (C-DAG)   b9 = 0x20..0x2f  x  K = 0..31,  b8 = 0xd0
                    -> A1 (0x22 vs 0x2c separate bit 1 from bit 3)
                    -> A3 (0x2e vs 0x2f at every K, including ODD K)
                    -> A4 (the byte+7 x byte+9 cross product, all 32 K)
  b8imm   (C-DAG and C-CONST)
                    b9 in {0x26, 0x2e}  x  b8 = 0xd0..0xd7  x  K = 0..31
                    -> A2 (the fetch index width) AND its own Gate B control:
                       the SAME b8 low bits in IMMEDIATE mode must form the
                       high three bits of an 8-bit immediate.  If they do, the
                       bits demonstrably reach the instruction, so a zero in
                       fetch mode is a fact about the index/file and not about
                       a dead field.
  cross32 (C-CONST) b9 in {0x2e, 0x2f} x K = 0..31, b8 = 0xd0
                    -> A3 on a SECOND carrier with a completely different file
  ctrl    (both)    Gate B / detection-power controls, dispatched in every run:
                      * the UNMUTATED anchor (must reproduce the baseline)
                      * b9 with bit 5 clear (0x06, 0x0e) at K = 12 -- the
                        documented "the block does not compute" outcome, so the
                        arm is shown able to produce a NON-baseline result by a
                        mechanism independent of the addend
                      * b7 with (b7 & 3) == 1 at K = 12 -- product dropped, so
                        the addend is readable alone

CLEAN-ROOM: OWN-SHADER.  Only our own compiled MSL is read or mutated.
"""
from __future__ import print_function

import hashlib
import json

K_ALL = list(range(32))
B9_CROSS = list(range(0x20, 0x30))
B9_IMM_FETCH = [0x26, 0x2e]
B8_LOW = [0xd0 + i for i in range(8)]
SSETS = [1, 2]


def _mut(anchor, **kw):
    b = bytearray(anchor)
    for k, v in kw.items():
        b[int(k[1:])] = v
    return bytes(b)


def build_cases(anchor_hex, carrier):
    """`anchor` is the 12-byte imad block; `carrier` is 'dag' or 'const'."""
    anchor = bytes.fromhex(anchor_hex)
    assert len(anchor) == 12
    cases = []
    idx = 0

    def add(arm, bytes_, fields, predict, sset):
        nonlocal idx
        cases.append({"idx": idx, "arm": arm, "carrier": carrier,
                      "instr": "imad", "bytes": bytes_.hex(),
                      "fields": fields, "sset": sset, "predict": predict})
        idx += 1

    for sset in SSETS:
        # ---- Gate B / detection-power controls (first in every run) ---------
        add("ctrl", anchor, {"b7": anchor[7], "b8": anchor[8], "b9": anchor[9]},
            "anchor: must reproduce the arm baseline exactly", sset)
        for b9 in (0x06, 0x0e):
            add("ctrl", _mut(anchor, b9=b9),
                {"b7": anchor[7], "b8": anchor[8], "b9": b9},
                "bit5 clear: documented 'block does not compute'", sset)
        for b7m in (0x61, 0x62):      # K = 12, mode = 1 and 2 -> product dropped
            add("ctrl", _mut(anchor, b7=b7m),
                {"b7": b7m, "b8": anchor[8], "b9": anchor[9]},
                "mode 1/2: product dropped, destination IS the addend", sset)

        if carrier == "dag":
            for b9 in B9_CROSS:
                for K in K_ALL:
                    add("cross", _mut(anchor, b7=(K << 3) & 0xFF, b8=0xd0, b9=b9),
                        {"b7": (K << 3) & 0xFF, "b8": 0xd0, "b9": b9, "K": K},
                        "A1/A3/A4 cross product", sset)
        else:
            for b9 in (0x2e, 0x2f):
                for K in K_ALL:
                    add("cross32", _mut(anchor, b7=(K << 3) & 0xFF, b8=0xd0, b9=b9),
                        {"b7": (K << 3) & 0xFF, "b8": 0xd0, "b9": b9, "K": K},
                        "A3 on a second carrier", sset)

        for b9 in B9_IMM_FETCH:
            for b8 in B8_LOW:
                for K in K_ALL:
                    add("b8imm", _mut(anchor, b7=(K << 3) & 0xFF, b8=b8, b9=b9),
                        {"b7": (K << 3) & 0xFF, "b8": b8, "b9": b9, "K": K,
                         "hi3": b8 & 7},
                        "A2 fetch-index width + its immediate-mode control", sset)
    return cases


def matrix_sha256(cases):
    h = hashlib.sha256()
    for c in cases:
        h.update(("%d|%s|%s|%d\n" % (c["idx"], c["arm"], c["bytes"], c["sset"]))
                 .encode())
    return h.hexdigest()


if __name__ == "__main__":
    import sys
    a = sys.argv[1] if len(sys.argv) > 1 else "9f00560002080060d02e0a00"
    for carrier in ("dag", "const"):
        cs = build_cases(a, carrier)
        print(carrier, len(cs), matrix_sha256(cs))
        from collections import Counter
        print("  ", Counter(c["arm"] for c in cs))
