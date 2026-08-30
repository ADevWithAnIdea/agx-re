# g17p_20260829_faultconfirm — lease-isolated 5x re-confirmation (PARTIAL, honest)

Pass specified by amendment **A3** after FIELD-SWEEP-PROTOCOL **§7A** (EXP-0153)
landed mid-experiment: majority-of-3 plus cross-run agreement is not sufficient
for a `fault` verdict.

**Scope actually covered.** 1 010 values were recorded `fault` or `hang` in BOTH
gated runs. The pass takes a spread of at most 8 values per (arm, field) and was
stopped by hand at **133 confirmation records** because throughput fell to about
one record per 85 s — each target is 5 renders and a hang costs a 15 s watchdog
plus a child restart. Targets are processed in the frozen arm PRIORITY order, so
the coverage is the priority end of the matrix, not a random sample.

**Two defects in this pass, recorded rather than hidden:**

1. **19 of the 133 records are not real targets.** The selector took any record
   with outcome `fault`/`hang`, which also matched the `_field_stopped` /
   `_arm_stopped` **control records** run.py emits with `value = -1` and an empty
   `bytes` string. Re-running one splices zero bytes, i.e. runs the unmutated
   baseline, so it trivially returns `ok` 5/5. **These are not refutations** and
   are excluded from every number below. A successor should filter
   `value >= 0 and bytes != ""`.
2. **Isolation was not guaranteed for the whole pass.** This process broke a
   genuinely stale lease (holder `EXP-0158-run03`, age 902 s > the 900 s
   staleness rule) and acquired the lock at 06:46:5x — and `EXP-0156` wrote
   itself as owner at 06:46:53, within seconds. That is a race in the shared
   `mkdir`-based lease when a stale break happens: two waiters can both break and
   both believe they hold it. So this pass ran under a *held* lease but not
   necessarily an *exclusive* one. The results below are still much stronger than
   the unlocked runs, but they are not the perfect isolation §7A describes.

**Result over the 114 genuine targets:**

| | |
|---|---|
| reproduced **5/5** under the lease | **112** |
| did not reproduce | **2** |

The two that did not:

- **`tex_write.coord_pack = 5` on write w1 — NOT A FAULT.** Both gated runs
  recorded `fault`; under the lease it is `wrong_value` **5/5**. This is exactly
  the §7A phenomenon EXP-0153 described: contamination that survived
  majority-of-3 *and* two independent runs. The `coord_pack` semantics in
  `RESULTS.md` §2.3 are corrected accordingly.
- **`imageblock_store.src = 246` — 4/5 fault, 1 silent zero.** Reported as
  "faults 4/5 under isolation", not as a clean fault.

So the unlocked two-gated-run reading was right for 112 of 114 checked values
(98.2 %) and wrong for one. The remaining ~900 cross-run fault/hang values are
**unconfirmed**; every fault statement resting on them is labelled as such.
