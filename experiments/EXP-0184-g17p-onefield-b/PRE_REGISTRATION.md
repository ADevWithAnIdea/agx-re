# EXP-0184 — PRE-REGISTRATION (frozen before any build or device run)

**Target:** Apple A18 Pro / **G17P** (`applegpu_g17p`, `AGXAcceleratorG17P`, 5 cores,
macOS 26.6, Metal family Apple9), `users-MacBook-Neo.local` / `192.168.10.243`.
Nothing runs on the M4; the M4 is the repo host and analysis machine only.

**Clean-room provenance:** `HW-PROBE` + `OWN-SHADER`.
**Inputs inspected:** only `kernels/*.metal`, which we authored, and their compiled
`_agc.main` bytes. **Apple binary introspection: NONE.**

---

## 1. The question

Four instructions in `tools/agx-isa/emit_worklist.py`'s **ONE FIELD AWAY** list are blocked by a
single field each. Can an emitter *choose* that field's value and get documented behaviour on
G17P — or is the field a proven don't-care, or is the descriptor simply wrong?

| instruction | blocking field | span | current label | why it is still open |
|---|---|---|---|---|
| `rt_query_traverse` | `dst` | bits 4..7 (byte0 high nibble) | `untested`, `range: "none"` | **never swept, on any target.** |
| `if_push` | `scope` | bits 16..23 (byte+2) | `untested` | EXP-0140 swept 256 values on **one** carrier, 0 moved; EXP-0164 withheld it. |
| `cvt_f2i` | `b9` | bits 72..79 (byte+9) | `untested` | EXP-0144, same one-carrier withhold. |
| `copysign` | `operands` | bits 24..31 (byte+3) | `untested` | EXP-0138, same one-carrier withhold. |

EXP-0164's withhold reason is identical in all three cases and is the thing this experiment is
built to fix: *"256 values dispatched, **1 carrier** tested, 0 observations moved. Never moved
anything on the ONE carrier tried, so the probe could not have shown liveness either way. Needs a
second, structurally different carrier."*

## 2. Ownership reconciliation (against the live worklist, not the dispatch text)

- **EXP-0182 owns `tools/agx-isa/isadb.py`; EXP-0183 owns `tools/agx-isa/db.json`.** Neither is
  read or written here. `pinned/db.json` (`1ada4e7b…`) and `pinned/isadb.py` (`9cda47a1…`) were
  snapshotted **before any other work** and every resolution is by absolute path with a **hard
  exit if absent** (`harness/locate184.py::pinned_dir`, `harness/saferunner184.py::_import_persistrun`).
- **Skipped, owned by EXP-0183:** `half_alu.dst`, `falu2_uni.dst`, `reg_move_cb.dst`,
  `half_alu_fma12.ext`, `iter_at.grp`.
- **Skipped, declined four experiments deep:** `ret.scoreboard` (EXP-0179 declined it **on a
  control that FIRED**), `dev_scoreboard_fence.scope_flag`.
- **Skipped, already measured inert on multiple carriers:** `simd_ballot.cache`,
  `simd_shuffle.cache`, `imageblock_store.b4`, `frag_color_store.store_mode`, `vtx_out_pos.slot`,
  `iter.b9`.
- **Declined here, each with a named reason** (§8).

## 3. Priority, and why

`rt_query_traverse.dst` is TIER 1 because it is the only field in the list that has **never been
swept at all**, while **two sibling fields of the same instruction are `hardware-run` and
demonstrably load-bearing** on A18 (EXP-M4-14: `opB` ∈ {0x42,0x48,0xc8} gives the correct near
hit, eight values skip it, four HANG the traversal; `sel` 0x07/0x0f preserve correctness and other
values corrupt operand selection). A destination-register selector on that op is the strongest
prior in the whole one-field-away list.

`if_push.scope` is TIER 1 because the reason it read inert is *diagnosable*: the dimension it is
modelled to control is **nesting parity**, and no prior arm ever varied nesting depth. That is the
`iter_at.loc` failure exactly (EXP-0164: eight carriers at `samples=1` are one carrier) and the
`get_sr.form` story (declined on eight arms, live on the ninth — the one that changed *stage*).

`cvt_f2i.b9` and `copysign.operands` are TIER 2: cheap on the same harness, and a bounded negative
on carriers that genuinely span the dimension is a real deliverable.

## 4. Hypotheses, expected observations, refuters

