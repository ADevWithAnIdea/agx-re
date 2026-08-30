# EXP-0157 — PROGRESS

Append-only. One entry per milestone, timestamped. A kill costs at most one milestone.

## 2026-08-29 — M0: context, feasibility, and the testbed gap
- Read `CLAUDE.md`, `CODEX.md`, `SUBAGENT_BRIEF.md`, `NEO-TARGET-BRIEF.md`,
  `FIELD-SWEEP-PROTOCOL.md`, `work/UNATTENDED-RUN.md`, `docs/evidence-classification.md`.
- Diffed `validation.json` against `db.json` for all 20 dispatched descriptors →
  `work/blocking_fields.txt` (the exact blocking field list).
- **Found that EXP-0146 already swept `n2_op6`/`n2_op8`/`n2_op10`/`n3_mov`/`sfu_marker`
  densely on M4 and its `field_verdicts.json` was never merged into `validation.json`.**
  Those are therefore G17P-revalidation targets here, not from-scratch derivations.

## 2026-08-29 — M1: THE ACCELERATION-STRUCTURE TESTBED GAP IS CLOSED
- Wrote `harness/agxrun_persist_as.m`: `tools/agxtest/agxrun_persist.m` + an
  `MTLAccelerationStructure` build-and-bind path. The shared tool is NOT edited
  (four sibling G17P experiments rebuild it concurrently).
- Authored `kernels/k_rq_prim.metal` / `k_rq_inst.metal` / `k_rq_getters.metal`.
- **Verified on G17P: all 8 host-computed ray-query oracles match exactly.**
  `q.next()` now enters the traversal loop; every getter reaches the output.
  EXP-0146's blocker ("`agxrun_persist` binds `MTLBuffer`s only") is gone.
- Learned: `opaque = NO` on the geometry is load-bearing (an opaque hit is
  auto-committed and never surfaces as a candidate); and the AS *build* command
  buffer is itself a frequent `...ErrorInnocentVictim` on a busy device, so it
  needs its own retry loop (30 attempts, backoff).

## 2026-08-29 — M2: census of what G17P actually emits
- `analysis/resync.py` (resync tokenizer, after-gap flagged).
- The ray-query carrier contains `sr_read_wide` (36), `rtq_state_move` (42),
  `ray_move` (46), `rtq_pred` (28), `rtq_dualsrc` (28), `ray_move_copy6` (20),
  `ray_move_zinit` (9), `ray_move_zero6` (7), `op04_len8` (9), `n2_op6` (45).
- `k_provoke.metal` provocations found carriers for `h_coord_hi` (k_h4_fma) and
  `h_coord_hi_ext` (k_h3_mix).
- **NEGATIVE, and a G16G↔G17P delta: `n2_op8` is emitted by NO own-MSL
  provocation on G17P** (7 transcendental variants tried), although EXP-0146
  found it in `fast::sin` on M4. Likewise `coord_madf` (4 texture variants) and
  `mesh_out_src`.
- Differential compilation over three `triangle_data` getter kernels isolates a
  single ray-query PROPERTY SELECTOR byte at 14 sites (0xc4 bary.x / 0xc6
  bary.y / 0xc8 distance) — inside `rt_ray_mem`, not inside `sr_read_wide`.

## 2026-08-29 — M3: contract frozen, harness built, smoke passed
- `PRE_REGISTRATION.md` + `CAPTURE_CONTRACT.json` frozen (repo revision recorded).
- Harness: `carriers.py` (16 carriers, every RT oracle NON-ZERO by construction),
  `cases.py` (frozen arm table + coverage rule), `run.py` (adapted from EXP-0153),
  `runner_as.py`, `build.sh`.
- Smoke runs smoke01..smoke04 pass on arms R, S, H. Retained, not reused.

## 2026-08-29 — M4: gated run01 launched (arms R, S, H)

## 2026-08-29 — M5: arms L/M/N/Q — the `0x04` length rule, measured on hardware
- `harness/run_lm.py` witness probe. **Both controls pass**: 8 bytes of known
  2-byte `mov_imm` leave every witness set; a known 6-byte instruction followed by
  `mov_imm(r5,5)` sets r5. So the probe can see a 6-byte length.
