# EXP-0237 results — canonical `fspecial` register reach and lifecycle

**Verdict: PASS on G17P.** In the generated ten-byte direct-round FP32 form, byte+5 directly reads
and releases r0..r63 as `source = byte5 >> 2`; byte+3 directly writes r0..r95 as
`destination = byte3 >> 1`. The source field has no representation for r64..r95. Destination r96
is the first invalid register by EXP-0161's already-complete upper-region sweep. If source equals
destination, result publication follows release and the result wins.

The complete matrix and all controls were frozen at commit `801890fc` before hardware dispatch.

## 1. Generated recipe

```text
fn_hi       = 0
fnclass     = 0
src_ext     = 0
src_cache   = 0x56
dst         = (D << 1) | d0
src_class   = 0x02
src         = (S << 2) | s01
fnsel       = 0xb0
precsel     = 0x40
roundmode   = 0x02
sched_flag  = 0
```

This computes binary32 `floor(source)`. Every generated source is first produced by a
`device_load` and immediately handed to an accepting generated `device_store`, which checks its
exact bits and leaves an ordinary materialized GPR. Inputs are exact positive binary32 values
`N + 0.5`, so the independent host oracle predicts the exact result `N` without an approximate-SFU
tolerance.

Every `fspecial` byte is generated from a documented rule. No Apple instruction field or carrier
field is copied.

## 2. Source descriptor

Both runs densely execute all 256 byte+5 values:

```text
source = byte5 >> 2
byte5 0..255 -> physical r0..r63
```

All **512/512 source cases** across both runs match the exact floor value and complete pre/post
state. Values differing only in bits 0..1 select the same physical source and have the same effect
in this materialized FP32 direct-round form. This is `accepted-inert in this tested envelope`, not
a claim that these bits have no role under other source classes or datapaths.

Every source is released after the read: all 512 post-source observations are zero. Distinct values
in the direct, modulo-16, and modulo-32 candidate registers make alias models distinguishable at
their boundaries. The 8-bit field is exhausted: after spending two low bits below the register
number, it has no encoding for physical r64..r95.

## 3. Destination descriptor and finite boundary

Both runs densely execute the complete safe byte+3 region, values 0..191:

```text
destination = byte3 >> 1
byte3 0..191 -> physical r0..r95
```

All **384/384 destination cases** write the exact independently predicted value to the directly
named physical register. Values differing only in bit 0 select the same destination and have the
same effect in this form.

The upper region was not destructively repeated. EXP-0161 already swept byte+3 values 192..255:
none worked; 45 of 64 produced a genuine contained `ErrorHang`, while 19 were only observed as
innocent victims of their neighbours' resets. EXP-0138 independently found the same boundary.
Thus r95 is maximum valid and r96 is first invalid for this destination role; an emitter must not
encode destination byte values 192..255.

## 4. Alias publication and direct-round semantics

The matrix explicitly tests source=destination at r0, r15, r16, r31, r32, r47, r48, and r63 in
both orders. All **16/16 alias cases** contain the floor result, not zero or the old source. The
state transition is therefore:

```text
read source -> release source -> publish destination
```

The exact outputs also execute the previously unrun EXP-0161 direct-floor refinement: all 912
positive cases across both runs compute the correct direct-round result. This does not characterize
NaN, infinity, denormal, signed-zero, or every rounding-family selector; those remain instruction-
semantics work rather than register-reach claims.

## 5. Formal evidence and gates

- `raw/g17p_e0237_run01`: canonical order, 466 dispatches;
- `raw/g17p_e0237_run02`: reverse order, 466 dispatches.

Each run contains eight slot probes, 456 positive `fspecial` cases, and two wrong-oracle controls.
All 466 command buffers returned `OK`; all positives matched and both controls fired.

| gate | result |
|---|---|
| **A — geometry** | **PASS.** Every main/control body is exactly one generated 10-byte `fspecial`; all 256 source codes and 192 safe destination codes are present, actual bytes decode to the requested values, and opposite-order programs agree case-for-case. |
| **B — detection** | **PASS.** Explicit first-handoff materialization, distinct exact register values, poison, sentinel, complete relevant pre/post observations, and both wrong-oracle controls distinguish the selected register and lifecycle. |
| **C — semantics** | **PASS.** Zero source-value, source-release, destination-value, alias-publication, semantic, undecidable, or cross-run failures. |
| **D — generation** | **PASS.** Per run: `RULE=2392754`, `FREE=60362`, `CARRIER=0`, `COPIED=0`. |
| **E — target/reproduction** | **PASS.** Each run has 45 quiet samples and zero foreign activity, faults, hangs, recoveries, retries, or runner restarts. |

Machine-readable gates are `analysis/formal_result.json` and `analysis/gate_e_result.json`.

## 6. Scope

This closes register reach and the tested release/alias lifecycle for one canonical ten-byte FP32
direct-round form with an ordinary materialized GPR source. It does not transfer the result to
alternate source classes, pending producers, other `fnsel`/`precsel` datapaths, compressed forms,
or the separate `fspecial_est` instruction.

Clean-room provenance: OWN-SHADER + HW-PROBE. Apple binary introspection: **NONE**.
