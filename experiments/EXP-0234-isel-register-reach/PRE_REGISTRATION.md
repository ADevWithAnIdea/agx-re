# EXP-0234 pre-registration — canonical `isel10` register reach

Frozen before the first EXP-0234 hardware dispatch. Repository base: `2bc50ff1`.

## Question

What exact physical GPR sets can the already-proved canonical ten-byte 32-bit `isel10` recipe read
through each of its four source roles and write through its destination role on G17P? What happens
at the first two representative descriptors beyond the 96-register physical file?

EXP-0223 proves the compare/select condition table, retained/released source lifecycle, aliases,
pending-load acceptance, all source roles through r23, and the complete four-bit destination
namespace r0..r15. This experiment changes only one selected register role at a time.

## Frozen primary model

For canonical integer equality `D = (A == B) ? T : F`, retaining all four sources:

- **compare A:** `cmpA = (A << 1) | 1` directly reads r0..r95;
- **compare B:** `cmpB = (B << 1) | 1` directly reads r0..r95;
- **true value:** `selTrue = T << 1` directly reads r0..r95;
- **false value:** `selFalse = F << 1` directly reads r0..r95;
- **destination:** the four-bit `dst` field directly writes exactly r0..r15; physical r16..r95
  are unrepresentable in this form, not runtime-invalid encodings;
- r96 is the first invalid source for each role and faults; r127 also faults rather than wrapping.

The canonical fields are otherwise fixed at `opsel=0`, `cmp_mode=0x06`, `cc=0`, `flags=0xc0`, and
`selFalse_file=0`.

## Detection construction

Every valid target and its modulo-16/32/64 rivals receive distinct codewords. Compare-role cases
seed the other compare operand with the exact target codeword, so equality is true only for the
exact source and selects a value distinct from every alias model. True/false-value cases force the
corresponding arm and expose that source's exact bits. Complete state verifies all sources retained.

The formal matrix per run is:

- 96 dense cases for each of A, B, T, and F: 384 source cases;
- 16 dense destination cases: r0..r15;
- two wrong-oracle controls;
- eight slot probes, for 410 dispatches total;
- canonical and reverse formal orders on Apple A18 Pro / G17P.

The source-boundary matrix has five cases per role, 20 total: r95 exact; r96 expected contained
fault; r95 exact; r127 expected contained fault; r95 exact. It is repeated in canonical and reverse
order. Exact controls after every fault must pass. Eight deliberate faults/recoveries per boundary
run are expected; any hang stops the run immediately.

## Tokenizer hypothesis

The EXP-0223 tokenizer rule deliberately recognized the canonical ten-byte signature only while
each source descriptor stayed within its old r23 test envelope. Without a change, a valid-looking
`cmpA` descriptor for r28 is misclassified as a two-byte trailing operand word. Before dispatch,
EXP-0234 widens only the four parity-constrained source descriptors inside the already-tight
canonical signature (`opsel`, compare mode, condition, flags, source class, and ten-byte tail remain
fixed). Every hardware case retains a following framing witness. Successful execution and exact
state therefore test operand reach and the widened ten-byte framing together; a local decoder fit
alone is not evidence.

## Five gates

- **A:** actual dispatched body decodes as exactly one generated `isel10`, with no byte, descriptor,
  or whole-stream framing disagreement.
- **B:** target/alias pre-witnesses, independently forced predicate arms, complete three-buffer
  state, sentinel, and both wrong-oracle controls must discriminate the result.
- **C:** every main result and all retained/alias state match the independent host model in both
  runs; exact source selection must beat modulo-16/32/64 alternatives where distinguishable.
- **D:** every field is generated from EXP-0223's canonical recipe; `COPIED=0`, `CARRIER=0`.
- **E:** quiet opposite-order G17P runs agree case-for-case, with no foreign runner, unexplained
  recovery, fault, hang, or restart. Boundary runs may contain exactly their eight pre-registered
  contained faults/recoveries and no others.

## Pilot and stop rule

After this pre-registration and the frozen dependencies are committed, work-only pilots may test
only r95 in each source role. Pilot output stays below `work/pilot/` and cannot be promoted.

Every dispatch has a 20-second watchdog. If SSH or the device becomes unresponsive, immediately
stop, preserve evidence, perform no recovery/reboot, and report blocked.

Clean-room provenance: OWN-SHADER + HW-PROBE. Apple binary introspection: **NONE**.
