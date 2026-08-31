# EXP-0214 — verdicts for the 13 fields EXP-0212's span splits created

**Target of the underlying observations:** G17P (A18 Pro). **This experiment:** desk work on
the M4 host. **No device was contacted, no shader compiled, no program dispatched** —
EXP-0213 held the neo for quiet Gate E confirmations and any load would have corrupted them.

## Question

EXP-0212 applied hardware-confirmed descriptor repairs that split five field spans and
created **13 new fields**, all at `untested`. Three instructions (`half_pack`, `irotate`,
`simd_reduce`) left the emittable set as a direct consequence. The experiments that
*discovered* these sub-fields also *measured* them — their raw swept the parent span. So:

> For each of the 13, does the discovering experiment's committed raw actually cover the
> **new** span, and what label does that coverage honestly support?

The trap this experiment exists to avoid is the one the corpus keeps falling into: a parent
sweep does **not** automatically cover a sub-field. If the parent varied only bits outside
the sub-span, coverage is **zero** and the field stays `untested` no matter how large the
parent's numbers look.

## Method

1. **Re-derive the sub-span from the ACTUAL DISPATCHED BYTES.** `scripts/span_coverage.py`
   decodes bits `[start, start+width)` out of every raw record's actual-byte ledger and
   counts distinct span values, distinct actual encodings, arms and runs. A parent-field
   name is never trusted as evidence that its bits moved.
2. **Re-derive Gate A per new span.** Two experiments' drivers compute `ledger_ok` against
   the *parent* field's decode, which is wrong once the parent is split; both are recomputed
   here against the new span.
3. **Score the six axes of `RE_EXPERIMENT_PROCESS_CORRECTIONS` §2 separately** — geometry,
   liveness, semantics, recipe, target, reproducibility — with exact numerators and
   denominators (§5), never a bare percentage.
4. **Propose a legacy label only where the five gates support it.** `sem_checked == 0` can
   never produce `hardware-run`; liveness without an independent predictor is
   `live; role unknown`; an inertness claim needs §7's bar.

## Result

**1 of 13 promoted, 12 stay `untested`. The emittable-instruction count does not move.**

| field | span | verdict |
|---|---|---|
| `half_alu_fma12.srcC` | (40,8) | **`hardware-run`** — 6144/6144 full-16-word host-oracle matches |
| `half_alu_fma12.lensel` | (32,2) | `untested` — live on a 2-valued length observable; the 4-value map is unconfirmed and the db map is contradicted |
| `half_alu_fma12.mods` | (34,6) | `untested` — live, no predictor indexed by the field |
| `half_pack.dst` | (4,4) | `untested` — **never swept**; 2 of 16 values, both fixed arm constants |
| `irotate.rot_dst` | (24,8) | `untested` — live, pre-registered predictor refuted on 520/2048 |
| `irotate.op_enable` | (32,8) | `untested` — live, predictor refuted on 1016/2048 |
| `irotate.rot_src` | (40,8) | `untested` — live, predictor refuted on 24/2048 |
| `irotate.amt_tail` | (56,8) | `untested` — live, predictor refuted on 56/2048 |
| `simd_reduce.op_hi` | (11,5) | `untested` — accepted-inert (period 8 in 24/24 cells); §7 bar not met |
| `frag_depth_store.b1_lo` | (8,1) | `untested` — accepted-inert; §7 bar not met |
| `frag_depth_store.b1_hi` | (11,5) | `untested` — accepted-inert; §7 bar not met |
| `frag_depth_store.b2` | (16,8) | `untested` — accepted-inert; §7 bar not met |
| `pop_reconverge.reserved_hi` | (40,8) | `untested` — **9 of 256 values**, on carriers 2 of 3 of which are blind |

`python3 work/merge_verdicts.py --dry-run experiments/EXP-0214-new-field-verdicts/analysis/field_verdicts.json`
→ rc 0, 13 applied / 0 skipped, emitter-grade 559 → 560, **emittable 37 → 37**.

## Layout

```
README.md                          this file
RESULTS.md                         the six-axis records, the gate arithmetic, and what could have gone wrong
analysis/field_verdicts.json       the deliverable, keyed <mnemonic>.<field>, every row carrying start/width
analysis/field_verdicts_meta.json  provenance header (kept out of the verdicts file so the merge exits 0)
analysis/e0203_half.json           re-derived coverage: half_alu_fma12 lensel/mods/srcC, half_pack.dst
analysis/e0202_irotate.json        re-derived Gate A + coverage: the four irotate sub-spans
analysis/e0205_op_hi.json          re-derived period-8 inertness test
analysis/e0199_frag_depth_store.json  re-derived accepted-set and sub-span coverage
analysis/e0206_reserved_hi.json    re-derived high-byte coverage stratified by the sibling low byte
scripts/                           every number above, reproducible; see scripts/README.md
```

**Nothing outside this directory was written.** `tools/agx-isa/validation.json`, `db.json`,
`docs/` and `PROVENANCE.md` are untouched; no raw file was edited; nothing was committed.
