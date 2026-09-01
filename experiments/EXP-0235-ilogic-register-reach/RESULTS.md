# EXP-0235 results — canonical `ilogic` register reach and XOR lifecycle

**Verdict: PASS on G17P.** Both source roles of the canonical ten-byte 32-bit XOR directly read
and release r0..r63. Encoded source numbers 64..127 execute, read, and release r0..r63
respectively; physical r64..r95 cannot be named by either role and remains intact. The destination
nibble directly writes r0..r15 after both source releases.

The sparse protocol was frozen at `c19af0bb`. The complete-descriptor confirmation was frozen at
`2e6062c3` before formal dispatch.

## 1. Canonical recipe

For `D = A XOR B`:

```text
dst        = D
srcA       = (B << 1) | 1   # db field contains semantic B
op_base    = 0
srcB       = (A << 1) | 1   # db field contains semantic A
lut_a_sel  = 2
lut_a_free = 0
lut_a_z    = 0
lut_b      = 8
z6         = 0
outmod     = 0x80
z8         = 0
z9         = 0
```

EXP-0226 established the operand-label swap, donor-free selector recipe, dependency-derived source
release, and destination publication after releases. EXP-0235 changes one register role at a time
and closes the finite register namespace for this canonical XOR form.

## 2. Sources and lifecycle

Each formal run exhausts encoded R=0..127 independently for semantic A and semantic B:

| encoded R | effective physical source | post-read state |
|---:|---|---|
| 0..63 | rR | effective source is zero (released) |
| 64..127 | r`(R & 63)` | aliased low source is zero; physical high rR, where it exists, is unchanged |

All **512/512 source cases** across both runs match this model. Distinct values in the physical
target and modulo-16/32/64 candidates make the alternatives observable wherever their register
numbers differ. No high case reads/releases its nominal physical r64..r95; every r80+ case rejects
modulo 16, and every r96+ case rejects modulo 32. Both source roles behave identically.

The complete canonical descriptor byte has 128 register payloads because its low parity/class bit
is fixed. Every payload executes. Descriptor bit 7 is ignored by the GPR selection, leaving no
additional source code beyond r127 to test. This is an instruction-form addressability limit, not
the 96-register physical-file limit.

## 3. Destination

Both runs densely test all 16 destination nibbles. All **32/32 destination cases** are exact:

```text
D=0..15 -> physical r0..r15
```

No encoding in the four-bit field can name r16..r95, so there is no representable first-invalid
destination to dispatch in this form.

## 4. Formal evidence and gates

- `raw/g17p_e0235_run01`: canonical order, 282 dispatches;
- `raw/g17p_e0235_run02`: reverse order, 282 dispatches.

Each run contains eight slot probes, 272 positive instruction cases, and two wrong-oracle controls.
Every command buffer returned `OK`; all 272 positives matched per run and both controls fired.

| gate | result |
|---|---|
| **A — geometry** | **PASS.** Every main/control body is exactly one generated ten-byte `ilogic`; opposite-order programs are byte-identical case-for-case, with zero framing errors or aliases. |
| **B — detection** | **PASS.** Distinct codewords, pre/post target and alias observations, complete output state, and two wrong-oracle controls distinguish value and release behavior. |
| **C — semantics** | **PASS.** Zero source-model failures, exact-high matches, distinguishable modulo-16/32 matches, semantic failures, undecidable cases, or cross-run observation disagreements. |
| **D — generation** | **PASS.** Each run records `RULE=1461588`, `FREE=43018`, `CARRIER=0`, and `COPIED=0`. |
| **E — target/reproduction** | **PASS.** Each run has 35 quiet samples and zero foreign activity, faults, hangs, recoveries, retries, or runner restarts. |

Every committed capture hash agrees with the frozen local harness. Machine-readable gates are
`analysis/formal_result.json` and `analysis/gate_e_result.json`.

## 5. Tokenizer correction

Before dispatch, the offline gate found that a valid high source descriptor (`srcA=0xe1`, encoded
r112) collided with an older R9 trailing-word prefix heuristic. The experiment froze a narrow
precedence rule for the exact canonical XOR tail. Hardware executed all affected words as one
ten-byte `ilogic`; the main tokenizer now carries that rule and three hardware-executed regression
canaries, including the `0xe1` collision.

## 6. Scope

Together with EXP-0226, this closes a compiler-usable canonical 32-bit XOR recipe and its register
lifecycle. The source reach applies to this canonical ten-byte logic family. It does not silently
transfer to immediate, non-GPR, alternate-tail, compressed, 64-bit, or other low-nibble-b forms.
EXP-0226's function-dependent release rule remains the authority for LUT functions that do not
depend upon both inputs.

Clean-room provenance: OWN-SHADER + HW-PROBE. Apple binary introspection: **NONE**.
