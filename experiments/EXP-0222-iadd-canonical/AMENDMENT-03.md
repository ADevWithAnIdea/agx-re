# AMENDMENT-03 — isolate the five lifecycle-differential bits on hardware

Frozen after the revised dynamic own-MSL compile, before dispatching any case that varies these
five bits.

## What the authored compiler differential says — and does not say

The revised kernels have distinct, cleanly tokenized 134-byte mains.  The likely `a+b`
instruction in `add_dead` is:

```text
9f 01 56 0a 03 04 00 a8 17 05
```

The likely `a+b` instruction in `add_live` is:

```text
9f 01 56 0a 02 04 02 ac 11 05
```

These differ in five bits:

- `opmode` bit 0: 1 in `add_dead`, 0 in `add_live`;
- `srcB_ext` bit 0 (instruction bit 49): 0 in `add_dead`, 1 in `add_live`;
- `srcA` bit 2 (instruction bit 58): 0 in `add_dead`, 1 in `add_live`;
- `opc_tail` bits 1 and 2 (instruction bits 65 and 66): both 1 in `add_dead`, both 0 in
  `add_live`.

This does **not** assign semantics.  The authored kernels also differ in the sum's use count:
`add_dead` consumes `c` three times while `add_live` consumes it once.  The five-bit difference can
therefore mix source lifetime, destination lifetime/publication, cache routing, and invalid
descriptor-pair states.  The compiler bytes nominate a bounded hardware sweep only; no byte or
field is copied into a generated program.

## Frozen hardware sweep L1

Start from the independently generated, arithmetically working add point and emit `r0 = r1+r2`.
Keep every field fixed except the five nominated bits.  Exhaust all 32 combinations:

```text
opmode       = 2 | O                    O in {0,1}
srcB_ext     = (r1 << 2) | A            A in {0,1}
srcA         = 0xa8 | (B << 2)          B in {0,1}
opc_tail     = 0x11 | (T1 << 1) | (T2 << 2)   T1,T2 in {0,1}
```

All other fields remain at the generated point in PRE_REGISTRATION section 2.  `r0`, `r1`, and
`r2` begin with distinct values; the full r0..r23 state is dumped after the instruction.  The
independent expected arithmetic is `r0=83`, and the discovery oracle provisionally expects
`r1=41`, `r2=42` so each released source appears explicitly in the diff.

Classify each combination only by direct observation:

- destination: correct / not written / wrong;
- source A (`r1`): retained / zeroed / other;
- source B (`r2`): retained / zeroed / other;
- collateral registers: unchanged / changed;
- execution: success / fault / hang.

Do not call a bit a source-lifetime bit merely because it correlates with retention in one
combination.  A candidate retain encoding must then pass single-source-live tests, aliases,
immediate consumers, and a multi-instruction DAG.  Faulting combinations remain meaningful
descriptor constraints; null combinations remain bounded observations, never "unused bits."

## Frozen controls and stopping

- The natural destructive point `(O,A,B,T1,T2)=(0,0,0,1,1)` must reproduce correct arithmetic
  with both sources zeroed.  If it does not, the sweep is carrier-undecidable.
- The own-compiler live nominee `(0,1,1,0,0)` is a hypothesis, not an expected pass.
- A wrong-selector arithmetic case from the existing pilot remains the detection control.
- Stop after four hangs or eight contained faults.  Preserve partial output and pre-register a
  safer split if the threshold is reached.

