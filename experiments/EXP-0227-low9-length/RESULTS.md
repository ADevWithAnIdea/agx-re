# EXP-0227 — results

## Verdict

**Hardware-validated on G17P, bounded to the tested point:**

```text
09 01 20 05
```

is a four-byte instruction. The following instruction begins at byte +4.

This confirms the specific low-nibble-9 selector-0 boundary left structural by
EXP-0148. It does **not** yet prove every `byte+2 & 7 == 0`, every selector-1
value, every destination high nibble, or every stream placement.

## Evidence

Two formal runs passed the frozen `analysis/formal227.py` gate:

| run | case order | length cases | quiet samples | recovery delta | result |
|---|---|---:|---:|---:|---|
| `g17p_e0227_run01` | canonical | 5/5 | 36 | 0 | pass |
| `g17p_e0227_run02` | reverse | 5/5 | 36 | 0 | pass |

Both runs contained 13 dispatches including the eight base-slot probes, with
zero hangs, faults, restarts, foreign retries, or unexplained cross-run output
differences. The learned mapping was `out=0, mem=1, imem=2` in both runs.

The disputed prefix was followed by a staircase of generated two-byte markers.
All expected values appeared in both runs:

```text
candidate relative +4   first marker: r0=85, r0=51, or r6=87 by case
candidate relative +6   r3=91
candidate relative +8   r4=92
candidate relative +10  r5=93
candidate relative +12  r11=94
```

Thus the observed marker vector is `[true,true,true,true]` with the post marker
true, uniquely selecting length 4 from the preregistered `{4,6,8,10,12}` set.
The first marker tracked two different immediates and a different destination,
so this is not a coincidental arithmetic result in r0. The previously known
`09 01 21 05` compact control produced the same boundary signature.

The identical `09 01 20 05 · mov r0,85` program scored against a deliberately
wrong r0=51 host model was rejected as `wrong_value` in both runs. That proves
the readback distinguishes the asserted marker effect from a plausible wrong
model.

## Gate details

- Every on-disk archive region reread byte-identical to the generated program.
- Gate A reported zero field disagreements and zero descriptor/framing aliases.
- Every program reported `COPIED=0` and `CARRIER=0`.
- All three buffers were read back; sentinels stayed intact and length cases had
  zero stray writes.
- Program hashes and complete three-buffer output hashes agreed case-by-case
  across opposite run orders.
- Pre/post `busy_count` was zero and `recovery_count` was unchanged in both
  formal runs. Every quiet sample reported zero foreign runner.
- The hardware identified itself as Apple A18 Pro; raw records name target G17P.

Frozen formal summary: `analysis/formal_result.json`.

## Raw artifact hashes

```text
run01 sweep.jsonl  afc5eec15ced42d39ab07dc0acb273efcfe8c5ef462b62eb5e81f085335252ab
run02 sweep.jsonl  aabdd97cf2c3deaf5270a624c2762c76f4daacdea6f0263f4878864372413bb9
run01 00_inputs    fe819874f050461bdfbda417a3459e3b48766cd868b8d456134d491b64b9ed46
run02 00_inputs    096a38403f427a2fc33915a8e050aeed27e31398ae2812d59f3378691096f438
```

## Process notes

The input-contract checker caught and corrected a hand-transcribed carrier
hash before any dispatch. After the formal runs, one multi-source `scp` command
retrieved only run01; the frozen analyzer failed closed with `FileNotFoundError`.
Run02 was then pulled in a separate read-only transaction and the unchanged
analyzer passed. Neither issue changed a generated program, raw record, gate,
or hypothesis.

## What remains

Step 1 stays unchecked. Immediate follow-up coverage should include:

1. a dense selector/mode sweep for the low-nibble-9 four-byte class, preserving
   causal marker controls and classifying fault/inert/longer outcomes;
2. byte0 high-nibble and alignment/adjacency matrices for the validated forms;
3. the unresolved selector-2/3 forms;
4. the `0x10` compressed-half rule, low-nibble-b rule, `op04` ambiguity,
   shuffle extension, stop/padding, illegal/truncated streams, and code extent;
5. all other compressed/normal/extended families in the Step 1 inventory.

## Clean-room statement

The carrier is our own MSL and is overwritten in full. Every executed shader
instruction was generated from our documented fields. No Apple binary or fresh
Metal-generated low-nibble-9 instruction was inspected.
