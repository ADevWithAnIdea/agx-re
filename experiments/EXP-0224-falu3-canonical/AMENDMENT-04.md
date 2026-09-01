# AMENDMENT-04 — narrow the `n3_mov` fallback after EXP-0230

This is a post-result claim correction, not a change to EXP-0224's frozen experiment or its raw
evidence. EXP-0230 subsequently tested `n3_mov` with all 96 physical GPRs independently live and
proved the exact source-addressing boundary that EXP-0174's 16-register carrier could not prove.

EXP-0224's canonical FP32 FMA result over r0..r15 remains unchanged. Its original fallback claim
was too broad:

- `n3_mov` directly reads only r0..r63. Source descriptors 64..127 alias modulo 64; they do not
  read physical r64..r95.
- `n3_mov` writes only r0..r15 in this compact form.
- Therefore two half moves provide a tested 32-bit transfer from r0..r63 into r0..r15, but do not
  provide low-to-high, high-to-low from r64..r95, or high-to-high transfer.
- An FMA operand held in r16..r63 can be staged into r0..r15. An operand held in r64..r95 cannot
  be staged with this form. Likewise, the compact FMA result cannot be moved to r16..r95 with this
  form.

The wider native FMA encoding and any wider move or memory-mediated transfer remain open hardware
questions. Until one of those paths is proved, EXP-0224 establishes a canonical low-bank FMA, not
arbitrary-program emittability.

Evidence: EXP-0230's broad and focused formal pairs, including independently materialized r92..r95,
select the modulo-64 source model with zero mismatches and refute direct-96 and zero-above-limit
models.
