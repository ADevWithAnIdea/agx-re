# PRE-REGISTRATION — EXP-0140 (M4): making the MOV and control-flow families EMITTABLE

**Frozen before any gated run.** Target: **local Apple M4 / G16G only.** No SSH, no A18,
no M5, no `macvdmtool`.

Governing documents: `CLAUDE.md`, `CODEX.md`, `experiments/SUBAGENT_BRIEF.md`,
`experiments/FIELD-SWEEP-PROTOCOL.md` (including the new §7), `docs/evidence-classification.md`.

---

## 1. Question

23 instructions in `tools/agx-isa/db.json` are decodable but **not emittable**, blocked by
51 fields that are not `hardware-run`/`isolated-byte-diff`:

* **MOV (10 / 25 fields):** `get_sr` `mov_imm` `psel` `reg_move_c0` `reg_move_c1`
  `reg_move_c2var` `reg_move_c9` `reg_move_cb` `sel` `uniform_mov`
* **CF (13 / 26 fields):** `call` `call_indirect` `frame_prologue` `if_push` `if_push_pred`
  `jump` `jump_cond` `link_save_restore` `mask_op` `pop_reconverge` `ret` `ret_luse` `stop`
  (`frame_prologue`, `link_save_restore`, `stop` are already emittable and are not touched.)

**Can an emitter choose an arbitrary value for each of these fields and get the documented
behaviour on real hardware?**

## 2. Hypotheses and refuters

| # | Hypothesis | Refuter (pre-registered) |
|---|---|---|
| H1 | `mov_imm.dst` is a 4-bit GPR selector: `mov_imm(D,99)` writes **only** r_D. | Any D where the value does not land in r_D, or where a second register also changes (12-register aliasing scan). |
| H2 | `sel.body` decomposes into three located byte-fields; **byte+3 is the predicate-FALSE operand**, an 8-bit immediate whose value is the byte itself for byte+3 ≥ 0x80, and an unwritten register/other-file operand (reading 0) below 0x80. | Any byte+3 ≥ 0x80 whose false-arm output ≠ the byte; any byte+3 < 0x80 whose false-arm output ≠ 0. |
| H3 | `psel` behaves the same way in its `sel` byte (byte+3). | As H2, on `gsel4`. |
| H4 | The five `reg_move_*` descriptors plus `uniform_mov` are **ONE** 4-byte instruction `(dst<<4)\|0x0B, src, form, opdesc`; only `form=0x01, opdesc=0x08` moves a value. | Any other `form`/`opdesc` pair that moves the value; or `form=0x01,opdesc=0x08` failing to move it. |
| H5 | `uniform_mov.usrc` ≥ 0x80 materialises the **immediate** `usrc & 0x7F`; usrc < 0x80 selects a uniform register, pair-quantised, with our four bound constants at usrc {0x18,0x19}, {0x1C,0x1D}, {0x20,0x21}, {0x24,0x25}. | Any usrc ≥ 0x80 not equal to `usrc & 0x7F`; any of the eight mapped indices not returning its bound magic constant. |
| H6 | `get_sr` still reads `thread_position_in_grid.x` for the compiler-natural `form`/`dp_width`/`dp_marker`; the sweep establishes which other values are inert, corrupting, or fatal. | The natural triple failing to produce the per-lane tid vector. |
| H7 | The CF fields (`if_push`, `if_push_pred`, `jump`, `jump_cond`, `pop_reconverge`, `ret`) can be given arbitrary byte values inside a **frozen, HW-validated** skeleton and the result is classifiable as inert / wrong / faulting / hanging. | The unmutated skeleton failing to reproduce its host-computed oracle. |
| H8 | `jump_cond.offset` reach is **not** transferable from `jump` (EXP-0115 measured it on `jump`) and is a checkerboard, not a threshold. | A contiguous working range across the structured offset set. |

## 3. Independent / controlled variables

Independent: exactly ONE named field (or one body byte) per case. Controlled: carrier kernel,
buffer bindings, dispatch shape, input vectors, every other field of every other instruction,
all branch displacements (never recomputed — see §6).

## 4. Carriers (all authored by us; `_agc.main` lengths re-derived per run by `harness/baseline.py`)

| id | kernel | main | role |
|---|---|---|---|
| `uni` | `kernels/carrier_uni.metal` | 300 B | whole-`_agc.main` replacement; four `constant int&` args force a constant program that preloads the **uniform file with values we bind** → the ground-truth oracle for `uniform_mov` |
| `dsel5` | `kernels/dsel5.metal` (EXP-0010) | 46 B | in-place patch of the 4-byte `sel` at `+0x18` |
| `gsel4` | `kernels/gsel4.metal` (EXP-0010) | 32 B | in-place patch of the 4-byte `psel` at `+0x0A` |
| `cf` | `kernels/carrier_cf2.metal` | 200 B | whole-`_agc.main` replacement with EXP-0090/EXP-0112's HW-validated CF skeleton |

