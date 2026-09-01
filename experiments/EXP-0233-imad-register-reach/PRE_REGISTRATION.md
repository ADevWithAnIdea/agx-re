# EXP-0233 pre-registration — canonical low-32 `imad` register reach

Frozen before the first EXP-0233 hardware dispatch. Repository base: `f72867a2`.

## Question

What exact physical GPR sets can the already-proved canonical twelve-byte low-32 `imad` recipe
read through each multiplicand role and write through its destination role on G17P?

EXP-0225 proves the complete donor-free arithmetic recipe, immediate K=0..255, retained/released
source lifecycle, aliases, direct pending-load consumption, and all three roles through r23. This
experiment changes only the selected register of one role at a time.

## Frozen primary model

For `D = (X * Y) mod 2^32` with both sources retained:

- **X source:** `srcC_lo = X << 2` directly reads exactly r0..r63.
- **Y source:** `srcB = Y << 3` directly reads exactly r0..r31.
- **Destination:** `dst = D << 1` directly writes every physical GPR r0..r95 on G17P.
- r96 is the first invalid destination and faults; r127 also faults rather than wrapping.

The first unrepresentable canonical X descriptor is r64 (`256`, outside its eight-bit field). The
first unrepresentable canonical Y descriptor is r32 (`256`, outside its eight-bit field). These are
representation bounds for this fixed form, not hardware faults. Low descriptor bits, `b1hi`, and
alternate multiply/addend/width forms remain separate capability questions.

The G17P destination hypothesis is informed by the 96-register physical-file result and EXP-0232's
target-qualified `iadd2` boundary, but is not inherited from it: EXP-0233 executes every r0..r95
IMAD destination and separately tests r96/r127.

## Matrix

- 64 X-source cases: r0..r63 dense.
- 32 Y-source cases: r0..r31 dense.
- 96 destination cases: r0..r95 dense.
- Two wrong-oracle controls, one source and one destination.
- Two formal runs in canonical and reverse order on Apple A18 Pro / G17P.
- A separate five-case destination-boundary sequence, repeated in canonical and reverse order:
  r95 exact; r96 fault; r95 exact; r127 fault; r95 exact.

Every selected source and every modulo-16/32 rival receives a separately observed codeword before
the multiply. Destination cases seed and observe the physical destination and its modulo-16/32/64
rivals. Dynamic memory-index registers are chosen outside the case's relevant set.

## Five gates

- **A:** the actual dispatched body must decode as exactly one generated `imad`, with no byte or
  descriptor disagreement.
- **B:** source/destination/alias pre-witnesses, complete three-buffer state, and the sentinel must
  pass; both wrong-oracle controls must fail.
- **C:** every main result and all retained/alias state must match the independent modulo-2^32 host
  model in both runs. Exact source selection must beat modulo-16/32 alternatives where the tested
  range distinguishes them.
- **D:** all fields are generated from the EXP-0225 canonical retained-source recipe. `COPIED=0`
  and `CARRIER=0` are mandatory.
- **E:** two quiet opposite-order G17P runs must agree case-for-case, with no foreign runner,
  unexplained recovery, fault, hang, or restart. Boundary runs may contain exactly their two
  pre-registered contained faults/recoveries and no others.

## Pilot and stop rule

After this pre-registration is committed, work-only pilots may test only the last representable
X/Y selectors and r95 destination before the formal runs. Pilot output stays below `work/pilot/`
and cannot be promoted.

Every dispatch has a 20-second watchdog. If SSH or the device becomes unresponsive, immediately
stop, preserve evidence, perform no recovery/reboot, and report blocked.

Clean-room provenance: OWN-SHADER + HW-PROBE. Apple binary introspection: **NONE**.