- **All six real `op04_len8` patterns from our own G17P compiles consume TWELVE
  bytes, not the eight `db.json` declares** (witness pattern `r1=r2=0, r3=3, r4=4`
  in every case).
- **`mesh_out_src`'s 2-byte length is CONFIRMED for `byte+1 < 0x80` and REFUTED
  for `byte+1 >= 0x80`**: a `04 XX` probe consumes exactly 2 bytes for all 128
  values with bit7 clear and exactly 4 for all 128 with bit7 set.
- Arm N (byte-position sweep) and arm Q (2-D `byte+1` x `byte+2`) turn that into
  a rule: the `0x04` group's length is a function of **byte+1 bit 7 AND byte+2**,
  not of byte+1 alone.

## 2026-08-29 — M6: the reachability control — `inert` vs `unreached`
- `harness/reachprobe.py`. Erasing **256 contiguous bytes** at three `rtq_pred`
  and three `rtq_dualsrc` anchors leaves the ray-query oracle EXACTLY correct;
  the same erase over the live `sr_read_wide` anchor breaks it at **four** bytes.
- So those regions are **UNREACHED** by a triangle-only query, not inert.
- Follow-up: authored `kernels/k_rq_bbox.metal` + a `--accel-kind bbox`
  bounding-box acceleration structure to drive the CUSTOM-INTERSECTION path
  (all four oracles verified: 3.0 / 6.0 / 1.0 / 6.0). `rtq_pred` and
  `rtq_dualsrc` are inert at every scanned anchor **there too**.

## 2026-08-29 — M7: coordinator directives applied
- FIELD-SWEEP-PROTOCOL §7A: `--repeats` added to `harness/run.py`; every
  `fault`/`hang` will be confirmed under `~/agxre/gpulease.sh`, 5x, not by
  majority-of-3 in an unlocked run.
- `tools/agxtest/persistrun.py` EOF fix: verified the neo's copy is byte-identical
  to the fixed repo copy (`cc53d8ef...`), so no re-copy was needed.

## 2026-08-29 — M8: gated run01 COMPLETE (20 962 records)
- 188 of 190 mid-run baseline health checks passed; 0 hangs; 1 107 faults recorded
  (all pending lease confirmation per §7A); 2 660 innocent-victim retries absorbed.
- 47 live anchors of 119 scanned. `rtq_pred` 0/8 live, `rtq_dualsrc` 0/11 —
  explained by the reachability control (M6), not left ambiguous.
- run02 launched CONCURRENTLY with run01 (`harness/chain2.sh`) rather than after
  it: the two gated runs are independent captures of the same frozen case list
  and run01's fault-heavy `h_coord_hi` arm would otherwise have cost hours.
- Post-freeze arm **B2** (`ray_move` etc. in the 25 kB `k_rq_prim` carrier) found
  the live `ray_move` anchor that `rq_cdist` did not contain: dst 15/15,
  src 255/255, b3 255/255 ok, form 223 ok / 32 fault. Second capture gated.

## 2026-08-29 — M9: emittability reported BOTH ways
- `analysis/emittability.py` applies DOC-02's rule mechanically AND separately
  reports `single_value_only` operand fields — densely swept, exact rule, but the
  accepted set is the compiler's own value up to don't-care bits, so an emitter
  cannot actually choose that operand. Reporting only the first number would
  overstate the result.
- `scoreboard_fence` / `compute_fence_scoped` and `op04_len8` are explicitly
  DECLINED in `analysis/verdicts.py` with the reason recorded per field.

## 2026-08-30 — M10: gate composition, and the run02 decision
- **run02 STOPPED at 11 830 records and RETAINED as a partial**, not reused, not topped up.
  It had completed all of arm R and the `sfusin` groups — which is what gates the ray-query
  cluster, `n2_op6` and `sfu_marker` — then slowed to ~10 records/min because half of
  `sfumix.n2_op6.opsel` faults with `...ErrorHang` and, under sustained sibling load, each of
  those costs a device recovery. Finishing it would have taken ~16 h of shared GPU for arms whose
  instructions were already gated in another carrier.
