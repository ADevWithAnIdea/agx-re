# EXP-0238 pre-registration — canonical `cvt_f2i` register reach and lifecycle

Frozen before the first EXP-0238 hardware dispatch. Repository base: `9f9933b5`.

## Question

What exact physical GPR sets can the source and destination descriptors of the canonical ten-byte
FP32-to-signed-I32 `cvt_f2i` form access on G17P, and what is the source lifecycle including a
source/destination alias?

EXP-0168 located both descriptor bytes and densely exercised the destination byte. Direct audit of
its immutable `g17p_20260830_run02` and `run03` raw rows shows that values 0..191 execute, while
values 192..255 produce `ErrorHang` in all four carrier/run observations except one independently
labelled `InnocentVictim`. Its 16-register observation window could not prove the exact physical
destination for high valid values. This experiment fills the exact value-proof matrix without
repeating the destructive region.

## Frozen hypothesis

The generated signed FP32-to-I32 recipe is:

```text
mode=0x56
dst=(D<<1)|d0           # D=0..95, d0 is inert in this form
src_class=0x02
src=(S<<2)|s01          # S=0..63, s01 is inert in this form
cvtop=0xb4
signflag=0x48
dst_class=0x03
b9=0
```

Every source is first produced by a generated `device_load` and immediately consumed and checked
by an accepting generated `device_store`, leaving an ordinary materialized GPR before `cvt_f2i`.
For positive finite binary32 input `N + 1.5`, the independent host oracle predicts signed I32
`N + 1`, because conversion rounds toward zero. The source is released after the read. If source
equals destination, release precedes result publication and the integer result wins.

Competing models are direct selection, modulo-16, modulo-32, and modulo-64 aliasing. Every register
that those models distinguish is seeded distinctly and observed before and after the instruction.

## Frozen matrix

- Source byte+5: all 256 encodings, dense. Expected mapping `S = v >> 2`, directly covering
  physical r0..r63 four times. The byte has no encoding for physical r64..r95.
- Destination byte+3 safe region: all 192 encodings, dense. Expected mapping `D = v >> 1`, directly
  covering physical r0..r95 twice.
- Alias publication: source=destination at r0,r15,r16,r31,r32,r47,r48,r63.
- Two wrong-oracle controls, one source and one destination, must fail the semantic comparison.
- Eight descriptor-slot probes precede every run.

The formal matrix therefore has 456 positive cases, two controls, and eight slot probes: 466
dispatches per run. It is run twice, canonical and reverse order, under measured quietness.

## Finite-boundary treatment

The source descriptor's complete 8-bit namespace is exhausted here. Its maximum directly named
source is r63; r64 cannot be represented by this form.

EXP-0168 already dispatched every destination byte value on two `cvt_f2i` carriers in each of two
G17P runs. All 0..191 values executed; all 192..255 values are invalid and almost uniformly report
`ErrorHang` (one observation is an `InnocentVictim` caused by the neighbouring recovery). This
experiment does not intentionally submit those known-invalid encodings again. Destination
promotion requires both the new r0..r95 exact-value proof and the cited EXP-0168 first-invalid
evidence.

## Gates and stop rule

- Gate A: exactly one generated ten-byte `cvt_f2i` body with exact requested/actual fields and no
  framing alias.
- Gate B: distinct exact source values, independent fixed readback addresses, poison, sentinel,
  complete relevant pre/post state, and both wrong-oracle controls must discriminate.
- Gate C: the host-computed truncation and lifecycle model must match every positive case and
  distinguish direct/modulo candidates where their register numbers differ.
- Gate D: `COPIED=0`, `CARRIER=0`; every `cvt_f2i` byte is generated from the frozen formula.
- Gate E: two quiet opposite-order G17P runs with no unexplained fault, hang, recovery, restart,
  retry, or foreign GPU activity.

Every dispatch has a 20-second watchdog and zero-hang budget. If SSH or the device becomes
unresponsive, stop immediately, preserve evidence, perform no recovery/reboot, and report blocked.

Clean-room provenance: OWN-SHADER + HW-PROBE. Apple binary introspection: **NONE**.