**H1 — `rt_query_traverse.dst` is a live destination-register selector.**
*Expect:* on a committed-distance / committed-primitive-id intersection_query carrier, changing
the byte0 high nibble away from its compiled value relocates where the traversal result lands, so
the observed scalar stops being the oracle (1.0 / 2.0 / 10.0 / 4.0) and becomes a wrong value, a
silent zero, or an unwritten (still-poison) word. A subset of the 16 values may reproduce the
baseline (aliasing).
*Refuter:* all 16 values reproduce the baseline vector on every carrier **while the `opB` control
at the same occurrence moves** → `dst` is not a destination selector here and is INERT-ROBUST.
*Second refuter:* the 16 values move but the tokenized mnemonic changes → the "movement" is a
different instruction, not this field (two fields were withdrawn for exactly this on 2026-08-30).

**H2 — `if_push.scope` selects the reconvergence mask bank, and is only observable when
nesting parity actually varies.**
*Expect:* on a 32-lane dispatch, at least one carrier in the depth-1/2/3 ladder shows values that
change the per-lane result vector — lanes taking the wrong branch, lanes never written, or the
whole dispatch masked off. db.json names 0x54 (outer/even) and 0x56 (nested/odd); the strong form
predicts that forcing the *inner* push to the outer bank corrupts reconvergence at depth ≥ 2 while
being harmless at depth 1.
*Refuter:* 0 of 256 values move on **all** depth-1, depth-2 and depth-3 carriers while the
`scope_kind` control fires on each → the field is INERT-ROBUST and nesting parity is not it.
*Known hazard, pre-registered:* EXP-0179 found an unconditional `if_push` with `scope_kind == 0x01`
masks off the only lane of a **one-thread** dispatch in BOTH banks. Every carrier here is
**grid 32 / threadgroup 32** for that reason. EXP-0168 hung on this field; hangs are expected
and are **results**, and there is no abort path (§6).

**H3 — `cvt_f2i.b9` is a reserved don't-care.**
*Expect:* 256 values, no movement, on carriers spanning four destination integer types and two
source widths, with the `dst` control firing on each.
*Refuter A:* movement on any carrier → live, and the dimension is readable from *which* carriers
move. *Refuter B:* faults/hangs/corruption of the following instruction → the modelled **length 10
is wrong** and byte+9 is the next instruction's leader (a first-class db defect, protocol §6).

**H4 — `copysign.operands` (byte+3) is a don't-care, and `db.json`'s copysign descriptor is wrong
about which byte carries the operand.**
*Expect:* byte+3 inert across 256 values on five carriers spanning operand provenance
(load-sourced / ALU-sourced / mixed / two-occurrence / result-consumed — EXP-0129 showed operand
provenance is a real Apple9 axis), **while byte+1 — which `db.json` models as a fixed match
constant `0xc2` — moves.** EXP-0138 measured byte+1 live on M4 (240/256 silent zero, 8 → −5.0,
8 → +5.0) and byte+2 a 256/256 don't-care; this is the G17P half of that, and byte+1 doubles as
this arm's detection-power control.
*Refuter:* byte+1 inert on G17P → either the M4 result does not transfer (a per-target fact worth
recording) or the carrier is dead, and in the latter case **no verdict may be written on byte+3.**

## 5. Confounders, and what is done about each

