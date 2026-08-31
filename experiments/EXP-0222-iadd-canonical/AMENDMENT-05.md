# AMENDMENT-05 — operand provenance and r16..r23 extension

Frozen after the two byte-identical-by-case V1 pilot confirmations, before dispatching the P1
cases below.

## Why this is a separate gate

V1 used values produced by the `mov_imm` prologue or an earlier `iadd2`.  Apple9 has already shown
operand-provenance-sensitive acceptance/forward controls in `falu2` and `device_store`; an integer
recipe is not compiler-usable merely because it works on immediate-seeded operands.  The generated
recipe must also consume a `device_load` result and values in the upper half of the load-addressable
GPR range.

## Frozen P1 cases

Using R1 unchanged (`opmode=2`, descriptor low bits clear, `srcA=0xa8`, `opc_tail=0x11`):

1. load the logical A operand into r1 and consume it in the immediately following add;
2. load logical B into r2 and consume it immediately;
3. issue loads into both operands consecutively, so the second is the immediately preceding
   instruction;
4. consume a just-loaded logical A in subtraction, where it occupies the second physical source;
5. repeat with one independent `mov_imm` between the load and consumer;
6. add/subtract values in r16..r23 seeded by the generated load prologue, including high
   destinations and low/high crossings;
7. consume r23 in the first body instruction, immediately after the prologue's load to r23;
8. repeat high-register destination/source aliases.

Every value is independently predicted and the complete r0..r23 state is dumped.  A direct-load
case that gives the stale value, zero, or a correct result with a dropped source refutes the R1
provenance envelope.

If only immediately-adjacent load cases fail, the next sweep is limited to the three bits that were
null for `mov_imm` provenance in L1 (`opmode` bit 0, `srcB_ext` bit 0, `srcA` bit 2), crossed with
which physical source receives the load.  Do not transfer `falu2`'s route value by analogy.

