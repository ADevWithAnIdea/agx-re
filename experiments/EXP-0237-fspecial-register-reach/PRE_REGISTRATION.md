# EXP-0237 pre-registration — canonical `fspecial` register reach and lifecycle

Frozen before the first EXP-0237 hardware dispatch. Repository base: `2c043b97`.

## Question

What exact physical GPR sets can the source and destination descriptors of the canonical ten-byte
FP32 direct-round `fspecial` form access on G17P, and what is the source lifecycle including a
source/destination alias?

EXP-0161 recovered the corrected geometry: byte+3 is destination `v >> 1`, byte+5 is source
`v >> 2`, and the source is released. It densely established the safe/invalid destination boundary
but only value-proved destination r1..r14 and source r1,r2,r3,r5,r7,r9,r14. This experiment fills
the value-proof matrix without repeating EXP-0161's destructive r96+ destination region.

## Frozen hypothesis

The generated direct-round recipe is:

```text
fn_hi=0                 # byte0 0x2f direct family
fnclass=0               # direct round family
src_ext=0               # historical name; canonical inert high nibble
src_cache=0x56
dst=(D<<1)|d0           # D=0..95, d0 is inert
src_class=0x02
src=(S<<2)|s01          # S=0..63, s01 is inert
fnsel=0xb0
precsel=0x40
roundmode=0x02          # floor
sched_flag=0
```

Every source is first produced by a generated `device_load` and immediately consumed and checked
by an accepting generated `device_store`, leaving an ordinary materialized GPR before `fspecial`.
For positive finite input `N + 0.5`, the host predicts the exact binary32 result `N`. The source is
released after the read. If source equals destination, release precedes result publication and the
new result wins.

Competing models are direct selection, modulo-16, modulo-32, and modulo-64 aliasing. Every register
that those models distinguish is seeded with a different exact floor result and observed before and
after the instruction.

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

EXP-0161 already swept destination byte values 0..191 densely without a hang and 192..255 densely
in its bounded danger arm. None of 192..255 worked; 45 values produced a genuine contained
`kIOGPUCommandBufferCallbackErrorHang`, while 19 were only observed as innocent victims of their
neighbours' resets. EXP-0138 independently found the same upper-region fault/hang behavior. This
experiment does not cause another 64 reset-producing dispatches merely to repeat that established
boundary. Its destination promotion requires both the new r0..r95 value proof and the cited
EXP-0161 first-invalid evidence.

## Gates and stop rule

- Gate A: exactly one generated ten-byte `fspecial` body with exact requested/actual fields and no
  framing alias.
- Gate B: distinct exact source values, independent fixed readback addresses, poison, sentinel,
  complete relevant pre/post state, and both wrong-oracle controls must discriminate.
- Gate C: the host-computed floor and lifecycle model must match every positive case and distinguish
  direct/modulo candidates where their register numbers differ.
- Gate D: `COPIED=0`, `CARRIER=0`; every `fspecial` byte is generated from the frozen formula.
- Gate E: two quiet opposite-order G17P runs with no unexplained fault, hang, recovery, restart,
  retry, or foreign GPU activity.

Every dispatch has a 20-second watchdog and zero-hang budget. If SSH or the device becomes
unresponsive, stop immediately, preserve evidence, perform no recovery/reboot, and report blocked.

Clean-room provenance: OWN-SHADER + HW-PROBE. Apple binary introspection: **NONE**.
