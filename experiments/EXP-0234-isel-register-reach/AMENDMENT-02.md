# EXP-0234 AMENDMENT-02 — freeze the corrected full-selector confirmation

Frozen after the two AMENDMENT-01 sparse discovery runs and before any confirmation dispatch.
Repository base: `e0f2cbb0`.

## Sparse result

`g17p_e0234_discovery01` and `g17p_e0234_discovery02` each dispatched eight slot probes plus the
same 48 source cases in opposite orders.  Both completed with zero faults and zero hangs.  Every
case agreed across runs in instruction bytes, complete observations, status, outcome, and semantic
classification.

For every one of compare A, compare B, selected true, and selected false:

- r0, r23, r24, r31, r32, r47, r48, and r63 read the exact physical register;
- descriptors nominally encoding r64, r79, r80, and r95 did not read those physical registers;
- selected-value r80/r95 cases read r16/r31 respectively, ruling out modulo-16 and showing that
  source descriptor bit 7 is ignored in this canonical form;
- compare-role observations were consistent with the same alias, but equality-to-exact alone did
  not distinguish that alias from any other unequal value.  The confirmation below fixes that
  detection gap.

The immutable work-only evidence hashes are:

```text
ba29adba01137d73c8b0fc41bc2997bc7ea83acf6b39948d081b1c06c6ff7ef6  discovery01/sweep.jsonl
cbc83e695f0726b3eb5c62e24a04feacae4846c232c7676caae0ad7466553bb6  discovery01/05_run_manifest.json
9f21d47f3af350e15137cb6dcc770d1832ee7bc1f15d9f8508ffbf51753c9e56  discovery02/sweep.jsonl
20ace7a0802494d40eab054e02cafb3fce1b0a030fe45abd5e09b8d4bea5a67a  discovery02/05_run_manifest.json
```

These files remain discovery-only and are not promoted as formal evidence.

## Corrected primary model

In the canonical ten-byte 32-bit form, all four source bytes encode a seven-bit descriptor payload
plus a source-class/parity bit.  The GPR selector is effectively `R & 63`:

- encoded R=0..63 directly reads physical r0..r63;
- encoded R=64..127 aliases r0..r63 respectively;
- physical r64..r95 cannot be directly named by any of the four canonical source fields;
- the complete one-byte descriptor namespace has no beyond-range code and therefore no expected
  fault boundary in this form.

The four-bit destination remains exactly r0..r15; no encoding in this form can name r16..r95.

## Frozen confirmation matrix

Each formal run contains:

- all encoded R=0..127 for each of compare A, compare B, true value, and false value: 512 cases;
- all destination nibbles r0..r15: 16 cases;
- two wrong-oracle controls;
- eight slot probes;
- 538 dispatches total.

For direct cases the oracle predicts the physical target.  For high-descriptor cases the oracle
predicts r`(R & 63)`.  Compare-role high cases seed the other comparator with the aliased low
register's value, so the predicate must become true only if the alias is actually read.  This
closes the sparse run's compare detection gap.  Cases where modulo-16 differs must reject that
alternative.  Physical r64..r95 are independently seeded and observed where applicable, proving
that an aliased read neither accesses nor corrupts them.

Run the matrix once in canonical order and once in reverse order using the original formal IDs
`g17p_e0234_run01` and `g17p_e0234_run02`.  The superseded fault-boundary run IDs are retired and
must not be dispatched.  Any fault, hang, recovery, foreign runner, byte disagreement, or
complete-state mismatch fails confirmation.  Device unresponsiveness still requires an immediate
stop without recovery or reboot.
