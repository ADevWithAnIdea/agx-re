# EXP-0223 — generated integer compare/select recipe

Pre-registration time: 2026-08-31, before the first EXP-0223 dispatch and before compiling or
inspecting any fresh compare/select MSL.

Target: Apple A18 Pro / G17P.  Clean-room class: OWN-SHADER carrier + HW-PROBE.  Reuse EXP-0220's
already-audited carrier, complete-state oracle, actual-byte ledger, and runner.  Every instruction
field is generated from the hypotheses below; no compiler instruction is copied.

## 1. Compiler question

Can the backend generate a fused signed-i32 compare/select over four arbitrary GPR values:

```text
D = (A < B) ? T : F
```

The first milestone is a register-register `isel10` recipe, including source lifetime.  Later
milestones extend the condition/type table and fold forms.  A correct final backend may choose a
different select family if this family cannot express the operation.

## 2. Fixed instruction point

Use the current structural `isel10` descriptor without reading any captured instance:

```text
dst             = D
opsel           = 0
cmp_mode        = 0x81
cc              = 0x07
flags           = 0
selFalse_file   = 0
```

`cmp_mode=0x81, cc=0x07` is the repository's existing signed-less-than hypothesis.  It is not
treated as proven on G17P by this experiment until both true and false cases execute.  `opsel=0`
is the lowest ten-byte member accepted by the current structural length rule, chosen independently
as a canonical candidate rather than copied from a compiler token.

Inputs use the generated prologue's distinct values: r1=41, r2=42, r3=43, r4=44; destination r0.
Thus `r1<r2` predicts r0=43 and `r2<r1` predicts r0=44.  The full r0..r23 state must otherwise be
unchanged.

## 3. Three frozen operand-packing hypotheses

Each applies the same packing to `cmpA`, `cmpB`, `selTrue`, and `selFalse`:

- H1 plain: field = register number;
- H2 pair/width descriptor: field = `(register << 1) | 1`;
- H3 factor-four descriptor: field = `register << 2`.

Run both predicate polarities for every hypothesis.  A hypothesis passes arithmetic only if both
true and false selections match.  It passes the full contract only if all compare and select inputs
remain readable and no collateral register changes.

Only after H1/H2/H3 all fail may a new authored-MSL differential be compiled and its main inspected.
The compiler output may nominate fields but is never copied or counted as hardware proof.

## 4. Controls, gates, and stopping

- S0 re-measures buffer slots.
- A wrong-predicate host model must mismatch, proving selected-value sensitivity.
- Gate A records requested fields, actual emitted bytes, bytes reread from the archive, and an
  independent decode; any disagreement or alias fails the case.
- All fields must be `RULE`/`FREE`, with `COPIED=0` and `CARRIER=0`.
- Outputs are poisoned, a separate sentinel is written, and r0..r23 plus all three buffers are
  compared.
- Stop after four hangs or eight contained faults.  A null result with a failed control is
  carrier-undecidable, not evidence of an unused field.

