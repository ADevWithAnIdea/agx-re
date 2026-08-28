# m4_20260828_run01 — PARTIAL, RETAINED, NOT USED

This capture stopped after **3,137 of 22,237** cases when the HOST ORACLE raised
`OverflowError: float too large to pack with e format` in `oracle.f16_bits`:
Python's `struct.pack('<e')` refuses to encode an fp16 overflow instead of
producing ±inf, and `c_f2h_dst`'s semantic vector deliberately contains 65520.0 —
the exact tie between the largest finite half (65504) and 65536, which
round-to-nearest-even must carry to +inf. The failure is in *our own oracle*, not
in the hardware, the harness, or the GPU: no device misbehaviour occurred and every
periodic baseline check up to the stop had passed.

Per `CODEX.md` ("a partial capture is retained, never reused") this directory is
left exactly as it was written. Its records are **not** used for any verdict and it
is **not** topped up. The fix (an exact integer fp16 RNE encoder handling overflow,
subnormals and NaN, cross-checked against Python's encoder over 20,000 random
bit patterns wherever Python is willing to answer) landed in `harness/oracle.py`,
together with a mandatory pre-flight that evaluates the oracle over *every* case's
input vector before a single dispatch is issued.

The gate pair was re-captured as `m4_20260828_run02` and `m4_20260828_run03`.
