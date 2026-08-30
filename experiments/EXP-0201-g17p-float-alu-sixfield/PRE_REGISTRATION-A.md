# EXP-0201 — AMENDMENT A, pre-registration (frozen before its first dispatch)

**Trigger.** `RE_EXPERIMENT_PROCESS_CORRECTIONS.md` was added to the repository while runs 01–04
of this experiment were executing. It is **normative and overrides the gates in the original
`PRE_REGISTRATION.md` where they conflict**. This amendment brings EXP-0201 into compliance.

**Frozen:** 2026-08-30, **before the first dispatch of run id `a_run01`**. Runs
`g17p_20260830_run01..run04` are **retained unchanged** as evidence under their own frozen gate
(§9: "Do not retroactively call an observation false merely because a later acceptance gate is
stricter than the experiment's frozen gate"). They are reclassified on the six axes in
`RESULTS.md`, not discarded. Nothing is re-run that already has what the new gates require.

## A0. What runs 01–04 already satisfy, and what they do not

| gate | runs 01–04 status |
|---|---|
| **A — actual-byte ledger** | **PARTIAL.** Every case records the mutated instruction bytes and the pinned tokenizer's opinion of them, and `analysis/gen_arms.py` proved pairwise-distinct, span-confined encodings for every value of every arm **before** dispatch. What is missing is the ledger's *closing link*: bytes re-extracted from the blob that was actually dispatched, the value decoded back out of those bytes, and the program hash. **Re-run required.** |
| **B — positive control** | **MET.** Every arm carries a `_live_control` on a different field at the same occurrence, plus a pre-registered falsifier. The `fspecial_est` arms' controls **failed**, which under Gate B makes those arms `carrier-undecidable` — the correct verdict, already reached. |
| **C — independent semantic predictor** | **MET IN STRUCTURE, THIN IN INPUTS.** `harness/models201.py` pre-registered a per-value predicted operation before any dispatch, and `harness/carriers201.py` classifies every read-back against a named host library, giving all five required buckets. But the inputs were two well-behaved magnitude vectors. **Phase 3 requires** signed zero, infinities, NaNs, denormals and rounding boundaries. **Re-run required, as added arms.** |
| **D — generated recipe** | **NOT ATTEMPTED** beyond `copysign`, whose descriptor pins bits 0..23 by `match`. Stated as a bounded gap; not claimed. |
| **E — clean confirmation** | **NOT MET.** `harness/gpuwatch.py` measured concurrency for all four runs: run01 saw a foreign GPU process in 6 of 128 samples and **0** foreign *dispatch* runners; runs 02/03/04 were heavily contended (47/65, 32/32, 18/18 samples with foreign dispatchers). All four ran in identical case order. **Re-run required, in reversed order, on a quiet machine.** |

## A1. What changes

1. **Gate A ledger, per case.** `run.py` now records, for every dispatch:
   `ledger = {requested_value, requested_bytes, actual_bytes, decoded_value, ok,
   program_sha256, main_off, instr_off, start, width}`, where `actual_bytes` is re-extracted
   **from the blob that is about to be dispatched** and `decoded_value` is read back out of those
   bytes by an expression independent of the patch routine. `ok` is the assertion
   `requested value == value decoded from actual dispatched bytes`. `db_sha256` and
   `harness_sha256` are on every record. **`analysis/verdicts.py` refuses any hardware conclusion
   on an arm with a single `ledger.ok == false` case**, and reports requested case count, distinct
   requested values, **distinct ACTUAL encodings**, and any `match`-bit collision.
2. **Gate C adversarial inputs.** Five new arms use the same authored kernels with
   **adversarial input sets**: `-0.0`, `+0.0`, `+inf`, `-inf`, `NaN`, the smallest denormal
   (`1.4e-45`), and the `2^24` rounding boundary where `x + 1` rounds back to `x`.
   `analysis/oracle_check.py` was extended to compare library members by **bit pattern**, because
   value equality cannot see `+0.0` vs `-0.0` and reports `NaN != NaN`. It caught a real collision
   on the first draft of the adversarial `copysign` set — with all signs opposite,
   `copysign(a,b)` **equals** `-a` and the library cannot tell a sign copy from a negation — and
   the set was changed before any device time. **The saturating carrier's adversarial set
   deliberately omits `NaN` and infinities**, because `saturate(NaN)` is not something we can
   predict on the host with confidence; that limitation is stated, not papered over.
3. **Gate E ordering.** `run.py --order forward|reverse|shuffle`. The confirmation pair runs
   **`a_run01` forward and `a_run02` reversed**, so an order-dependent artefact cannot masquerade
   as agreement.
4. **Gate E quietness.** A confirmation run must be QUIET: **zero** `gpuwatch` samples showing a
   foreign GPU-runner process for the whole duration. `analysis/verdicts.py` also reports
   `samples_with_foreign_DISPATCH_runner` separately, because a hang-induced **device reset** —
   the contamination mechanism `FIELD-SWEEP-PROTOCOL.md` §7 names — comes from a sibling's
   *dispatch*, not from its compile. **The gate uses the STRICT figure**, so that distinction can
   only inform a reader, never loosen a verdict. **If no quiet window is obtained, no field is
   promoted and the cross-run figure is reported as `CONTAMINATED`** — a contaminated run cannot
   confirm at all.
5. **Six-axis verdict.** `analysis/field_verdicts.json` reports, per field and independently:
   `encoding_geometry`, `liveness`, `semantics`, `compiler_recipe`, `target`, `reproducibility`,
   with exact numerators and denominators, never a bare percentage. **Liveness never rounds up
   into semantics**: `sem_checked == 0` can never yield `hardware-run`, and a field whose values
   move without an independent semantic predictor selecting a model is `live; role unknown`.
6. **Negative wording.** An inert reading is written
   `inert in <exact tested envelope>; global role unknown` — never `unused`, `reserved`,
   `don't-care`, or `may be chosen arbitrarily`.

## A2. What does NOT change

The hypotheses, refuters, carriers, field spans, coverage and the aliasing hard stop of the
original `PRE_REGISTRATION.md` (with amendments A1/A2 there) stand unaltered. **No hypothesis is
edited to match data already captured.** The published `falu3.op` operation map is still tested as
a prediction that can be refuted, and it has already been *partially refuted* on run01 — that
result stands on its own frozen gate and is reported as such.

## A3. Frozen expectations for the amendment runs

| field | prediction carried into `a_run01`/`a_run02` |
|---|---|
| `falu3.op` | accept set on the identity fma carrier is `(v & 7) ∈ {4,5,6}` with `(v & 0xC0) == 0`, giving `-b` / `0` / `a*b+c`; `(v & 7) == 7` faults; bits 3,4,5 inert; the low-3 entries `0/1/2` (`a+b`, `a*b`, `a*b+a`) do **not** reproduce on a three-source carrier. Refuted if the adversarial-input arm disagrees with the well-behaved arm on any accepted value. |
| `falu3_ext.op` | accept rule exactly `(v & 0xC7) == 0x06`. Refuted by any accepted value outside it. |
| `fspecial_est.srcA` | `carrier-undecidable`: no arm has detection power, because the positive control and the falsifier both fail. Refuted if any adversarial arm's control fires. |
| `falu3_srcmod12.opsel` | only `{2,3,6,7}` stay in the mnemonic (bit 17 is pinned by `match`); accept `(v & 7) == 6`. Refuted if a bit-17-clear value still tokenizes as `falu3_srcmod12`. |
| `falu3_srcmod12.ctrl` | accept `(v & 0x7F) == 0x03`; `6 + 2*(v & 3)` re-lengths the instruction. Refuted if the accept set is not explained by the length rule plus the fixed remainder. |
| `copysign.operands` | accept rule exactly `(v & 0x7E) == 0x00` — bits 0 and 7 inert — identically on the role-exchanged carrier. Refuted by a different accept set, or by the adversarial-input arm disagreeing. |

Each is a **pre-registered prediction for the amendment runs, derived from runs 01–04 and stated
before the amendment's first dispatch**. Confirmation on adversarial inputs and reversed order is
a genuine test; agreement is not guaranteed by construction, and disagreement is reportable.

## A4. Stopping rule

`a_run01` (forward) and `a_run02` (reverse) over the full frozen arm set. If neither is quiet, a
further pair may be attempted; run ids are never reused and a partial capture is retained, never
topped up. If no quiet pair is obtained within the dispatch, the amendment reports
**`reproducibility: incomplete — no clean confirmation window`** and promotes nothing on Gate E,
while the geometry, liveness and semantic axes still carry their measured results.
