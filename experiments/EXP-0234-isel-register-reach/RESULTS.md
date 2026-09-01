# EXP-0234 results — canonical `isel10` register reach

**Verdict: PASS on G17P.** Each of the canonical ten-byte 32-bit `isel10` source roles directly
reads r0..r63.  Encoded source numbers 64..127 execute and alias r0..r63 respectively; therefore
physical r64..r95 cannot be named by this form.  The destination nibble directly writes r0..r15,
and no destination encoding in this form can name r16..r95.

Pre-registration commit: `30446ab8`.  The equality correction/sparse protocol was frozen as
`e0f2cbb0`; the complete-descriptor confirmation was frozen as `85875905` before formal dispatch.

## 1. Canonical recipe under test

For integer equality `D = (A == B) ? T : F`, retaining all four sources:

```text
dst             = D
cmpA            = (A << 1) | 1
opsel           = 0
cmpB            = (B << 1) | 1
cmp_mode        = 0x06
selTrue         = T << 1
cc              = 7
flags           = 0xc0
selFalse_file   = 0
selFalse        = F << 1
```

EXP-0223 established the operation, condition table, lifecycle controls, load-acceptance mode, and
r0..r23 source envelope.  EXP-0234 changes one register role at a time and closes its complete
canonical descriptor namespace.

## 2. Source result

The two formal runs each contain all 128 encoded register numbers for each source role:

| role | canonical field | direct physical set | high descriptor behavior |
|---|---|---|---|
| compare A | `cmpA=(A<<1)|1` | r0..r63 | A=64..127 reads `r[A & 63]` |
| compare B | `cmpB=(B<<1)|1` | r0..r63 | B=64..127 reads `r[B & 63]` |
| true value | `selTrue=T<<1` | r0..r63 | T=64..127 reads `r[T & 63]` |
| false value | `selFalse=F<<1` | r0..r63 | F=64..127 reads `r[F & 63]` |

All **1,024/1,024 source observations** across both runs match that model.  For high compare cases,
the other comparator contains the predicted low alias's value, so the selected-true result proves
the alias rather than merely showing that the high physical register was not read.  High selected-
value cases expose the aliased value directly.  Every distinguishable r80..r127 case rejects a
modulo-16 interpretation, and r64..r95 cases independently seed and preserve the nominal high
physical register.

The finite resource is completely bounded for this form: each source field is one byte and its
canonical parity leaves exactly 128 encoded register numbers.  All 128 execute.  The register
payload ignores descriptor bit 7, so there is no source-fault code beyond r127; the encoding space
ends there.  This is an addressability limit, not a physical-file limit.

## 3. Destination result

Both runs densely test every destination nibble.  All **32/32 destination observations** are exact:

```text
D=0..15 -> physical r0..r15
```

The destination field is four bits.  Physical r16..r95 are unaddressable in this form; there is no
representable r16 boundary to dispatch and therefore no runtime fault/alias claim beyond the
nibble namespace.

## 4. Formal evidence and gates

- `raw/g17p_e0234_run01`: canonical order, 538 dispatches;
- `raw/g17p_e0234_run02`: reverse order, 538 dispatches.

Each run has eight slot probes, 528 positive instruction cases, and two wrong-oracle controls.
Every command buffer returned `OK`; 528/528 positives matched per run and both controls fired.

| gate | result |
|---|---|
| **A — geometry** | **PASS.** Every main/control body is exactly one generated ten-byte `isel10`; opposite-order programs are byte-identical case-for-case, with no decode or framing alias. |
| **B — detection** | **PASS.** Exact/high/low-alias codewords, alias-targeted compare predicates, complete state, and two wrong-oracle controls distinguish the result. |
| **C — semantics** | **PASS.** Zero model failures, zero exact-high matches, zero distinguishable modulo-16 matches, and zero cross-run observation disagreements. |
| **D — generation** | **PASS.** Each run records `RULE=2767532`, `FREE=91418`, `CARRIER=0`, and `COPIED=0`. |
| **E — target/reproduction** | **PASS.** Each run has 49 quiet samples, zero foreign runners/compiler services, zero faults, hangs, recoveries, retries, or runner restarts. |

Machine-readable gates: `analysis/formal_result.json` and `analysis/gate_e_result.json`.

## 5. Corrections preserved

The initial pre-registration predicted direct r0..r95 sources and r96/r127 faults.  The first
work-only r95 pilot refuted promotion and also exposed that the harness had requested floating
rather than integer equality.  `AMENDMENT-01.md` preserves that result and corrects the selector.
Two corrected sparse opposite-order runs then showed the r64 boundary and high aliasing.
`AMENDMENT-02.md` froze the alias-discriminating full confirmation and retired the fault-boundary
runs before they were dispatched.  No failed hypothesis or diagnostic record was rewritten.

## 6. What this closes, and what it does not

Together with EXP-0223, this closes a compiler-usable canonical ten-byte 32-bit fused compare/select
recipe, its four source access classes, its destination class, and the full finite source encoding
space.  It does not make alternate `isel8`, `isel10_c`, `isel_reg`, immediate, non-GPR-source, or
other noncanonical forms inherit these limits.

Clean-room provenance: OWN-SHADER + HW-PROBE. Apple binary introspection: **NONE**.
