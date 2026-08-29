# EXP-0138 progress log (append-only, one entry per milestone)

## 2026-08-28 — Milestone 0: setup
- Created `experiments/EXP-0138-m4-emit-falu/`. Repo revision at pre-registration:
  `f17938ee0105c8f1fb1e1c25be3aa22fa4a77a5c` (dirty: sibling agents' untracked
  EXP-0133/0139/0140/0141 dirs only; no tracked file modified by this experiment).
- Built `work/bin/{shdump,agxrun,agxrun_persist}` from the UNMODIFIED
  `tools/shdump/shdump.m`, `tools/agxtest/agxrun.m`, `tools/agxtest/agxrun_persist.m`
  (`harness/build.sh`). Host: Apple M4 (G16G), macOS 26.6.2 (25G82).

## 2026-08-28 — Milestone 1: pilot (NON-GATED, `work/pilot/`)
Purpose: obtain a known-good, compiler-emitted ANCHOR encoding for every family
before any sweep, and prove both execution modes work. Nothing here is promoted;
every gated claim is re-derived in `raw/`.

1. **Anchor compiles** (`work/pilot/anchors{,2,3,4}.metal`, OUR OWN MSL, 42 kernels):
   byte-exact anchors obtained for `falu2`, `falu2i`, `falu2_ext`,
   `falu2_srcmod10`, `falu3`, `falu3_ext`, `falu3_srcmod12`, `falu_acc`,
   `copysign`, `half_alu`, `half_alu_ext8`, `half_alu_fma12`, `fspecial`,
   `fspecial_est`. **No compiler-emitted anchor was found for `falu_srcmod12b`,
   `falu2_ext8b` or `falu2_uni`** across 42 authored kernels (round 4 hunted them
   specifically). `falu_srcmod12b` is therefore CONSTRUCTED by family analogy;
   `falu2_ext8b` and `falu2_uni` have no carrier.
2. **MODE A works** (`work/pilot/smoke2.py`): a fully hand-built program spliced
   over the whole `_agc.main` of `kernels/carrier.metal` (region 1218 B) seeds
   r0..r12 with 13 distinct exact minifloat constants via `falu2i` and reads them
   all back exactly (5.0,1.5,3.0,0.5,7.0,9.0,11.0,13.0 at word slots 0..28).
   **Pilot bug 1 (found and fixed here):** the first attempt used the compiler's
   own `opflags=3` on the instruction under test, which sets bits 19/20 =
   release-srcA/release-srcB (EXP-0086/0099) — the later read-back stores of those
   same source registers then returned 0.0. Every instruction under test now uses
   `opflags=0` unless `opflags` is itself the swept variable.
