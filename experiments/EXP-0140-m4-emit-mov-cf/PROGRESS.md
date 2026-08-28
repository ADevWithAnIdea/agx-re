# PROGRESS — EXP-0140

Timestamped milestone log. Written as each milestone completes so a kill costs at most one.

- **2026-08-27 M0 — orientation.** Read `CLAUDE.md`, `CODEX.md`, `SUBAGENT_BRIEF.md`,
  `FIELD-SWEEP-PROTOCOL.md`, `docs/evidence-classification.md`, EXP-0128's RESULTS. Counted the
  blocking fields per instruction from `db.json` + `validation.json`: MOV 25, CF 26 — matching
  the dispatch.
- **2026-08-27 M1 — tooling built.** `harness/build.sh` → `work/bin/{shdump,agxrun,agxrun_persist}`
  from our own read-only tool sources.
- **2026-08-27 M2 — carriers located (pilot, non-gated).** `work/pilot/locate.py`: `sel` sits at
  `+0x18` of `dsel5.metal`'s own 46-byte compile (`16 c2 a0 c8`); `psel` at `+0x0A` of
  `gsel4.metal`'s 32-byte compile (`05 22 a0 de`). Both baselines reproduce on hardware.
- **2026-08-27 M3 — uniform-file map found (pilot, non-gated).** `work/pilot/pilot2.py`, 256-value
  `usrc` sweep on an authored 4-`constant` carrier: **usrc ≥ 0x80 materialises the immediate
  `usrc & 0x7F`**; usrc < 0x80 reads a pair-quantised uniform register, with our four bound
  magic constants at usrc {0x18,0x19},{0x1C,0x1D},{0x20,0x21},{0x24,0x25} — matching EXP-0020's
  independent "byte1 steps by 4" corpus observation. This became pre-registered hypothesis H5.
- **2026-08-27 M4 — `sel`/`psel` body decomposed (pilot, non-gated).** `work/pilot/pilot4.py`,
  3×256 per-byte sweeps on both carriers: byte+3 ≥ 0x80 sets the predicate-FALSE arm to the byte
  itself, < 0x80 reads an unwritten operand (0). Confirmed statically against five authored
  `?:` variants: `(a>5)?130:250` compiles to `16 c2 a0 fa` (0xfa = 250). → hypotheses H2/H3.
- **2026-08-27 M5 — CF skeleton reproduced.** `work/pilot/pilot3.py`: EXP-0112's skeleton,
  rebuilt field-by-field through `isadb.assemble`, matches its host-computed oracle exactly
  (14.5) and equals the carrier's own natural compile output.
- **2026-08-27 M6 — environmental noise characterised (pilots 5–7).** `CMDBUF_ERROR` with
  `kIOGPUCommandBufferCallbackErrorInnocentVictim` occurs on byte-identical programs that
  otherwise pass 9/10 times. Replication + status-retry added.
- *(session interrupted by the account session limit; no gated capture had been started, `raw/`
  was empty, so nothing was partial and no run id was consumed.)*