`carrier_cf2.metal` is EXP-0112's `carrier_cf.metal` plus a tail of extra arithmetic on `acc`
**alone** (no new buffer reference — EXP-0128's item (d) was confounded by exactly that), to
make room for the integrity-sentinel prologue. Its base_slot mapping is re-derived from its own
compile and asserted equal to the frozen skeleton's (2 = `a`, 1 = `n`, 0 = `out`).

## 5. Coverage (FIELD-SWEEP-PROTOCOL §3)

* every 8-bit field: **all 256 values**;
* `mov_imm.dst` (4 bits): all 16, plus four 12-register aliasing scans;
* `get_sr.dp_marker` (5 bits): all 32; `get_sr.form` (1 bit): both;
* `sel.body` / `psel` bodies (24 bits): all 256 values of each of the three bytes **× two input
  vectors** for `sel` and **two dispatch shapes** for `psel`, plus whole-field boundaries
  {0,1,2,max−1,max}, all 24 powers of two, and 16 asymmetric interior samples;
* `pop_reconverge.reserved` (16 bits): boundaries + all powers of two + 16 interior samples;
* `jump_cond.offset` (48 bits): a **structured, bounded** set — every valid instruction start
  offset in the frozen skeleton relative to the `jump_cond`, ±1..4 around the natural target,
  and a few far probes. **Never a dense displacement sweep** (the EXP-0128 hang construction).

Total **7976** cases per run; **two gated runs** (`run01`, `run02`).

## 6. Confounders and how each is controlled

1. **Branch displacements.** Never recomputed. The CF skeleton's instruction sequence, lengths
   and both displacements are frozen; an override changes one named field only.
2. **Non-local tokenization (EXP-0148).** Our decoder's verdict on the spliced region is
   recorded per case (`rt`) but never gates a case: the hardware does not consult our decoder.
3. **Over-long decode of the swept `0x?B` byte+2.** Under the corrected L4 rule that group can
   be 4 or 10 bytes. Every `regmove` case therefore places **6 bytes of inert
   `mov_imm(pad,0)`** after the 4-byte test instruction, so even a 10-byte decode consumes only
   padding and never the following store's leader.
4. **`base_slot` is decided from the whole kernel body** (EXP-0112's trap): re-derived by
   `baseline.py` from each carrier's own compile and asserted.
5. **GPU contention / innocent-victim faults** (protocol §7) — see §7 below.
6. **"STATUS OK, nothing executed"** (EXP-0141) — see §7 below.
7. **`mov_imm` immediates** are restricted to 0..127 except in the two pre-registered boundary
   cases; the immediate **12** is avoided everywhere (it is the only 0..127 immediate whose
   2-byte encoding fails to tokenize under the current length rule — this experiment's own
   exhaustive static check).

## 7. Contamination defences (FIELD-SWEEP-PROTOCOL §7 + EXP-0141 + EXP-0143), all frozen

* **D1 — unique splice-archive path per request**, unlinked after use.
* **D2 — pre-poisoned output buffer + integrity sentinel.** Buffer 0 is bound as an *input*
  filled with `POISON_WORD(i) = 0xDEADBEEF + i`; on `uni` and `cf` the generated program's
  first three instructions store `SENT_VAL = 91` to a dedicated word through a path that runs
  **before** and is independent of the instruction under test. A measurement whose sentinel is
  missing — or, on `dsel5`/`gsel4` (46/32-byte compiles with no room), whose every oracle word
  is still poison — is `invalid_run` and is repeated.
* **D3 — never conclude `fault` from one observation.** Every case is replicated: 2 trials, and
  a 3rd whenever the first is not `ok` or the first two disagree; the majority wins.
  `...ErrorInnocentVictim` is recorded verbatim and classified `invalid_run`, never `fault`.
  Every trial's status and OS fault-classification string is kept in the record.
* **D4 — periodic baseline re-validation** every 250 cases: the unmutated carrier is re-run and
  checked. A failure restarts the runner process and re-checks; a second failure aborts the run
  rather than recording a cascade as data. Every check is a `baseline_check` record in the log.

**Concurrency to be stated in `RESULTS.md`:** this experiment is scheduled in batch 2 with
EXP-0144 (PACK) and EXP-0147 (pipeline misc).

## 8. Safety (FIELD-SWEEP-PROTOCOL §8)

Per-request watchdog 8 s. **Two genuine hangs in one (instruction, field) arm stop that arm**;
6 hangs across all CF arms stop every remaining CF arm; 10 hangs stop the run. Skipped cases
are written as `skipped` records. Append + `fflush` + `fsync` per case. `PROGRESS.md` entry per
milestone. Never `macvdmtool`; never touch the A18.

## 9. Raw-record schema (`raw/<run_id>/sweep.jsonl`, append-only)

One JSON object per case with at least the protocol §4 keys —
`instr field value bytes observed oracle match outcome carrier note` — plus
`i group arm expect_match status mode dispatch inputs rt attempts fault_class
trial_statuses trial_outcomes trial_errors replicates unstable sentinel_ok prog_sha256`.
`outcome` ∈ `ok | silent_zero | wrong_value | fault | hang | undecodable | invalid_run |
skipped`. `baseline_check` records use `kind:"baseline_check"`.
`raw/<run_id>/00_inputs.json` freezes carrier facts, tool/harness/kernel SHA-256s, the git
revision at capture time and every budget.

## 10. Success / failure criteria

A field reaches `hardware-run` only if its swept values executed with a **host-computed
oracle**, the coverage in §5 was met, the two gated runs agree, the sentinel held, and the
pre-registered falsifier for that group **failed as predicted**. Anything less is reported as
`corpus-correlation` or `untested` — never rounded up. An instruction is reported **emittable**
only when *every* field an emitter must fill is `hardware-run` or `isolated-byte-diff`.

**Clean-room provenance:** HW-PROBE + OWN-SHADER. Inputs inspected: our own MSL
(`kernels/*.metal`) and its compiled bytes, plus instruction bytes assembled by our own
`tools/agx-isa`. **Apple binary introspection: NONE.**
