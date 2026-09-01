# EXP-0236 results — materialized canonical `falu3` register reach

**Verdict: PASS on G17P.** For EXP-0224's canonical eight-byte retained-source FP32 FMA, source A,
B, and C each directly read ordinary/materialized r0..r63. Encoded source numbers 64..127 execute
and read r0..r63 respectively; physical r64..r95 remains intact. All sources are retained. The
destination nibble directly writes r0..r15.

The sparse protocol was frozen at `e4bb77ff`. Complete confirmation was frozen at `b5116b93`
before formal dispatch.

## 1. Canonical recipe and producer-state boundary

```text
dst       = D
srcA      = (A << 1) | 1
op        = 0x06
srcB      = (B << 1) | 1
ctrl_len  = 0x01
srcC      = C << 1
ctrl      = 0x02
srcmods   = 0xc0
```

EXP-0224 establishes that this computes a genuinely fused binary32 `D=fma(A,B,C)`, retains all
three sources, and publishes the destination after optional releases. EXP-0236 isolates register
reach: each generated source load is first consumed by an accepting generated store, which checks
the exact bits and leaves an ordinary retained GPR before FMA executes.

This distinction resolves EXP-0224's mixed r16..r23 discovery. Those cases fed unresolved pending
loads directly into FMA. With explicit first handoff, every retested r16..r23 case is direct and
exact for A, B, and C. The old mixture is evidence about pending-producer acceptance, not a hole in
ordinary GPR addressing.

## 2. Sources

Each formal run exhausts encoded R=0..127 independently for A, B, and C:

| encoded R | effective physical source | lifecycle |
|---:|---|---|
| 0..63 | rR | read exact; source retained |
| 64..127 | r`(R & 63)` | low alias read and retained; physical high rR, where it exists, unchanged |

All **768/768 source cases** across both runs match. Distinct finite binary32 values in the target
and modulo-16/32/64 candidates make the selected source observable in the fused result. Every r80+
case rejects modulo 16; every r96+ case rejects modulo 32; no r64..r95 case reads its nominal high
physical register. Pre/post observations show no source mutation.

Each canonical source descriptor has exactly 128 register payloads after its parity/class bit is
fixed. Every payload executes. The effective selector ignores descriptor bit 7, so no source code
exists beyond r127. This is an instruction-form addressability limit, not the physical-file limit.

## 3. Destination

Both runs densely test all destination nibbles. All **32/32 destination cases** are exact:

```text
D=0..15 -> physical r0..r15
```

The four-bit field cannot represent r16..r95; there is no runtime first-invalid destination inside
this form's encoding namespace.

## 4. Formal evidence and gates

- `raw/g17p_e0236_run01`: canonical order, 410 dispatches;
- `raw/g17p_e0236_run02`: reverse order, 410 dispatches.

Each run contains eight slot probes, 400 positive FMA cases, and two wrong-oracle controls. Every
command buffer returned `OK`; all 400 positives matched per run and both controls fired.

| gate | result |
|---|---|
| **A — geometry** | **PASS.** Every main/control body is exactly one generated eight-byte `falu3`; opposite-order programs are byte-identical case-for-case, with zero framing errors or aliases. |
| **B — detection** | **PASS.** Every load first hands off through an exact accepting store; distinct source candidates, complete output state, retained-source observations, and two controls distinguish the model. |
| **C — semantics** | **PASS.** Zero source-model failures, exact-high matches, distinguishable modulo-16/32 matches, source mutations, semantic failures, undecidable cases, or cross-run disagreements. |
| **D — generation** | **PASS.** Each run records `RULE=2098008`, `FREE=75622`, `CARRIER=0`, and `COPIED=0`. |
| **E — target/reproduction** | **PASS.** Each run has 41 quiet samples and zero foreign activity, faults, hangs, recoveries, retries, or runner restarts. |

Every committed capture hash agrees with the frozen local harness. Machine-readable gates are
`analysis/formal_result.json` and `analysis/gate_e_result.json`.

## 5. Scope

Together with EXP-0224, this closes a compiler-usable canonical retained FP32 FMA over ordinary
materialized GPRs. It does not close direct consumption of every pending producer, extended or
source-modifier forms, FP16, alternate rounding/exception modes, or noncanonical encodings. The
pending-load question is intentionally handed to the scoreboard protocol rather than encoded as a
false register-access restriction.

Clean-room provenance: OWN-SHADER + HW-PROBE. Apple binary introspection: **NONE**.
