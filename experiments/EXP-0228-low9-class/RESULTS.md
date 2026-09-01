# EXP-0228 — results

## Verdict

**Hardware-validated on G17P, bounded to the tested class:** every generated

```text
09 01 XX 05    where XX & 7 is 0 or 1
```

consumes exactly four bytes for all 64 possible values of the upper five bits
of `XX`. The following instruction begins at byte +4.

This closes the byte+2 selector-0/1 length rule at fixed `byte0=0x09`,
`byte1=0x01`, and `byte3=0x05`. It is a framing result only; it does not assign
semantics to selectors or upper mode bits.

## Evidence

The frozen `analysis/formal228.py` gate passed two opposite-order formal runs:

| run | case order | distinct selector values | quiet samples | recovery delta | result |
|---|---|---:|---:|---:|---|
| `g17p_e0228_run01` | canonical | 64/64 | 43 | 0 | pass |
| `g17p_e0228_run02` | reverse | 64/64 | 43 | 0 | pass |

Each run made 73 dispatches: eight slot probes, 64 generated length probes,
and one wrong-model control. All 64 probes completed with `status=OK`, uniquely
inferred length four, and executed every marker in the staircase. The duplicate
`XX=0x20` case scored against the deliberately wrong first-marker value was
rejected in both runs, proving the detector could distinguish its claimed
boundary effect from a plausible wrong host model.

Both runs reproduced `out=0, mem=1, imem=2`, had zero hangs, zero faults, zero
foreign runners, zero busy pre/post samples, and no recovery-count movement.
Generated-program hashes, all three complete output-buffer hashes, inferred
outcomes, and marker observations agreed case-by-case across run order.

The dense set was:

```text
XX = (mode << 3) | selector
mode = 0..31
selector = 0 or 1
```

Thus the result covers natural and off-natural encodings through the maximum
five-bit upper-mode value; it is not an extrapolation from a few compiler-seen
points.

## Raw artifact hashes

```text
run01 sweep.jsonl  850a187f14ea7a7627d9e7ce7c4ebe29a526338ea77b2c58b521aeb96b128e88
run02 sweep.jsonl  609363a56a1a7a67763427b13813e5110ac1c1f89f41d9891f464d040effb5b3
run01 00_inputs    78f8e45cc7583646c9285889b9976cf2914c84affcf26828e1d12ee13b2b7705
run02 00_inputs    4b0b9c7d9ea2066a82ecb304718070f1b2000d4b379ad8dfddbee6e835864042
```

Frozen formal summary: `analysis/formal_result.json`.

## Scope

This result deliberately does not claim that destination, source, operand,
alignment, or arbitrary surrounding bytes are irrelevant. Under the shortened
instruction-length task, those axes do not need dedicated length experiments
unless an existing stream, later semantic experiment, or decoder conflict
shows that they affect framing.

## Clean-room statement

The carrier is our own MSL and is overwritten in full. Every executed shader
instruction was generated from documented fields. No Apple binary or fresh
Metal-generated low-nibble-9 instruction was inspected.