| confounder | mitigation |
|---|---|
| **The observable co-varies with the field** (protocol 3a; EXP-0140 swept `uniform_mov.dst` while building its read-back out of the swept dst, so "0 moved" was the only answer the test could give). | None of the four observables can be named by its field. `rt_query_traverse.dst` is read through the kernel's own `out[0]` store at a fixed address; `if_push.scope` is read through 32 fixed per-lane words; `cvt_f2i.b9` and `copysign.operands` are read through fixed output words while the swept bytes are **not** the dst byte (`cvt_f2i.dst` is byte+3, swept only as a control). |
| **Carriers identical in the dimension the field controls** (EXP-0164; `get_sr.form` declined on eight arms). | Carrier sets are chosen *for* the dimension: nesting depth 1/2/3 + loop + loop-with-if (`scope`); four destination integer types + a 16-bit source (`b9`); five operand-provenance shapes (`operands`); four query getters across the candidate and committed phases, up to 4 occurrences each (`dst`). `analysis/gen_arms.py` additionally prefers occurrences whose **baseline field value** differs, and the verdict records `distinct_baseline_field_values`. |
| **A false hang cascade from a mere watchdog timeout** (protocol 3d, widened 2026-08-30; EXP-0178 proved all four "hangs" in its pilots were manufactured on a case the hardware handles cleanly). | `harness/saferunner184.py`: exactly one reader thread per child, tagged by owner; a malformed response is recorded as `measurement_failure` **with the raw lines kept**, never as a hang. The shared `tools/agxtest/persistrun.py` is used unmodified as a base class and is not edited. |
| **A per-field hang budget hiding a contiguous hazard** (protocol 3c; `frag_color_pack.dst`'s exact wall at 0xC0 was missed by three experiments, each discovering exactly two more bad values). | **There is no hang budget.** Every value in every arm is dispatched. Declared as a hazard-mapping pass in `PROGRESS.md` as a courtesy before the control-flow sweep. |
| **A wrong value returning a silent zero rather than a fault** ("absence of a fault proves nothing": 256 `rt_index` values on four carriers, not one fault). | Poisoned read-back (`0xDEADBEEF + i`) on every output word; a word still holding its poison is `not_written`, never `silent_zero`. Every oracle is non-zero except convert lane 6 (0.5 → 0), which is excluded from the match test and reported separately. |
| **A contaminated dispatch reporting `STATUS OK` and writing nothing** (EXP-0160: 25 such cases, no `InnocentVictim` string anywhere). | An integrity sentinel written **before** the tested instruction through an independent path; `sentinel_ok == False` ⇒ `invalid_run`, re-run up to 3×, never scored. A tail region that nothing stores to must stay poison. |
| **`InnocentVictim` from a sibling experiment's reset** (protocol §7). | The OS fault-classification string is recorded on every non-OK case; `InnocentVictim` responses are retried before anything is scored, and every non-OK case is confirmed majority-of-3. |
| **"Movement" that is really a different instruction** (two fields withdrawn 2026-08-30). | The **tokenized mnemonic of the mutated bytes** is recorded on every case, and `encodable_range` counts only values that still re-decode as the target mnemonic. |
| **A push that silently did not arrive** (EXP-0179 burned a run id on a stale harness). | `harness/verify_remote.py` hashes the frozen blobs **on the device** and is run as a **separate, unchained step** whose exit code gates the capture. |
| **`device_load` asynchrony (DEF-0169-1)** fabricating movement against a refreshed baseline. | No arm diffs against a periodically-refreshed baseline. The comparison baseline is the **arm-open unmutated dispatch**, recorded once per arm; mid-arm and close baselines are health checks only. |
| **A stale/renamed descriptor under a sibling's edits.** | Everything resolves through `pinned/`; `start`/`width` in the verdict are re-read from the pinned `db.json`. |
| **Repo `HEAD` moving mid-sequence** (EXP-0082). | The contract records the revision **at pre-registration time** and captures are compared against that recorded value, never against live `HEAD`. |

## 6. The promotion gate (frozen; no verdict may be written any other way)

Implemented by `analysis/verdicts.py` and nothing else. A field is promoted only if **all** hold:

1. **Two gated runs**, `run01` and `run02`, byte-identical programs, the same frozen `arms184.json`.
2. **≥ 99 % per-value cross-run agreement** on the outcome partition (`outcome` + the exact
   observed value vector), **and `moved >= 2 * disagree AND moved >= 1`**.
   Written that way deliberately: **`moved >= 2 * max(disagree, 1)` silently cannot promote any
   width-1 field**, because a 1-bit field has two values and `moved` can be 1.
3. The arm's **control** — a field on the SAME instruction at the SAME occurrence, already known
   live — moved in both runs. An arm whose control never fires is **barred from supporting any
   verdict, inert or live.**
4. The arm-open and arm-close baselines are both `ok`.
5. For a never-moving field, rule 2 is satisfied by the **carrier set**: the carriers must differ
   in the dimension the field controls.

**Label policy.** `LIVE → hardware-run`. `INERT-ROBUST → single-template-inference`, **not**
emitter grade — emitter grade asserts the implementer may *choose* the value, and "emit what the
compiler emitted" is a captured-template dependency. `STILL-UNDERPOWERED → untested` (do not round
up). `DECLINED →` the field keeps its current label and the reason is recorded.

**Machine-readable coverage on every verdict row:** `values_dispatched`, `distinct_bytes` (counted
from **distinct `bytes` strings in `raw/`**, never the dispatched-value count), `encodable_range`
(values that still re-decode as the target mnemonic), `start`, `width` — the last two re-read from
the pinned `db.json`.

## 7. Frozen procedure

1. Freeze this file + `CAPTURE_CONTRACT.json` (sha256 of every kernel, harness file, analysis
   script, `run.py`, and the pinned `db.json` / `isadb.py` / `agxparse.py` / `persistrun.py` /
   `shdump.m`). **Done before any build.**
