# EXP-0239 pre-registration — canonical `cvt_i2f` register reach and lifecycle

Frozen before the first EXP-0239 hardware dispatch. Repository base: `e218d305`.

## Question

What exact physical GPR sets can the source and destination descriptors of the canonical eight-byte
signed-I32-to-FP32 `cvt_i2f` form access on G17P, what is the source lifecycle including a
source/destination alias, and is destination r96 the first invalid encoding for this form?

Existing byte-diff work locates byte+3 as `dst<<1` and byte+5 as `src<<2`; M4 sweeps and limited
register windows do not prove exact G17P physical reach. The 96-entry physical GPR file makes the
destination boundary a finite resource. Unlike EXP-0238, there is no already-complete G17P
destructive upper-region sweep for this exact instruction, so the first invalid value is tested in
separate captures after the clean positive matrix.

## Frozen hypothesis

The generated signed I32-to-FP32 recipe is:

```text
mode=0x56
dst=(D<<1)|d0           # D=0..95, d0 is inert in this form
src_class=0x02
src=(S<<2)|s01          # S=0..63, s01 is inert in this form
cvtop=0xac
signflag=0x60
```

Every source is first produced by a generated `device_load` from the authored integer buffer and
immediately consumed and checked by an accepting generated `device_store`, leaving an ordinary
materialized GPR before `cvt_i2f`. The input for register R is positive signed I32 `257 + R`, which
is exactly representable as binary32; the independent host oracle predicts the exact binary32
bits. The source is released after the read. If source equals destination, release precedes result
publication and the FP32 result wins.

Competing models are direct selection, modulo-16, modulo-32, and modulo-64 aliasing. Every register
that those models distinguish is seeded distinctly and observed before and after the instruction.

## Frozen positive matrix

- Source byte+5: all 256 encodings, dense. Expected mapping `S = v >> 2`, directly covering
  physical r0..r63 four times. The byte has no encoding for physical r64..r95.
- Destination byte+3 safe region: all 192 encodings, dense. Expected mapping `D = v >> 1`, directly
  covering physical r0..r95 twice.
- Alias publication: source=destination at r0,r15,r16,r31,r32,r47,r48,r63.
- Two wrong-oracle controls, one source and one destination, must fail the semantic comparison.
- Eight descriptor-slot probes precede every run.

The formal positive matrix has 456 positive cases, two controls, and eight slot probes: 466
dispatches per run. It is run twice, canonical and reverse order, under measured quietness.

## Frozen first-invalid boundary

Only after both positive runs and their formal gate pass, destination byte value 192 (`D=96`) is
submitted once per isolated capture, with eight slot probes before it and no later GPU dispatch.
The frozen prediction is a command-buffer error whose OS class contains `ErrorHang`, followed by
one GPU recovery and a responsive device. Two isolated captures must agree. No other value in the
known-dangerous 192..255 region is submitted: the question is the first-invalid boundary, not a
repeat of an already-established physical-file fact 64 times.

If either first-invalid dispatch makes SSH or the device unresponsive, stop immediately, preserve
all evidence, perform no recovery/reboot, and report blocked. If it executes successfully, the r96
boundary hypothesis is refuted and the upper range must be mapped under a new pre-registration.

## Gates

- Gate A: exactly one generated eight-byte `cvt_i2f` body with exact requested/actual fields and no
  framing alias.
- Gate B: distinct exact source values, independent fixed readback addresses, poison, sentinel,
  complete relevant pre/post state, and both wrong-oracle controls must discriminate.
- Gate C: the host-computed signed-I32-to-FP32 and lifecycle model must match every positive case
  and distinguish direct/modulo candidates where their register numbers differ.
- Gate D: `COPIED=0`, `CARRIER=0`; every `cvt_i2f` byte is generated from the frozen formula.
- Gate E: two quiet opposite-order positive runs with no unexplained fault, hang, recovery,
  restart, retry, or foreign GPU activity.
- Boundary gate: both isolated byte-192 captures produce the frozen `ErrorHang` classification,
  each followed by exactly one recorded recovery and an independently responsive-device check.

Every dispatch has a 20-second watchdog. Clean positive captures have zero-hang budget. Boundary
captures intentionally admit only the one pre-registered command-buffer error.

Clean-room provenance: OWN-SHADER + HW-PROBE. Apple binary introspection: **NONE**.
