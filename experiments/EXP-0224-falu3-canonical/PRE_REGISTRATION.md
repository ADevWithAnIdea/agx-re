# EXP-0224 — generated FP32 fused multiply-add recipe

Frozen before the first EXP-0224 dispatch.  Target: Apple A18 Pro / G17P.  Clean-room class:
OWN-SHADER carrier + generated instructions + HW-PROBE.  No fresh Metal FMA compilation or machine
code inspection is allowed until the generated hypotheses below have all failed at least twice.

## Compiler question

Can a backend generate, without a donor token, a register-register FP32 instruction computing:

```text
D = fma(A, B, C)
```

with independently selectable sources and destination, complete-state-correct source lifetime,
load/ALU provenance, aliases, and multi-operation chains?

## Generated hypotheses

The existing structural descriptor establishes field positions but is not itself an emission
proof.  Generate every field from these formulas:

```text
dst=D
srcA=(A<<1)|1
srcB=(B<<1)|1
srcC=C<<1
ctrl=0x02
srcmods=0xc0
```

Cross three fixed-control candidates, none copied from a compiler token during this experiment:

- H1: `op=0x1e`, `ctrl_len=0x81`;
- H2: `op=0x06`, `ctrl_len=0x81` (same FMA low class, release-like high bits clear);
- H3: `op=0x06`, `ctrl_len=0x01` (same eight-byte length class, high bit clear).

Each candidate runs two asymmetric operand assignments, a relocated destination, and a
destination/source alias.  Full r0..r23 state is predicted.  A candidate is safe only when the
arithmetic result and every retained source match; a right destination with destroyed sources is
not a pass.  Wrong-C and wrong-operation host refuters must mismatch.

Only after H1/H2/H3 all fail in two generated attempts may fresh own-MSL nominate another point.
Compiler bytes may never be copied into the generated program or counted as hardware proof.

## Gates and next phase

- Gate A records requested fields, actual dispatched bytes, independent field decode, and the
  whole-program walk. Any disagreement or alias fails.
- Gate B uses unique register seeds, poisoned output, a separate sentinel, and a complete state
  dump.
- Gate C compares against an independent host FP32 model and includes wrong-model refuters.
- Gate D requires `COPIED=0`, `CARRIER=0`.
- Gate E promotion requires two quiet G17P runs in different orders.

If a safe point exists, freeze an amendment before mapping lifecycle/load controls and before the
formal source/destination/DAG suite.  Existing dense field sweeps may seed hypotheses, but this
experiment must execute the complete generated recipe itself.