2. Stage `~/agxre/EXP-0184/` on the neo; build `work/bin/{shdump, agxrun_persist, agxrun_persist_as}`
   with `clang -fobjc-arc -O2 -Wno-deprecated-declarations -framework Metal -framework Foundation`.
   **Then run `harness/verify_remote.py` as a separate, unchained step** and require exit 0.
3. **Pre-freeze census** (`analysis/census.py`) → `raw/prefreeze/census.json`. Calibration only;
   **no verdict may cite it.** It answers: does each carrier compile with the exact pipeline the
   sweep will use, does it emit the target instruction, how many occurrences, at what offsets, with
   what baseline field value, and what the pinned tokenizer decodes there.
4. **Pilot** (`--limit-values`, into `raw/prefreeze/`): a coarse pass to measure hang density and
   per-case cost before committing a gated run id. **No verdict may cite it.**
5. `analysis/gen_arms.py` → `harness/arms184.json`, then **frozen** (contract amendment §9), pushed
   and re-verified. Selection rule frozen in that file's docstring.
6. `run01`, then `run02`, into `raw/<run_id>/sweep.jsonl`, one JSON object per case,
   `flush` + `fsync` per line. **Run ids are never reused; a partial run is retained, never topped
   up, never deleted.**
7. `analysis/verdicts.py run01 run02` → `analysis/field_verdicts.json` (flat `<mnemonic>.<field>`)
   + `db_defects`. Then `RESULTS.md`.

**Environment / timeouts (frozen):** request watchdog **8.0 s** (compute) / **20.0 s**
(intersection_query); `CONFIRM_ATTEMPTS = 3`; `INNOCENT_RETRIES = 3`; `CANARY_RETRIES = 3`;
`BASELINE_EVERY = 200`; **no hang budget**. Compute carriers: grid 8 / tg 8 (copysign, convert),
grid 32 / tg 32 (control flow), 64–160 byte outputs. Ray-query carriers: grid 1 / tg 1, the
primitive acceleration structure built by `harness/agxrun_persist_as.m` (two geometries,
four non-opaque triangles at z = 3, 2, 1, 4).

**Raw record schema, frozen** (protocol §4), one object per case:
`carrier, arm, instr, field, value, bytes, token, observed, oracle, match, outcome, status,
statuses, fault_classes, innocent_retries, role, occ, off, instr_len, start, width, note, ts`
with `outcome ∈ {ok, silent_zero, wrong_value, fault, hang, undecodable, not_written, invalid_run,
nondeterministic, measurement_failure}` (plus the two carrier-level markers). `observed` carries
`status`, the value vector as both typed values and raw u32, the sentinel word, the poison tail,
the unwritten-word list, and `gputime_ns`.

## 8. Declined before any device time — each with a named reason

| field | reason |
|---|---|
| `iadd2.b2_fmt` | EXP-0171 already swept it dense and found it inert, refuting its own H6. Re-litigating costs device time for no new information. |
| `n4_cf_word.b3` | EXP-0172 already dispatched all 256 values and reported **STILL-UNDERPOWERED / `untested`**: no arm had power. A fourth pass needs a new instrument, not another sweep. |
| `cubearray_coord_const.b3` | Declined on a **measured** basis: 0 occurrences across 24 carriers (EXP-0148 corpus: 0 firings in 1080 files; its signature sits *interior* to a 12-byte `tex_addr_setup` token). 24 carriers tried. |
| `mesh_out_src.sel` | Same measured basis: 0 occurrences across 24 carriers, and reaching it needs a mesh-stage render carrier this experiment does not build. |
| `n4_rt_word.dst` | In scope in principle — it shares the ray-query carrier — but deferred rather than half-done: TIER 1 consumes that carrier's device budget, and a second RT field would dilute both. Named as the recommended next step. |
| `ret.scoreboard`, `dev_scoreboard_fence.scope_flag` | Declined four experiments deep. EXP-0179 declined `ret.scoreboard` **on a control that fired** — it built an ordering observable from `device_load` asynchrony, proved it fires as a clean monotone step, and the field still did not move it across all 16 values. Not re-litigated without a genuinely new instrument. |

## 9. What this experiment will NOT do

No `git commit`. No edit to `tools/agx-isa/db.json`, `tools/agx-isa/isadb.py`,
`tools/agx-isa/validation.json`, `docs/`, `PROVENANCE.md`, `CLAUDE.md` or `CODEX.md`. No edit to
the neo's shared `~/agxre/tools/`. **No `macvdmtool`, ever** — if the host stops answering this
experiment STOPS and reports BLOCKED. Nothing outside
`experiments/EXP-0184-g17p-onefield-b/` on the repo host and `~/agxre/EXP-0184/` on the neo.

