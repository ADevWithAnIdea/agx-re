# EXP-0238 results — canonical `cvt_f2i` register reach and lifecycle

**Verdict: PASS on G17P.** In the generated ten-byte signed FP32-to-I32 form, byte+5 directly
reads and releases r0..r63 as `source = byte5 >> 2`; byte+3 directly writes r0..r95 as
`destination = byte3 >> 1`. The source field has no representation for r64..r95. Destination r96
is the first invalid register by direct audit of EXP-0168's complete destination sweep. If source
equals destination, result publication follows release and the integer result wins.

The complete matrix and all controls were frozen at commit `b0549ad0` before hardware dispatch.

## 1. Generated recipe

```text
mode        = 0x56
dst         = (D << 1) | d0
src_class   = 0x02
src         = (S << 2) | s01
cvtop       = 0xb4
signflag    = 0x48
dst_class   = 0x03
b9          = 0
```

Equivalently: `27 07 56 (D<<1) 02 (S<<2) b4 48 03 00`. This converts binary32 to signed I32 with
round-toward-zero truncation. Every generated source is first produced by a `device_load` and
immediately handed to an accepting generated `device_store`, which checks its exact bits and leaves
an ordinary materialized GPR. Inputs are exact positive binary32 values `N + 1.5`, so the
independent host oracle predicts integer `N + 1` exactly.

Every instruction byte is generated from a documented rule. No Apple instruction field or carrier
field is copied.

## 2. Source descriptor

Both runs densely execute all 256 byte+5 values:

```text
source = byte5 >> 2
byte5 0..255 -> physical r0..r63
```

All **512/512 source cases** across both runs produce the exact truncated integer in the selected
destination. Values differing only in bits 0..1 select the same physical source and have the same
effect in this materialized canonical form. This is `accepted-inert in this tested envelope`, not a
claim about other source classes or pending-producer forms.

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

All **384/384 destination cases** write the exact independently predicted integer to the directly
named physical register. Values differing only in bit 0 select the same destination and have the
same effect in this form.

The upper region was not destructively repeated. EXP-0168 already dispatched every destination
byte value on two `cvt_f2i` carriers in each of two G17P runs. Direct audit of its raw records shows
all values 0..191 execute. The 256 carrier/run observations of values 192..255 contain 255
`ErrorHang` results and one recovery-adjacent `InnocentVictim`; none works. Thus r95 is the maximum
valid destination and r96 is first invalid for this role. An emitter must not encode destination
byte values 192..255.

## 4. Release and alias publication

The matrix explicitly tests source=destination at r0, r15, r16, r31, r32, r47, r48, and r63 in
both orders. All **16/16 alias cases** contain the converted integer result, not zero or the old
floating-point source. The state transition is therefore:

```text
read source -> release source -> publish destination
```

The exact positive inputs also reproduce truncation toward zero over all 912 positive cases. This
does not characterize negative overflow, NaN, infinity, denormals, unsigned conversion, other
widths, or alternate mode/class selectors; those remain instruction-semantics/form work rather
than register-reach claims.

## 5. Formal evidence and gates

- `raw/g17p_e0238_run01`: canonical order, 466 dispatches;
- `raw/g17p_e0238_run02`: reverse order, 466 dispatches.

Each run contains eight slot probes, 456 positive `cvt_f2i` cases, and two wrong-oracle controls.
All 466 command buffers returned `OK`; all positives matched and both controls fired.

| gate | result |
|---|---|
| **A — geometry** | **PASS.** Every main/control body is exactly one generated 10-byte `cvt_f2i`; all 256 source codes and 192 safe destination codes are present, actual bytes decode to the requested values, and opposite-order programs agree case-for-case. |
| **B — detection** | **PASS.** Explicit first-handoff materialization, distinct exact register values, poison, sentinel, complete relevant pre/post observations, and both wrong-oracle controls distinguish the selected register and lifecycle. |
| **C — semantics** | **PASS.** Zero source-value, source-release, destination-value, alias-publication, semantic, undecidable, or cross-run failures. |
| **D — generation** | **PASS.** Per run: `RULE=2435196`, `FREE=60434`, `CARRIER=0`, `COPIED=0`. |
| **E — target/reproduction** | **PASS.** Each run has 45 quiet samples and zero foreign activity, faults, hangs, recoveries, retries, or runner restarts. |

Machine-readable gates are `analysis/formal_result.json` and `analysis/gate_e_result.json`.

## 6. Scope

This closes register reach and the tested release/alias lifecycle for one canonical ten-byte
materialized-source signed FP32-to-I32 form. It does not transfer the result to unsigned, half-
width, integer-to-float, pending-producer, compressed, or alternate conversion forms.

Clean-room provenance: OWN-SHADER + HW-PROBE. Apple binary introspection: **NONE**.
