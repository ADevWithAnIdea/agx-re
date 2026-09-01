# EXP-0233 results — canonical low-32 `imad` register reach

**Verdict: PASS on G17P.** The canonical twelve-byte retained-source low-32 `imad` directly reads
X from r0..r63, directly reads Y from r0..r31, and directly writes every physical GPR r0..r95.
r96 is the first invalid destination and raises a contained command-buffer fault; r127 also faults
rather than wrapping.

Pre-registration commits: `de91f95b` and frozen dependencies `f6c9e538`. The replacement-boundary
protocol and duplicate-run guard were frozen as `c784f718` before `boundary03` dispatch.

## 1. Main direct-reach result

The two formal runs each contain 8 slot probes, 192 main cases, and 2 wrong-oracle controls:

- `raw/g17p_e0233_run01` — canonical order, 202 dispatches;
- `raw/g17p_e0233_run02` — reverse order, 202 dispatches.

All **384/384 main observations** were exact across the pair:

| role | canonical selector | direct physical set | result |
|---|---|---|---|
| X multiplicand | `srcC_lo = X << 2` | r0..r63 | 64/64 exact per run |
| Y multiplicand | `srcB = Y << 3` | r0..r31 | 32/32 exact per run |
| destination | `dst = D << 1` | r0..r95 | 96/96 exact per run |

The X field is eight bits and cannot represent canonical r64. The Y field is eight bits and cannot
represent canonical r32. These are form-specific encoding bounds, not out-of-file accesses.

Every source and its modulo-16/32 alternatives held distinct codewords. Exact source selection had
zero mismatches; modulo-16 was rejected by 48 X cases and 16 Y cases, and modulo-32 was rejected by
32 X cases. Both wrong-oracle controls fired in both runs. Both sources remained live, as required
by the frozen `b9=0x20` recipe.

## 2. Destination finite boundary

The accepted formal boundary pair is:

- `raw/g17p_e0233_boundary01` — canonical order;
- `raw/g17p_e0233_boundary03` — reverse order.

Both agree byte-for-byte and semantically:

```text
r95  exact
r96  contained CMDBUF_ERROR
r95  exact after recovery
r127 contained CMDBUF_ERROR
r95  exact after recovery
```

Each invalid destination took about 505 ms, incremented the recorded GPU recovery counter once,
and was followed by an exact r95 control. There were zero hangs or runner restarts. Therefore r95
is the maximum valid G17P destination, r96 is the first invalid destination, and larger encodings
do not wrap to a lower register.

## 3. Boundary02 ancillary-metadata exclusion

`raw/g17p_e0233_boundary02/sweep.jsonl` also contains 13 complete original records and agrees with
the accepted pair. It is excluded from Gate E because a later accidental duplicate-ID invocation
overwrote only its process/GPU snapshots after `run233.py` refused to reuse the sweep directory.
The timestamp inconsistency and recovery samples are retained; no record was rewritten to conceal
the defect. `AMENDMENT-01.md` gives the full chain, and `analysis/ancillary_exclusion.json` records
the exclusion mechanically. The capture wrappers now reject duplicate IDs before sampling.

## 4. Five gates

| gate | result |
|---|---|
| **A — geometry** | **PASS.** Every main/control/boundary body contains exactly one generated 12-byte `imad`; accepted formal pairs have byte-identical programs case-for-case, with no decode or descriptor-alias disagreement. |
| **B — detection** | **PASS.** Distinct target/alias codewords and both wrong-oracle controls prove the result channels discriminate exact selection. Exact controls surround every invalid destination. |
| **C — semantics** | **PASS.** All 384 main observations are exact; both accepted boundary runs agree with no failures. |
| **D — generation** | **PASS.** Main runs each record `RULE=1053779`, `FREE=27480`, `CARRIER=0`, and `COPIED=0`; boundary runs also have zero donor/carrier fields. |
| **E — target/reproduction** | **PASS for run01/run02 and boundary01/boundary03.** All have quiet-process samples with zero foreign runners/compiler services, zero hangs, and zero restarts. Main runs have zero recoveries; each accepted deliberate-boundary run has exactly two. |

Machine-readable gates: `analysis/formal_result.json`, `analysis/boundary_result.json`,
`analysis/gate_e_result.json`, and `analysis/ancillary_exclusion.json`.

## 5. What this closes, and what it does not

Together with EXP-0225, this closes a compiler-usable canonical retained-source low-32 IMUL/IMAD
recipe and its physical-GPR reach. It does not close multiply-high, b16/b64 or pair forms, external
addend fetch, alternate lifecycle controls, or noncanonical low descriptor bits. Those remain
separate instruction-capability questions.

## 6. Clean-room provenance

Clean-room provenance: OWN-SHADER + HW-PROBE.

The programs were assembled from documented project rules and executed through the public Metal
API on Apple A18 Pro / G17P. Apple binary introspection: **NONE**.