## 10. Amendment log (append-only once frozen)

*(none yet)*

- **2026-08-30, after the pre-freeze census, before any gated run id was spent.**
  `analysis/gen_pilot.py` was added (and `harness/arms_pilot.json` generated from it) to run a
  **calibration pilot into `raw/prefreeze/`**. No verdict cites it; §7.4 already reserved a pilot.
  Its purpose is one thing the census cannot settle without the device: EXP-M4-14 found only **one
  of eighteen** rtq ops in its kernel was on the committed path, and our census found **14
  `rt_query_traverse` occurrences per ray-query carrier**. Choosing four of those fourteen blind
  would very likely sweep four *inert* occurrences and report a confident, meaningless INERT. The
  pilot probes every occurrence with the `opB` control before any occurrence is frozen into a
  gated arm. It also measures control-flow hang density (the gated run has **no abort path**) and
  per-case wall-clock cost.
- **2026-08-30, same point.** The census result is recorded here because it *changed the carrier
  set*, and the drops are measured negatives, not failures:
  `cs_alu`, `cs_mix`, `cs_two` emit **0** `copysign` (5 authored, **2 emit it**: `cs_load`,
  `cs_chain`); `cf_if1`, `cf_loop`, `cf_loopif` emit **0** `if_push` (5 authored, **2 emit it**:
  `cf_if2` with 3 occurrences, `cf_if3` with 7). All five convert carriers and all four ray-query
  carriers emit their target. **Every `if_push` our G17P compiler emitted for a 3-deep if/else
  ladder is `0f 05 54 01`** — `scope` = 0x54 at all seven pushes, with no 0x56 anywhere; db.json's
  "ping-pongs 0x54/0x56 with nesting parity" derives from a *loop* ladder (EXP-M4-13 R6, M4) and is
  **not** reproduced by if-nesting on G17P. That is an observation about the compiler, not yet
  about the hardware, and the sweep tests the hardware question directly by dispatching 0x56 (and
  every other value) at an outer push.
- **2026-08-30, after the calibration pilot, before any gated run id was spent.**
  `MAX_OCC_PER_CARRIER` in `analysis/gen_arms.py` was raised from `{cs:1, cvt:1, cf:3, rq:4}` to
  `{cs:1, cvt:1, cf:10, rq:14}` — i.e. **every** occurrence in every carrier is now swept, and the
  selection rule's "prefer an unseen baseline value" ordering no longer discards anything. The
  reason is the pilot's central result: the `opB` reachability control fires at **3 of 14**
  `rt_query_traverse` occurrences and is silent at the other 11, so a cap of 4 would very likely
  have frozen four *unreached* occurrences and produced a confident, meaningless INERT verdict on
  a field that in fact moves. Raising the cap can only ADD arms; it removes no arm and changes no
  threshold in §6. Nothing else in the selection rule changed.
- **2026-08-30, after `gen_arms.py` ran, before any gated run id was spent.** `harness/arms184.json`
  (147 arms, 7176 cases) and `harness/arms_pilot.json` were added to the contract's
  `authored_sha256` so the frozen contract covers the **generated arm list the device actually
  executes**, not merely the generator. `analysis/contract.py`'s file list is the only other blob
  that changed. From this point `harness/arms184.json` is frozen and is not edited again;
  `harness/verify_remote.py` re-checks it on the device before every gated run.
- **2026-08-30, AFTER both gated runs, analysis only.** Three post-run changes, all to analysis
  code, **none to a gate threshold and none to a raw capture**:
  (a) `analysis/verdicts.py` now routes a `_`-prefixed pseudo-field — a probe of a byte the pinned
  descriptor models as a fixed MATCH CONSTANT — out of `verdicts` into a separate
  `match_byte_probes` section, because changing such a byte changes *which instruction the bytes
  are* (`encodable_range` collapses to 1) and it therefore cannot carry a field label however
  cleanly it moves. This is a **strengthening**: it can only remove a promotion, never add one, and
  it removed exactly one (`copysign._b2_match`, which the first pass had labelled `hardware-run`).
  (b) the same file's inert/live *note text* now reports "N of the M arms that had detection power
  (K swept in total)" instead of "N of K", which was misleading for `rt_query_traverse` where 46 of
  56 arms sit on occurrences the query never executes.
  (c) `analysis/partitions.py` and `analysis/finalize.py` were added; both are pure derivations
  from `raw/`. `AGREE_MIN`, the movement rule, the control rule, the baseline rule and the label
  policy in §6 are **byte-for-byte unchanged**, and the verdicts were recomputed from `raw/` after
  the edit rather than carried over.