- **2026-08-28 M7 — resumed; new protocol §7 and the batch-1 corrections applied.**
  * D1 unique splice-archive path per request (EXP-0141's ~8% phantom `CMDBUF_ERROR`);
  * D2 pre-poisoned output buffer + integrity sentinel (EXP-0141's "STATUS OK, nothing executed");
  * D3 never conclude `fault` from one observation — replication, OS fault-class string recorded,
    innocent-victim segregated as `invalid_run`;
  * D4 periodic baseline re-validation with runner restart and cascade abort.
  * Re-read the EXP-0148 length-rule correction; re-checked the `0x?B` group under it (max 10 B,
    so the frozen 6-byte inert pad after each `regmove` test is still sufficient).
  * New `kernels/carrier_cf2.metal` (EXP-0112's CF carrier + `acc`-only padding, **no new buffer
    reference**) to make room for the sentinel; base_slots re-derived and unchanged (2/1/0).
- **2026-08-28 M8 — two findings from the hardened smoke, before freezing.**
  * `mov_imm` with immediate **12** is the only 0..127 immediate whose 2-byte encoding fails to
    tokenize under the current length rule (exhaustive static check over all 16 dst values).
    Avoided everywhere in the frozen matrix; recorded as a `db_defects` candidate.
  * With a **poisoned** output buffer, `mov_imm` with imm=200 does **not** "silently zero" the
    register (EXP-0128's reading, made against a zero-initialised buffer): padded, the register
    keeps its previous value (7); unpadded, the following instruction is consumed. A paired
    control case was added to the frozen matrix to settle it in the gated runs.
- **2026-08-28 M9 — contract frozen.** `PRE_REGISTRATION.md` committed; 7976 cases.
- **2026-08-28 M10 — gated `m4_20260828_run01` ABORTED by its own D4 baseline check at case
  4500, and the abort found a real confound.** The CF-carrier baseline reproduced
  `acc*2` on **every** lane instead of the `acc > 100 ? acc*2 : acc-3` mix — i.e. the reused
  skeleton's select comparison had changed. `work/pilot/pilot8.py` isolated it: **the carrier,
  not the sentinel.** EXP-0112's own `carrier_cf.metal` (152 B) reproduces the host oracle
  exactly on all 8 lanes; `carrier_cf2.metal` — the same kernel plus arithmetic on `acc`
  **alone**, adding no new buffer reference, which is exactly the padding technique EXP-0128
  proposed but never dispatched — breaks it, with the sentinel on *or* off, while every
  `base_slot` stays identical. Lengthening a CF carrier moves the constant the skeleton
  compares against. run01 is RETAINED as the record of that finding and is not used as
  evidence for any field verdict.
- **2026-08-28 M11 — CF arm reverted to `carrier_cf.metal`.** No sentinel prologue (the 152-byte
  region is exactly filled by the skeleton); on that carrier the integrity check is the
  poisoned output buffer alone, a stated limitation. Matrix re-frozen at 7960 cases; CF
  baseline verified `ok` on hardware before relaunching.
- **2026-08-28 M12 — `m4_20260828_run02` COMPLETE** (7960 cases, 859.9 s, all 30 periodic
  baseline checks `ok`). 5 hangs; the per-arm budget stopped exactly two arms
  (`if_push_pred.level@4`, `ret.scoreboard@12`); the CF-wide budget was not reached.
  98 `invalid_run` (integrity check failed) — segregated, never counted as encoding behaviour.
- **2026-08-28 M13 — `m4_20260828_run03` PARTIAL (7365 / 7960), retained.** It died inside
  `ret.linkmode@12` because the *machine's* `MTLCompilerService` became unavailable
  ("Connection init failed at lookup with error 141 - Reentrancy avoided"), so the persistent
  runner could not start. This is a **fourth contamination mode** for the protocol's §7 list,
  above the three already known: under many concurrent agents the Metal **compiler service**
  itself can go away, which kills a capture before any GPU work happens. `run.py` now retries
  runner start-up with backoff. Missing from run03: `ret.scoreboard@12`, `jump_cond.offset`,
  `pop_reconverge.reserved@14`, `pop_reconverge.reserved@15`, and part of `ret.linkmode@12`.
- **2026-08-28 M14 — `run04` (the tail groups) BLOCKED.** `MTLCompilerService` stayed
  unavailable for 20 consecutive probes over ~7 minutes; `shdump` cannot compile even a
  4-line kernel, while the device still enumerates as "Apple M4". This is host-wide and
  affects every agent, not this experiment's encodings. Per `CLAUDE.md` no recovery action was
  attempted (no `macvdmtool`, no reboot). Analysis proceeds on run02 (complete) gated against
  run03 (partial); the four tail groups are reported as **single-run, not `hardware-run`**.
- **2026-08-28 M15 — analysis complete.** `analysis/verdicts.py` gates run02 against run03
  (7365 common: 6953 agree, 320 disagree — 58 of them one arm run03 lost to its hang budget —
  92 excluded as environmental), `analysis/masks.py` fits an exact acceptance mask to every
  8-bit field's accepted set, `analysis/emittability.py` does the per-instruction accounting.
  Two analysis-side repairs, both leaving `raw/` untouched: a signed-vs-unsigned comparison bug
  in the driver (4 records; harness fixed for future captures) and the `no_store`
  reclassification of 65 CF cases that were `invalid_run` in both runs with every trial
  STATUS OK.
- **2026-08-28 M16 — `jump_cond` deliberately NOT promoted.** All three of its fields, and all
  36 structured offsets including targets outside the program, reproduced the baseline exactly.
  That is a carrier-liveness failure, not an inertness finding: the guard's only true lane has
  trip count 0. Reported `untested` with the reason, per FIELD-SWEEP-PROTOCOL §3.2.
- **2026-08-28 M17 — deliverables written.** `RESULTS.md`, `field_verdicts.json`,
  `field_masks.json`, `emittability.json`, `manifest.json`, `QUARANTINE-NOTE-run01.md`.
  **11 of 23 instructions newly emittable (3 → 14 of 23); 31 fields to emitter grade.**
  Four more instructions (`jump`, `ret`, `pop_reconverge`, `if_push_pred`) are one gated
  capture short, not one hardware result short — blocked only by the host's
  `MTLCompilerService` outage, which was still active at hand-off.
- **Disclosure (run id hygiene).** The blocked `run04` attempt created its `raw/` directory and
  then raised inside `harness/baseline.py` before writing a single record, twice. Both empty
  directories were removed and the id was re-attempted; **no capture data was lost or
  overwritten**, because none had been written. `run01`, `run02` and `run03` were never
  touched after their driver finished with them.
