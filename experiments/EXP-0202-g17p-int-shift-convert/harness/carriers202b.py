#!/usr/bin/env python3
"""EXP-0202 AMENDMENT (v3) carrier additions. Extends `carriers202.CARRIERS`.

`harness/carriers202.py` is NOT edited: run02 executed against its frozen hash
and must stay reproducible byte-for-byte. This module imports it and adds the
carriers `RE_EXPERIMENT_PROCESS_CORRECTIONS.md` sections 3(B) and 6 require:

* five OPERAND-PROVENANCE carriers for `shift_amt_move.src_flag` -- ALU,
  system-value, SIMD-lane, overwrite/intervening-ALU and control-flow-merge
  producer classes, because a bit modelled as a SOURCE-CLASS selector must be
  repeated across producer classes before any inertness reading means anything;
* one WIDE-READBACK carrier for `ibitcount.dst`, a second disjoint register /
  readback plan so a redirected destination cannot masquerade as inertness.

Every oracle is host-computed in Python from the same arithmetic as the MSL.
CLEAN-ROOM: OWN-SHADER.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import carriers202 as C     # noqa: E402

M32 = C.M32
SAM2 = "kernels/k_sam2_202.metal"
PC2 = "kernels/k_pc2_202.metal"
A = C.A_ROT
B = C.B_AMT
AI = C.A_INT


def _c(metal, func, oracle, inputs, doc, **kw):
    d = dict(C.STD)
    d.update({"metal": metal, "func": func, "oracle": oracle,
              "inputs": inputs, "doc": doc})
    d.update(kw)
    return d


IN_A = {1: ("a_rot.bin", C.pack_u32(A))}
IN_A_B = {1: ("a_rot.bin", C.pack_u32(A)), 2: ("b_amt.bin", C.pack_u32(B))}
IN_AI = {1: ("a_int.bin", C.pack_u32(AI))}


def _cf_amt(t):
    return ((B[t] * 2) & 31) if (B[t] & 1) else ((B[t] + 5) & 31)


NEW = {
 "sam_alu": _c(SAM2, "k_sam_alu",
               [C.rotl(A[t], ((A[t] * 3 + 1) & M32) & 31) for t in range(8)],
               IN_A, "amount produced by an ALU chain (producer class: ALU)"),
 "sam_sys": _c(SAM2, "k_sam_sys",
               [C.rotl(A[t], (t * 3 + 1) & 31) for t in range(8)],
               IN_A, "amount produced by a SYSTEM VALUE (thread position)"),
 "sam_lane": _c(SAM2, "k_sam_lane",
                [C.rotl(A[t], (t + 1) & 31) for t in range(8)],
                IN_A, "amount produced by the SIMD lane index "
                      "(grid 8 / tg 8, so lane index == thread index)"),
 "sam_ovr": _c(SAM2, "k_sam_ovr",
               [C.rotl(A[t], B[t] & 31) ^ ((((A[t] ^ 0x5A5A5A5A) * 7 + 3) & M32) & 1)
                for t in range(8)], IN_A_B,
               "amount defined, then an intervening independent ALU op, then used"),
 "sam_cf": _c(SAM2, "k_sam_cf",
              [C.rotl(A[t], _cf_amt(t)) for t in range(8)], IN_A_B,
              "amount defined on BOTH sides of a control-flow merge"),
 "pc_dump": _c(PC2, "k_pc_dump",
               [v for t in range(4) for v in
                (bin(AI[t] & M32).count("1"),
                 (AI[t] * 3 + 1) & M32,
                 (AI[t] ^ 0x5A5A5A5A) & M32,
                 (AI[t] + 0x01010101) & M32)],
               IN_AI,
               "WIDE READBACK: four mutually distinct live values per lane at "
               "FIXED store indices, so a redirected ibitcount destination shows "
               "up as one of the other three words taking the count",
               nwords=24, sent_word=16, val_words=list(range(16)),
               tail_words=list(range(17, 24)), grid=4, tg=4),
}

for _k, _v in NEW.items():
    C.CARRIERS[_k] = _v