- `raw/g17p_run03` is a NEW run id: a targeted second capture of the four carriers run02 never
  reached (u64eq, roundm, h4fma, h3mix), replaying run01's resolved case list.
- Post-freeze arm **B2** gated on its own pair (`raymove01`+`raymove02`): 3 058 of 3 059 common
  cases agree.
- Nine oversized `00_cases.json` files (108 MB) replaced by CODEX §6 manifests — they are
  DERIVED INPUTS regenerable by `harness/cases.py`, and no `sweep.jsonl` was touched.

## 2026-08-30 — M11: side finding recorded rather than lost
- `rt_ray_mem.field_off` (byte+10) is the **ray-query property selector**: three
  `intersection_query<triangle_data>` kernels differing only in their getter compile to programs
  byte-identical except at 14 offsets, each taking 0xc4 / 0xc6 / 0xc8, and each program returns
  its own host oracle exactly. Not a dispatched descriptor, but it is the reason sweeping
  `sr_read_wide.sel` never produced another property. Recorded at `isolated-byte-diff`.

## 2026-08-30 — M12: verdicts made MERGE-READY, and why EXP-0146's never landed
- `work/merge_verdicts.py` requires keys of the exact form `<mnemonic>.<field>` and rejects
  `<mnemonic>.<field>@<carrier>` outright. **EXP-0146 uses the `@carrier` convention**, which
  is very likely why its dense M4 sweeps of `n2_op6`/`n2_op8`/`n2_op10`/`n3_mov`/`sfu_marker`
  never reached `validation.json` — those fields still read `untested` there.
- This experiment therefore emits BOTH: `analysis/field_verdicts.json` (merge-ready, exact rule
  and outcomes folded into `note`) and `analysis/field_verdicts_by_carrier.json` (per-carrier
  and per-byte detail).
- **Dry run of the orchestrator's merger: 29 applied, emitter-grade 552 → 580 fields,
  emittable instructions 53 → 59** — `n2_op6`, `ray_move`, `ray_move_copy6`, `ray_move_zero6`,
  `rtq_state_move`, `sr_read_wide`. The only 3 skips are the deliberate `op04_len8` downgrades,
  which the merger correctly refuses to apply without a human decision.

## 2026-08-30 — M13: output-SHAPE analysis (`analysis/shapes.py`)
- Classifying rejected values by the SHAPE of the multi-row output, rather than by an outcome
  label, turned "254 wrong values" into exact behavioural classes for three descriptors:
  `sfu_marker` (both bytes are SFU quadrant/sign control — EXP-0146's M4 sign-flip reproduced
  and extended), `n2_op6` (`opsel` bit 1 silences the SFU; `imm_sel` selects which reduced row
  survives), and `scoreboard_fence` (rejected values partition the rows BY THEIR OWN COMPARISON
  RESULT — an ordering signature, not generic corruption).

## 2026-08-30 — M14: the fault-confirmation pass had to be retried (shared-tool race)
- chain2's §7A lease pass **never ran**: at the moment it invoked `~/agxre/gpulease.sh`, that
  shared script was mid-rewrite by another agent and bash could not parse it —
  `` gpulease.sh: line 48: unexpected EOF while looking for matching `'` ``. `bash -n` on it
  passes now (mtime 23:47), so it was a transient half-written file, not a lasting break.
  **Worth telling the wave: a shell wrapper edited in place while eight agents invoke it is a
  race, and its failure mode is silent — `gpulease.sh` exits non-zero and the payload simply
  never runs.**
- `harness/chain4.sh` retries it over ALL THREE gated captures, and `bash -n`s the lease script
  before invoking it so the same failure is loud next time.
- The gate itself was also corrected: run02 (partial) and run03 (targeted) are COMPLEMENTARY
  second captures, so the gate is `run01` vs the **union** of the later runs, not their
  intersection. Intersecting all three briefly under-reported the result as 3 emittable
  descriptors instead of 6, because run03 was still mid-capture.