3. **All MODE A families verified computing the predicted value** (`work/pilot/
   famsmoke.py`, 15/15): falu2 add=8.0/mul=15.0, falu2i add=8.0, falu2_ext
   saturate=0.75/1.0, falu2_srcmod10=8.0, falu_srcmod12b (opsel_mod=0) = 8.0
   (**new: EXP-0119 never read this family's own result**), falu3 fma=22.0,
   falu3_ext saturate(fma)=1.0, falu3_srcmod12 fma=22.0, falu_acc add=8.0/mul=15.0.
   **Safety disclosure:** one pilot case ran `falu_srcmod12b` with `opsel=4` (the
   EXP-0119 unrelated-register corruptor) before that guard was added; it returned
   a non-OK status with no output, the host did not wedge, the next case ran
   normally, and the case was removed from the pilot. `opsel` is NOT swept for
   that family in the gated matrix.
4. **MODE B works** (`work/pilot/modebsmoke.py`): in-place single-instruction
   splices into compiled carriers execute and change the answer —
   `half_alu` 0x1c→0x1d flips 5+3=8 to 5*3=15; `fspecial` rsqrt(4)=0.5 → rcp=0.25
   → exp2=16 → floor=4.
5. **Uniform arm works and settles `falu2.mod_lo` bit1** (`work/pilot/unismoke.py`,
   `kernels/carrier_uni.metal`): with a `constant float4&` bound at buffer(2) =
   {101,202,303,404}, `falu2` with `mod_lo=2` and `srcB_reg` swept 0..15 returned
   exactly 101/202/303/404 at indices 6/7/8/9 and 0.0 elsewhere (index 10 returned
   the carrier's own literal 1.0000001f). With `mod_lo=0` the same field reads the
   GPR file. **mod_lo bit1 = "srcB reads the UNIFORM register file".**
6. **MODE-B carrier offsets pinned** by byte search (not by tokenization, which
   desyncs on some of them): k_add@0x2a, k_addi@0x12, k_hadd@0x2a, k_hsat@0x2a,
   k_hfmaabs@0x42, k_copysign@0x30, k_rsqrtf@0x12, k_rsqrtn@0x12.

Zero GPU hangs, zero host wedges across the whole pilot (~250 dispatches).
Throughput measured at ~1.1 ms/case on the persistent runner.

## 2026-08-28 16:40-17:05 — Milestone 2: the gated runs (resumed after a host sleep + a reboot)

**Re-orientation (from `raw/`, not from memory).** On resume the tree held
`run01` COMPLETE (16,202 cases, 0 cascades, elapsed 693 s), `run02` partial
(253) and `run03` partial (188) — both killed by a machine-wide
`MTLCompilerService` collapse ("Reentrancy avoided"), `run04` EMPTY (0 records,
killed by the host reboot at ~16:27), and `smoke01` (98, non-gated). No
verdicts file existed. All four partials are RETAINED AS-IS; none was topped
up or reused.

**Contract integrity check before running anything** (`analysis` of
`CAPTURE_CONTRACT.json` vs disk):
* `harness/families.py`, `harness/isa_helpers.py`, `harness/build.sh`, all
  three `kernels/*.metal`, `PRE_REGISTRATION.md`, and every read-only tool
  except `db.json` still hash EXACTLY as frozen.
* **`harness/bench.py` and `harness/run.py` differ from the frozen hashes.**
  The delta is commit `93822c0c` -> `97162755` and is confined to (a) retrying
  `shdump`/`agxrun_persist` startup through a transient machine-wide
  `MTLCompilerService` outage and (b) one extra counter in a `print`. It does
  not touch case generation, splicing, poisoning, majority-of-3, victim
  classification, the sentinel, or outcome classification — it is
  measurement-neutral. DISCLOSED here and in `RESULTS.md`; the frozen
  `authored_sha256` block is left untouched and an append-only `amendments`
  entry records the new hashes.
* **`tools/agx-isa/db.json` differs** (sibling EXP-0144 landed at `ef86175e`).
  Diffed instruction-by-instruction against the frozen `04fc5f7d` copy: the
  ONLY changed instructions are `pack_convert` / `unpack_convert`. No
  float-ALU instruction changed. Proven empirically as well: regenerating the
  whole 16,202-case matrix under the CURRENT `db.json` reproduces run01's
  recorded `bytes`/`instr`/`field`/`value` for **all 16,202 cases, 0
  mismatches**. The drift is provably irrelevant to this experiment.

**`smoke02`** (8 cases, non-gated, new id): end-to-end health check of the
whole path after the reboot. 8/8 `ok`.

**`m4_20260828_run05`** — full matrix, isolated host. Reached case 13,564 in
~90 s (vs 693 s for run01 against ~9 concurrent GPU siblings) with **0
victims** and 15 faults, then entered the `fspecial.src` arm and began HANGING:
values 192, 193, 194 each burned 5 attempts x 12 s watchdog. Per
FIELD-SWEEP-PROTOCOL section 8 ("after two genuine hangs in one area, STOP that
arm") the run was KILLED at 13,564 records and is retained as a partial.

**`m4_20260828_run06`** — every group EXCEPT `GB_fspecial`, 14,119 cases,
73 s, **0 victims, 0 hangs, 0 cascades, 0 compiler outages**, 15 faults.
COMPLETE.

**`m4_20260828_run07`** — same 19 groups, launched as the second isolated
gated run so the frozen promotion rule's "identical in both gated runs" clause
is satisfied by two runs captured on a QUIET host.

## 2026-08-28 17:05-17:25 — Milestone 3: run07 abandoned, verdicts produced

**`m4_20260828_run07` KILLED at 280 records and retained as a partial.** It
stalled in the `falu2_uni.ctrl_lo` sweep with repeated HANGs (3 x 12 s watchdog
per case) after `ps` showed **two sibling experiments holding live
`agxrun_persist` children** (EXP-0143 `c_simd.metal`, EXP-0151
`carrier_seed.metal`). Its records are contaminated and it is NOT used as a
gated run.

**Gated pair analysed: `run01` + `run06`** (`run06` replaces the contract's dead
`run02`), with `run05` carried as a third annotating run.

**Result: 65 of 98 previously-blocked float-ALU fields reached emitter grade**
(59 `hardware-run` + 6 `isolated-byte-diff`); 21 stayed `untested`; 12 were
never swept (`fspecial`'s 11 after the arm was stopped for hangs, plus
`half_alu_fma12.ext` which is `emit_unsafe` by design).
**Four instructions become emittable: `copysign`, `falu2`, `half_alu`,
`half_alu_ext8`.**

**Priority 1 LANDED. `falu2.mod_lo` = `hardware-run`**, dense over all 8 values,
with an IDENTICAL per-case outcome map in all three runs (98/98 in each of
run01, run05, run06). H-MODLO was refuted in both halves and replaced by an
operand-source-class model that then scores **294/294 exact** across the three
runs (`analysis/model_check.py`). The replacement exposed an inline 8-bit
**minifloat immediate** operand on `falu2` (`srcB_reg` 64..127 when `mod_lo`
bits[2:1]==1), which is the largest single find of the experiment.

Deliverables written: `analysis/field_verdicts.json` (97 field verdicts +
`db_defects` + per-field `cross_run` and `label_isolated_pair` disclosure),
`analysis/annotate.py`, `analysis/model_check.py`, `RESULTS.md`, and the
append-only `amendments` block in `CAPTURE_CONTRACT.json`.

Nothing was committed. `db.json`, `validation.json`, `docs/` and `PROVENANCE.md`
were not touched.
