# EXP-0229 — SIMD extra-operand length pre-registration

Target: Apple A18 Pro / G17P. Clean-room class: OWN-SHADER carrier + GENERATED
instructions + HW-PROBE. No fresh Apple compiler output will be inspected.

## One question

Does bit 7 of `simd_shuffle` byte+9 select a twelve-byte extra-operand form,
instead of the ordinary ten-byte form?

Existing evidence is deliberately separated:

- EXP-0205 directly executed generated ten-byte `simd_shuffle` operations on
  G17P, establishing the base instruction family.
- EXP-0148 found that all 7/7 own-compiler occurrences with byte+9 bit 7 set
  are followed by `02 00`, while 0/120 occurrences with the bit clear are.
  Those seven are exactly the two-source `simd_shuffle_and_fill` / `simd_rotate`
  operations. That is corpus correlation, not a consumed-length measurement.
- The current descriptor always says ten bytes, then tokenizes `02 00` as a
  separate two-byte word. The rejected twelve-byte decoder experiment in
  EXP-0148 only demonstrated a bad descriptor match; round-trip/corpus fit
  cannot decide hardware consumption.

## Generated formula

The ten-byte prefix is assembled from the current independently named fields:

```text
dir       = 0 or 1
mode      = 0x06
cache     = 1
dst       = 0
src       = 2
srctype   = 0
lane      = 2
rtype     = 0
dsthi     = 0x14
rsv9      = 0x11 or 0x91
```

This yields `47/c7 06 56 00 02 00 02 00 14 11/91`. Every bit is generated
from the formula; no instruction byte is copied into a dispatched program.
The only tested distinction is byte+9 bit 7. Other field names and operation
semantics are reused only to construct a legal family member and are not
promoted by this experiment.

Two prefix points are anchored by already committed own-compiler evidence:
`47 06 56 04 02 00 02 08 14 11` is a ten-byte fill-modulo form and
`c7 06 56 04 02 00 02 00 14 91 02 00` is an extra-operand rotate form.
The generated test normalizes unrelated register/width fields and crosses the
bit in both directions; it does not read fresh compiler output.

## Causal length witness

A two-byte generated `mov_imm` begins immediately at offset +10, followed by
independent markers at +12 and +14 and a post marker at +16. The first marker
is run twice with different immediates, so an accidental candidate result
cannot mimic the length signature.

```text
ten bytes consumed:     hit(+10), hit(+12), hit(+14), post(+16)
twelve bytes consumed:  miss(+10), hit(+12), hit(+14), post(+16)
fourteen bytes consumed:miss(+10), miss(+12), hit(+14), post(+16)
sixteen bytes consumed: miss(+10), miss(+12), miss(+14), post(+16)
```

The complete r0-r23 state and all buffers are captured. Registers whose value
the SIMD candidate may alter are modelled unknown; marker registers remain
observable. The ordinary bit-clear form is the positive ten-byte control. A
deliberately wrong marker-value model must be rejected while still inferring
the same hardware length.

## Falsifiable model

- `byte+9 & 0x80 == 0`: exactly 10 bytes.
- `byte+9 & 0x80 != 0`: exactly 12 bytes.
- The rule is independent of `dir` at the two tested direction values and of
  the two first-marker immediates.

Any clean status-OK marker signature inconsistent with this table refutes the
model at that exact generated point. A fault or hang from replacing the two
extension bytes is inconclusive for that case and does not erase the existing
ten-byte fact.

## Pilot and safety

Run the eight combinations `(dir in {0,1}) x (rsv9 in {0x11,0x91}) x
(first immediate in {51,87})`, plus one wrong-model control, after the standard
slot probe. Hang budget is one; all dispatches are serialized. Device
unresponsiveness invokes the plan hard stop: stop immediately, do not attempt
recovery or reboot, preserve the partial artifact, and report blocked.

If the pilot cleanly separates 10/12, freeze the identical matrix and run it
twice in opposite orders. This experiment establishes framing only, not SIMD
semantics, operand meaning, lifecycle, register reach, or the meaning of the
extra two bytes.
