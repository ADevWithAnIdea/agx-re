# EXP-0235 pre-registration — canonical `ilogic` register reach

Frozen before the first EXP-0235 hardware dispatch. Repository base: `7de48457`.

## Question

What exact physical GPR sets can the canonical ten-byte 32-bit two-input LUT instruction read
through each semantic source role and write through its destination on G17P? What does every finite
source descriptor tier do to both the value and EXP-0226's dependency-derived source release?

EXP-0226 already proves the donor-free table for all 16 boolean functions, the semantic-A/db-srcB
and semantic-B/db-srcA operand mapping, destination publication after releases, and the rule that
the LUT releases exactly the source operands on which the selected function depends. EXP-0235 uses
XOR so both source roles are read and released, and changes one register role at a time.

## Frozen sparse hypothesis

For the canonical XOR recipe, each source descriptor directly reads r0..r63. Encoded register
numbers 64..127 alias r0..r63 respectively, and the aliased physical source—not the nominal high
register—is released after the read. The four-bit destination directly writes exactly r0..r15.

The generated fields are:

```text
dst=D
srcA=(semantic_B<<1)|1
op_base=0
srcB=(semantic_A<<1)|1
lut_a_sel=2, lut_a_free=0, lut_a_z=0
lut_b=8, z6=0, outmod=0x80, z8=0, z9=0
```

Before dispatch, offline self-test found that canonical semantic-B descriptor `0xe1` (encoded
r112) collides with the frozen decoder's older R9 trailing-word prefix table. The experiment
therefore freezes a narrow precedence hypothesis: a low-nibble-b word with odd byte+1/byte+3 and
the exact canonical XOR tail `1e ?? 02 08 00 80 00 00` is one ten-byte `ilogic`. Hardware Gate A
must validate this framing for every generated case; the rule is not evidence about any broader
low-nibble-b namespace.

## Sparse matrix and detection

Each source role tests encoded R={0,23,24,31,32,47,48,63,64,79,80,95,96,111,112,127}. The
destination tests r0..r15 densely. Two wrong-oracle controls must fire. Run this 48-positive matrix
twice in opposite orders, with eight slot probes per run.

Every physical target and modulo-16/32/64 candidate receives a distinct codeword where the register
numbers differ. The oracle predicts the XOR result, which source register becomes zero, which
nominal high register remains intact, and the mandatory release of the other source. Thus a correct
destination alone cannot hide a wrong access or lifecycle model.

Sparse runs are discovery evidence only. If they agree, freeze a separate amendment specifying
dense direct ranges, the complete source-byte namespace, aliases/holes/faults, and formal run IDs
before promotion captures.

## Gates and stop rule

- Gate A: exactly one generated ten-byte `ilogic` body with exact requested/actual fields and no
  framing alias.
- Gate B/C: complete state, distinct codewords, source-release locations, and both refuters must
  discriminate the model.
- Gate D: `COPIED=0`, `CARRIER=0`.
- Gate E: quiet opposite-order G17P runs with no unexplained fault, hang, recovery, or restart.

Every dispatch has a 20-second watchdog and zero-hang budget. If SSH or the device becomes
unresponsive, stop immediately, preserve evidence, perform no recovery/reboot, and report blocked.

Clean-room provenance: OWN-SHADER + HW-PROBE. Apple binary introspection: **NONE**.
