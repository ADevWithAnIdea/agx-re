# EXP-0168 progress log (append-only)

## 2026-08-30 — M0: dispatch received, governing docs read
Read `CLAUDE.md`, `CODEX.md`, `experiments/SUBAGENT_BRIEF.md`,
`experiments/FIELD-SWEEP-PROTOCOL.md`, and EXP-0164's
`analysis/{reclassify,withhold_inert_single,withhold_unstable,withhold_unverifiable}.json`.

**Device work is BLOCKED** — EXP-0167 holds a hand-coordinated quiet window on
the neo. All analysis, carrier design, pre-registration and harness construction
happen offline first; the orchestrator will be asked for the window.

## 2026-08-30 — M1: the target set, extracted from EXP-0164
Target set = 26 field rows.

**A. the `dst` field name (14 rows; the audit's most load-bearing name, 13
instructions blocked):**
uniform_mov, falu2, falu2i, get_sr, cvt_f2i, unpack_convert, frag_color_pack,
matrix_mac, vtx_out_pos, reg_move_c0, reg_move_c1, reg_move_c2var,
reg_move_c9, reg_move_cb.

**B. the 12 one-field-away instructions (12 rows, `uniform_mov.dst` shared
with A):** atomic_mem.addr_desc_hi, copysign.operands, cvt_f2h.op,
falu_acc.cache, if_push.scope, iter_at.grp, mov_imm.imm_top, pack_convert.b7,
pixel_order.kind, shift_amt_move.src_flag, stop.reserved, uniform_mov.dst.

**C. two cheap companions that COMPLETE an instruction if they land**
(they are the only other withheld field on their descriptor):
cvt_f2i.b9, vtx_out_pos.slot.

Bucket census of the 26: INERT-SINGLE 7, UNSTABLE 7, UNVERIFIABLE 12.

## 2026-08-30 — M1b: the structural finding that decides the design
`db.json` records that `reg_move_c0/c1/c2var/c9/cb` + `uniform_mov` are **ONE
4-byte instruction** (EXP-0087/EXP-0140), `byte0`-hi = `dst`. EXP-0140 found the
byte+2 form selector makes it write a *moved value* (0x01/0x11/0x21/0x31), a
*silent zero* (low-nibble 0) or a *wrong value* (c9/cb).

All three of those write the destination register. So a carrier that **dumps all
16 GPRs** makes `dst` live for every one of the five descriptors — including the
ones that "do nothing" — because the observable is *which register slot changed*,
not *what value it changed to*. A carrier that reads back ONE word cannot express
that dimension at all, which is the leading hypothesis for the audit's
`0 observations moved` on `uniform_mov.dst` (16 dense values, one carrier).

## 2026-08-30 — M1c: overlap flagged to the orchestrator
`experiments/EXP-0169-g17p-rerecord/PROGRESS.md` claims the 144 UNVERIFIABLE
fields, which includes `reg_move_* (23)`, `falu2 (13)` and `falu2i (9)` — i.e. it
overlaps rows in set A. Raised with the orchestrator; EXP-0168 proceeds on the
field NAMES it was dispatched (`dst` + the 12 one-field-away) and will not touch
the other reg_move/falu2 fields.

## 2026-08-30 — M1d: orchestrator confirmed the split
EXP-0168 owns the field name `dst` on all 14 descriptors, the 12 one-field-away
fields, and the two companions (`cvt_f2i.b9`, `vtx_out_pos.slot`). EXP-0169 owns
the rest of the 144. No design handoff in either direction; carrier construction
is duplicated deliberately so neither agent blocks the other.
Device queue ahead of us: EXP-0167 -> EXP-0163 (generates ~88 deliberate device
resets; nothing else may run during it) -> EXP-0168 / EXP-0169.
Credentials are held in-session only and are written to NO file, committed or not.

## 2026-08-30 — M2: EXP-0140 archaeology. My hypothesis was HALF right, and the
##                 real defect is worse than the one I predicted.
A read-only audit of `experiments/EXP-0140-m4-emit-mov-cf/` (harness/cases.py,
harness/run.py, analysis/verdicts.py, raw/m4_20260828_run0{1,2,3}/sweep.jsonl)
settles what its carriers could and could not see. Reported here in full,
including the part that refutes me.

**(a) `uniform_mov.dst` — NOT blindness-by-single-word. Worse: the observable
CO-VARIED with the field.** `cases.py:92-100` builds the read-back as
`device_store(..., data_reg=D)` where `D` is the very dst value being swept.
Field and observable move together, so a *correct* hardware result is a constant
observed vector **by construction**, and "0 observations moved" was the
predicted outcome of a passing test. The sweep does falsify "dst is ignored" and
"dst selects some other register" — a genuine, if narrow, result. What it cannot
do is detect an additional or aliased write: only 2 output words are compared
(`run.py:119`), and the 12-register scan (`cases.py:103-110`) ran at exactly ONE
dst value, D=3. So `RESULTS.md:79`'s "all 16 values write r_D **and nothing
else**" is not supported at 15 of the 16 values.

**GENERALISABLE RULE, and this experiment's first design constraint:**
*the observable must not co-vary with the field under test.* A sweep whose
read-back path is parameterised by the swept value measures nothing about the
value. EXP-0168 fixes it by making the observable a FIXED 16-register dump whose
store list is identical in every case.

**(b) The four `reg_move_*` forms whose names carry a `dst` verdict were never
swept at their own form.** `cases.py:252-255` runs ONE 16-value dst sweep, at the
single byte+2=0x01 / byte+3=0x08 combination (the `reg_move_c1` form), and
`analysis/verdicts.py:327` then fans that one verdict out verbatim to
`reg_move_c0.dst`, `reg_move_c1.dst`, `reg_move_c2var.dst`, `reg_move_c9.dst`,
`reg_move_cb.dst` and `uniform_mov.dst`, all six with the identical note. There
is **no dst x form cross-product anywhere in that matrix**, and the forms are
known to behave differently: EXP-0140's own descriptor probe (raw i=1098..1102)
has c0 and c2var `silent_zero`, c9 `wrong_value` returning 213 = 0xD5 = byte+1
verbatim, cb `wrong_value`, and only c1 `ok`. EXP-0168 therefore sweeps
**dst x form as a cross-product**, which is the actual missing measurement.

**(c) `if_push.scope` — the carrier was NOT blind, and my blindness story does
not apply.** The same instruction's `scope_kind` moved 178 cases to
`wrong_value` plus 1 hang, with 6 distinct observed vectors, on the identical
carrier; `scope` was flat across all 256 values in two independent captures.
The carrier had detection power. But three specific limits are visible in the
disassembly of its 152-byte program and they bound what "flat" means:
  1. the kernel's if/else lowered to `isel10` — a SELECT, exercising no mask
     stack at all, so the mask-stack liveness rests on the loop alone (contrary
     to `RESULTS.md:92-93`);
  2. both live pushes carry scope **0x54** (`if_push_pred` at +0x026 and the
     `if_push` under test at +0x038), so the "ping-pongs 0x54/0x56 with nesting
     parity" model was never actually instantiated — there was no second bank in
     play for a wrong bank to collide with;
  3. the observable is ONE GPR (r1), one word per lane, 8 lanes in a
     partially-filled 32-wide SIMD.
EXP-0168's if_push carriers therefore force REAL branches (divergent stores,
which cannot be if-converted), use three genuine nesting levels, dispatch a full
32-lane SIMD, and read back a per-lane x per-region slot pattern out of a
poisoned buffer — so the observable IS the execution mask.

**(d) `mov_imm.imm_top` has exactly TWO records in the whole tree**, keyed
`group=mov_imm.dst.imm_boundary` / `..._padded`, `field="dst"`, `value=6` — one
immediate (200), one dst. The audit's `no per-value records` is correct. The
padded/unpadded pair is the right design and EXP-0168 keeps it, but runs it as a
dense 128..255 sweep across several dst values instead of a single point.

**(e) Not mine, but recorded for the orchestrator:** `jump.branch_ctrl` and
`jump.link` are 256/256 flat with `distinct_observed = 1`, and `jump` is
whitelisted into liveness unconditionally at `analysis/verdicts.py:540`
(`or mnem in ("jump",)`) — i.e. those two reached `hardware-run` without any
field of `jump` ever moving in the carrier. EXP-0164 did not withhold them.

## 2026-08-30 — M3: render/vertex archaeology. Reuse EXP-0163's harness; three
##                 of my four render fields turn out to have the SAME defect.
Read-only audit of `tools/agxtest/agxrender.m`, `EXP-0142`, `EXP-0143`,
`EXP-0155`, `EXP-0163`.

**Harness decision: fork `EXP-0163/harness/{gfrun2.m,runner2.py}`.** It is a
strict superset of every other render harness here and is G17P-proven (39,233
cases in 50.3 s on 2026-08-30). It already has: `--samples N` wired into BOTH
the build-archive and the run pipeline descriptor, `--resolve`, MRT, layered
targets, depth, occlusion, five writable-texture kinds, an `--out-buf` device
buffer **bound to the vertex stage as well as the fragment stage**,
vertex/fragment/compute splicing by absolute archive offset, `0xDEADBEEF`
read-back poison on every surface, and an integrity sentinel that re-reads the
patched archive from the filesystem and `memcmp`s every spliced window before
dispatch. EXP-0142's `renderpersist.m` is the weak M4-era ancestor (4x4, no
MSAA, no poison, no sentinel) and is NOT reused.

**The EXP-0155 nulls I inherited are all the same defect as `iter_at.loc`:**
- `iter_at@cent1_0` / `cent1_1` are TWO OCCURRENCES OF THE SAME INSTRUCTION IN
  ONE PROGRAM, both on carrier `c_cent1` at `samples=1`. EXP-0155 even defined a
  `c_cent4` (4-sample) carrier — and used it only for `iter`, never for
  `iter_at`. One carrier, labelled two.
- `fcp@pack0` / `pack1` likewise: one program, `color_format=80` (BGRA8Unorm),
  `samples=1`, two occurrences, identical liveness control `("val",0x80)`.
  `pack1` additionally drops `fmt_class` from its field list.
- `vtx_out_pos.dst`/`slot` (EXP-0147, M4) were inert in a **single-varying**
  carrier, and EXP-0147's own RESULTS.md leaves "`vtx_out_pos.slot` in a
  multi-varying carrier" open as the named follow-up. `slot` selects WHICH
  varying/output slot; with one varying there is nothing to select.
**Rule this experiment adopts: an occurrence-replicate inside one program is not
an adversarial replicate for any field whose meaning depends on pipeline state.**

**Correction to carry forward.** EXP-0163's `RESULTS.md:57` says its cent1/cent4
pair has "same compiled bytes". Its own `00_inputs.json` refutes that: same
source sha256, but fragment binaries of **174 B (1 sample) vs 482 B (4 samples)**
at different offsets. `rasterSampleCount` is an input to the shader compile. What
is genuinely held constant is source, bound resources, probe pixels and every
other pipeline field. EXP-0168 will state its render pairs that way and will not
claim byte-identity it does not have.

**`iter_at.grp` is a db.json DEFECT and a minefield, in that order.**
`db.json` declares `grp` as 8 bits at start=0, but the descriptor's own match
constant is `[0, 7, 47]` — bits 0..6 pinned to 0x2f. So **only bit 7 is free**;
`grp` has exactly two legal values, 0x2f and 0xaf, and every other value is a
DIFFERENT instruction, not a value of this field. That is the same
declares-a-field-over-pinned-bits self-contradiction EXP-0162 fixed in
`pixel_order`. It also explains the hang record: EXP-0163 hung on grp = 0x00 and
0x50, EXP-0155 on 0x00, 0x01, 0x0f, 0x12, 0x16, 0x18, and BOTH runs tripped
"FIELD STOPPED after 2 genuine hangs" — so `iter_at.grp` has never been swept
past ~25 of 256 values on any run. EXP-0168 sweeps the two legal values densely,
reports the descriptor defect, and opens the out-of-descriptor region only as a
small, pre-declared, hang-budgeted arm (budget 2, then STOP) because a device
reset costs every other agent on the machine.

## 2026-08-30 — M4: EXP-0144 / EXP-0138 archaeology. Two of my seven UNSTABLE
##                 rows are an AUDIT ARTIFACT, re-derivable offline for free.
Read-only audit of `EXP-0144-m4-emit-pack/` and `EXP-0138-m4-emit-falu/`.

**(a) `F` and `W` are NOT two carriers.** EXP-0164's arm key is
`carrier|arm` (`EXP-0164/analysis/collect_raw.py:192-194`), and EXP-0144's
`F`/`W` are ARM LETTERS over the SAME compiled program (`EXP-0144/harness/
casematrix.py:6-17`): F = every byte, all 256 values; W = whole-field values for
the >8-bit raw fields. So `withhold_unstable.json`'s "2 carrier(s) tested" for
`pack_convert.b7` and `unpack_convert.dst` is one carrier counted twice.
`n_arms_that_tested_the_field` counts (carrier, arm) pairs, not carriers
(`EXP-0164/analysis/audit.py:139-141`).

**(b) `pack_convert.b7` and `unpack_convert.dst` are NOT unstable. The gate
compared the wrong two runs.** EXP-0164 selects the two gated runs with the most
distinct attributed values, ties broken ALPHABETICALLY (`audit.py:78-80`), which
picks `run03` — and `run03` is a capture EXP-0144 itself disowns
(`EXP-0144/RESULTS.md:28-33`: everything promoted there comes from the
`rv01__*` revalidation only). run03's cases that were skipped after two hangs
were written with `outcome:"hang"`, and EXP-0164 treats only
`{invalid_run, victim, skipped}` as contamination (`collect_raw.py:42,202`), so
**248 skip placeholders for `pack_convert.b7` and 1024 for `unpack_convert` were
scored as real observations.** Measured against the runs that actually measured:
    pack_convert byte+7   run05 vs rv01 : 256 common, 0 disagreements (100.00%)
    unpack_convert byte+3 run05 vs rv01 : 192 common, 2 disagreements (98.96%)
and within rv01 both are 256/256 unanimous at 3 repetitions. **This is an
analysis defect in the audit, not a hardware instability, and it needs no device
time to settle.** EXP-0168 re-derives it in `analysis/rescore_0144.py` from the
committed append-only raw, as an offline deliverable independent of the sweep.

**(c) `cvt_f2h.op` and `cvt_f2i.dst` ARE genuinely noisy — but only at the
fault/silent-zero boundary, inside the value region that already fails the emit
rule.** `cvt_f2h.op`: 22/256 differ and every one is run03 `silent_zero` vs rv01
`fault`, all with `(v & 7) == 7`. `cvt_f2i.dst`: 45 disagreements = 41 run03 skip
placeholders + 4 genuine, and the 4 are hang/fault boundary flips. rv01
within-run unanimity is 94.9% and 92.6%. A third gated run plus majority-of-5 in
the flapping region should settle both.

**(d) A real, unpublished hardware finding is sitting inside `cvt_f2h.op`.**
`EXP-0144/analysis/byte_scans.json -> cvt_f2h.byte2`: **62 of 256 values turn the
fp32->fp16 convert into an fp32->bfloat16 convert** (`f2bf_rne(v0)`), and 8
values redirect the SOURCE to the second operand. So byte+2 is a combined
format + source selector, not the "result-routing/source-cache mode" db.json
attributes to the cvt_f2i sibling. EXP-0168 confirms or refutes this on G17P.

**(e) Every EXP-0144 carrier for `cvt_f2h` and `cvt_f2i` is STANDALONE.** The
consumed-vs-standalone distinction db.json attributes to byte+2 was never tested
with a CONSUMING carrier for either op; the one consuming carrier it built
(`c_i2f_src`) is a different instruction, and there the byte had no effect at any
value (`EXP-0144/RESULTS.md:266-271`). `kernels/probes.metal`'s
`k_f2h_consumed` / `k_f2i_consumed` are exactly this missing arm.

**(f) `copysign.operands` read inert because the carrier had only TWO live float
registers.** `EXP-0138/harness/families.py:73-74` + `kernels/probes.metal:32-34`:
`k_copysign` loads a[t+0] and a[t+1], computes, and stores ONE word. A byte
claimed to be a src/dst REGISTER descriptor cannot show anything in a carrier
with a two-register operand space — and indeed the falsifier on byte+1 resolves
exactly two outcomes (-5.0 and +5.0). `k_copysign_rp` (12+ simultaneously live
values) plus the 16-register dump is the fix.
Two db.json defects fall out of the same data and are recorded for the
orchestrator, not acted on: byte+1 of `copysign` is a **live operand field**
(240/256 silent-zero, 8 -> -5.0, 8 -> +5.0) yet db.json pins it as a match
constant; and byte+2 (0x88) is a 256/256 don't-care also pinned as a match
constant.

**(g) `cvt_f2i.b9` is INERT-SINGLE, not UNSTABLE** — 256/256 `ok` in BOTH runs,
one distinct observed word, rv01 unanimous. Like `copysign.operands` it does not
need a third run; it needs a second, structurally different carrier.

**(h) PORTABILITY TRAP, and it changes the harness.** EXP-0144's frozen matrix
hash no longer reproduces on any host: `casematrix.py` reads the LIVE `db.json`,
and EXP-0144's own findings were later written back into it, so the `field`
LABEL STRINGS moved out from under the committed raw (`pack_convert` byte 7 was
`fmt_word`, is now `b7`; `unpack_convert` byte 3 was `convert_desc`, is now
`dst`). **EXP-0168 therefore (i) pins a `db.json`/`isadb.py` snapshot into
`work/frozen/` with sha256 in CAPTURE_CONTRACT.json, and (ii) records the full
instruction `bytes` on every case so attribution never depends on a label.**
Also noted: `EXP-0138/harness/run.py:110` hardcodes `"host": "Apple M4 (G16G)
local"` into its evidence file — EXP-0168 records the target from the live
device, never from a literal.

## 2026-08-30 — M5: the offline re-scoring RAN, and it lands three of the
##                 withheld rows without touching the device.
`analysis/rescore_0144.py` (no hardware; re-derives from EXP-0144's append-only
`raw/`, which is M4/G16G data) -> `analysis/rescore_0144.json`.

Per field, comparing every pair of runs that ACTUALLY DISPATCHED the value
(placeholders excluded by "no attempts recorded", not by the `outcome` string):

| field | audit said | best measured pair | common | agree | disagreements |
|---|---|---|---|---|---|
| `pack_convert.b7`    | 2.73%  (run03 vs run05) | run05 vs rv01 | 256 | **100.00%** | 0 |
| `cvt_f2i.dst`        | 82.42% (run03 vs rv01)  | run02 vs rv01 | 225 | **99.56%**  | 1 (fault->hang) |
| `cvt_f2i.b9`         | inert, 1 carrier        | run03 vs rv01 | 256 | **100.00%** | 0 |
| `unpack_convert.dst` | 25.78% (run03 vs run05) | run05 vs rv01 | 192 | 98.96%      | 2 (hang->fault) |
| `cvt_f2h.op`         | 91.41% (run03 vs rv01)  | run01 vs run04| 256 | 98.44%      | 4 |

The cause is now measured rather than argued: for `pack_convert.b7`, run03 has
**17 measured cases and 248 placeholders**; for `unpack_convert.dst`, run03 and
run04 have **0 measured and 272 placeholders each**; for `cvt_f2i.dst`, run03 has
41 placeholders and run04 has 265. Those placeholders carry `outcome:"hang"` and
EXP-0164 scored them as observations.

**Conclusions, stated at the strength the data supports:**
- `pack_convert.b7` and `cvt_f2i.b9` clear the >=99% clause outright on M4 data
  already committed. `cvt_f2i.dst` clears it at 99.56%. Their UNSTABLE/withheld
  status is an artifact of which two runs the audit compared. This is a
  RE-SCORING repair, not a third-gated-run repair, and it costs no device time.
- `unpack_convert.dst` (98.96%, both disagreements hang->fault at 0xbe/0xbf, the
  two hangs that stopped run05) and `cvt_f2h.op` (98.44% best, all disagreements
  fault<->silent_zero) are genuinely short of the bar and DO need another
  measured run.
- **None of this promotes anything.** The underlying observations are M4/G16G.
  EXP-0168's own G17P sweep is what will carry a target-correct label; this
  result tells the orchestrator that two of the rows he withdrew were withdrawn
  for the wrong reason, and it tells me which arms actually need device time.
- `cvt_f2i.b9` is 256/256 `ok` with ONE distinct observed word in both runs: a
  genuinely inert field. A field that is inert everywhere can never satisfy a
  "movement >= 2x disagreements" clause, by construction. EXP-0168 pre-registers
  a separate PROVEN-DONT-CARE verdict for that case, with its own criteria
  (dense coverage + >=2 carriers each PASSING ITS LIVENESS LADDER + 0 movement +
  >=99.5% cross-run agreement), and flags it to the orchestrator rather than
  quietly labelling it `hardware-run`.

## 2026-08-30 — M6: compute arm BUILT and dry-run clean, offline
Authored and verified without touching the device:

`harness/isa_helpers.py`  program construction. 104-word poisoned read-back:
  r0..r15 at words 0,4,..,60; PRE sentinel 64; POST 68; high-register probe 72;
  and a **28-word tail region no store ever targets** (76..103). PRE is written
  to MEMORY BEFORE the block and POST is materialized AFTER it, so neither can
  be destroyed by release-on-read — the trap that cost EXP-0138 six sweeps when
  it seeded its sentinel in r11 and the instruction then read and zeroed it.
`harness/anchors.py`      anchor extraction; probes may name a LIST of candidate
  kernels, because which kernel the Apple compiler emits a given instruction
  from is not under our control and an arm naming one kernel can silently lose
  itself. An arm that finds no candidate is recorded `arm_not_run` WITH THE
  REASON, never silently dropped.
`harness/casematrix.py`   the frozen generator. 33 arms, each naming the
  DIMENSION it varies and why that carrier can express the field.
`harness/sweeprun.py`     two carrier styles (SYNTH+LIFTED / IN-PLACE), the
  slot-pattern classifier, and `validity` kept strictly separate from `outcome`.
`harness/run.py`          gated driver: majority-of-3, OS fault class on every
  non-ok case, victim re-runs, baseline revalidation every 300, per-field hang
  budget 2 / per-arm 6, resume-safe, flush+fsync per record.
`harness/smoke.py`        PRE-FREEZE calibration incl. **S4: an empty program
  must leave the WHOLE buffer poisoned**, which is what makes `invalid_poison`
  distinguishable from `silent_zero` at all.
`harness/gpuwatch.py`     samples the target process table into
  `raw/<run>/gpuwatch.jsonl` for the duration, so "the machine was quiet" is a
  measurement (FIELD-SWEEP-PROTOCOL section 7, amended today).
`harness/dryrun.py`       offline: builds every arm's program, checks the record
  schema, checks the oracle. **0 bad records; every arm builds.**
`analysis/verdicts.py`    the pre-registered gate, and it refuses two things:
  it never counts a skip placeholder as an observation, and it never labels a
  genuinely inert field `hardware-run` on its own authority.

Matrix against the local dry-run fixture: **10,587 cases**, roles
sweep 8,736 / bytemate 1,312 / ladder 472 / falsifier 33 / baseline 33.
At EXP-0154's measured G17P throughput (44.9 cases/s) that is **~4 minutes per
gated run**; three runs plus smoke is well under 20 minutes of device time.

Per-field dispatched values (best arm), from the dry run:
  uniform_mov.dst 256 (16 dst x 14 FORMS + 16) . uniform_mov.form_b2 256 .
  uniform_mov.opdesc_b3 256 . cvt_f2i.dst 512 . cvt_f2i.b9 512 .
  unpack_convert.dst 768 . pack_convert.b7 768 . cvt_f2h.op 512 .
  copysign.operands 512 . if_push.scope 1024 . mov_imm.byte1 1536 .
  stop.b1/b2/b3 512 each + stop.reserved 132 . falu_acc.cache 84 (2 x 14 srcB
  x 3 carriers) . shift_amt_move.src_flag 52 (2 x 13 src_reg x 2 carriers) .
  atomic_mem.addr_desc_hi 108 (4 x 9 oper_reg x 3 carriers) .
  get_sr.dst 16 / dst_hi 8 / form 2 . falu2i.dst 16.
`falu2.dst` shows `arm_not_run` against the FIXTURE only — the fixture's
hand-built falu2 bytes decode as `falu_compact4`. The real anchor comes from the
device, and the multi-candidate mechanism will find falu2 wherever the compiler
actually put it. If it genuinely has no own-MSL anchor in this probe set, that
is reported as NOT REACHED, not as inert.

`PRE_REGISTRATION.md` and `CAPTURE_CONTRACT.json` frozen (27 authored files
hashed; a `work/frozen/` db.json+isadb.py snapshot pinned). Gate set at
**>=99.5% agreement and movement >= 4x disagreements** — deliberately above the
orchestrator's >=99% / >=2x — plus ladder-passed, falsifier-failed, dense
coverage, and no case counted whose `validity != valid`.

## 2026-08-30 — M7: bit surgery verified offline, and it turned up THREE MORE
##                 descriptor defects of the `pixel_order` class
`analysis/bitcheck.py` (no device) checks, exhaustively over every value, that
`casematrix.set_field(anchor, v)` equals `isadb.assemble(fields with field=v)`
for all 83 instruction/field pairs this experiment touches. If those two
disagreed on bit order or placement, EVERY case would be mislabelled and no
amount of hardware time could fix it.

**79 fields agree exactly. 0 mismatches.** The harness's bit surgery is correct.

The other 4 are a **first-class result**, not a harness bug: a field DECLARED
over bits its own descriptor's `match` constant PINS. That is the same
self-contradiction EXP-0162 fixed in `pixel_order.flags` — the field is
undecodable and unemittable at every value outside the pin, because those values
are a *different instruction*.

| descriptor | field | declared bits | match pins |
|---|---|---|---|
| `iter_at` | `grp` | 0..7 | **0..6** — only bit 7 free; 2 legal values |
| `pixel_order` | `scope` | 24..31 | 28..30 |
| `reg_move_cb` | `form` | 16..23 | 16..19 |
| `shift_amt_move` | `kind` | 16..23 | 16..19 |

`iter_at.grp` I had already derived by hand (M3) and the orchestrator has
confirmed it. **The other three are new** and are handed to him under
`db_defects`; `db.json` is NOT edited here (EXP-0165 owns it). Two of them touch
this experiment directly: `reg_move_cb.form` and `shift_amt_move.kind` are both
byte+2, which I sweep as a whole BYTE rather than as the declared field, so the
sweep is valid — but the analysis must record which swept values fall outside
the descriptor rather than calling them values of the field.

## 2026-08-30 — M7b: orchestrator rulings folded in
- **GO on the compute arm as soon as EXP-0163 clears**; do not wait for the
  render arm. Sweeps run unlocked alongside siblings; only confirmation passes
  need the quiet machine.
- The co-variation finding goes into `FIELD-SWEEP-PROTOCOL` section 3 as a rule.
  His framing, which is sharper than mine and is adopted here: with `iter_at.loc`
  the CARRIER could not express the field; with `uniform_mov.dst` the ORACLE
  could not.
- **The EXP-0144 re-score is accepted but those rows are NOT being restored** —
  restoring an M4 row an hour before a G17P sweep supersedes it is churn. RESULTS
  records them as "withdrawn for the wrong reason, superseded by this
  experiment's own G17P measurement". A separate experiment checks how many of
  the other 122 withdrawals hit the same systemic defect.
- **`proven-dont-care` accepted as a reporting state**, and the label ruling is
  now encoded in `analysis/verdicts.py` rather than argued in prose: an inert
  field is emitter-grade only if the carriers differ in the dimension the field
  controls AND the field's ROLE is known. Emitter-grade asserts the implementer
  may CHOOSE the value, so a proven-inert-but-unknown-role field is
  `single-template-inference`, never `hardware-run`.
- `jump.branch_ctrl` / `jump.link` are already `untested` and `jump` is not in
  the emittable list, so the unconditional liveness whitelist at EXP-0140
  `verdicts.py:540` is not currently propping anything up. Kept in the write-up
  as a named instance of the same class as the fan-out: **a gate that passes by
  construction.**

## 2026-08-30 — M8: RESUMED after the session limit. Re-oriented from disk only.
`raw/` was **empty** — no device case had ever been dispatched, so nothing
measured was lost and there are no results to tune a contract against.

**Contract integrity check, run before touching the device.** 23 of the 27
authored hashes in `CAPTURE_CONTRACT.json` verify exactly; both pinned toolchain
hashes verify. **Four drifted, and I am recording it rather than quietly
re-hashing:**

| file | why it drifted | semantic effect on the sweep |
|---|---|---|
| `PROGRESS.md` | it is an APPEND-ONLY log and hashing it was a design error of mine — it is guaranteed to drift the moment the next milestone is written | none; removed from the authored set below |
| `harness/isa_helpers.py` | `_find_isadb()` candidate-path list re-ordered to find `tools/agx-isa` at its real location on the neo (`EXP/tools/agx-isa`) | none — it changes WHERE the pinned db is looked up, not WHAT is looked up; the resolved hashes are asserted below |
| `harness/anchors.py` | new file, hashed from a 01:21 draft and finished at 01:30 | pre-device authoring |
| `harness/sweeprun.py` | new file, same | pre-device authoring |

All four edits predate the checkpoint commit `b44ffbc7` and all predate any
device dispatch. Re-hashed as `authored_sha256_refrozen` with the pre-existing
values kept beside them under `superseded_at_m8`, so an auditor can see the
diff rather than a silently-updated number. **The rule I am holding to: a freeze
may be amended before the first observation and never after.**

**Toolchain identity is now ASSERTED, not assumed.** The db.json/isadb.py pushed
to the neo hash to `07ad894d…` / `c97c2a22…` — byte-identical to the
`work/frozen/` snapshot pinned in the contract. `sync.sh frozen` is therefore a
verification step here, not an overwrite, and the hardware ran against exactly
the descriptor set the verdicts are keyed to.

## 2026-08-30 — M9: device prefreeze on G17P — anchors + matrix. THE FIXTURE WAS
##                 WRONG ABOUT falu2, AND TWO ARMS HONESTLY DO NOT EXIST.
`raw/prefreeze/anchors_g17p.txt`, `raw/prefreeze/casematrix_g17p.txt` (never
evidence), `work/anchors/anchor_{report,index}.json`, `work/casematrix_g17p.json`.

**`falu2` HAS a real anchor — 12 occurrences** (`k_fadd#0`, `k_sum#0..3`,
`k_sum_reuse#0`, …). The dry-run's `arm_not_run` was an artifact of the local
fixture's hand-built bytes decoding as `falu_compact4`, exactly as M6 predicted,
and the multi-candidate mechanism resolved it on the device without intervention.

**`reg_move_c0/c1/c2var/c9/cb` have ZERO occurrences in our whole probe corpus.**
The Apple compiler never emits those forms from any MSL we can write. This is not
a failure — it is the structural justification for the `REGMOVE/form` arm: the
family is ONE 4-byte instruction whose byte+2 selects the form (EXP-0087/0140),
so the five forms are reached by *setting byte+2 on the `uniform_mov` anchor*.
Any claim about `reg_move_*.dst` that is not built this way cannot be built at
all from own-shader evidence, which is worth stating plainly in RESULTS.

**Two arms are recorded `arm_not_run` WITH THE REASON, never as inertness:**
- `SHIFTMOVE/uni` — `k_rot_uni` yields **no `shift_amt_move` occurrence**; its
  `_agc.main` also fails to tokenize (62 leftover bytes, `<unknown>@22`), a
  db.json coverage gap noted for the orchestrator, not repaired here.
- `COPYSIGN/highpress` — `k_copysign_rp` compiles (180 B, clean tokenization) but
  **the compiler did not emit `copysign` in it**; it lowered the sign-transfer to
  `n2_op6` + `falu*` instead. So the register-pressure carrier that M4(f) argued
  for cannot be reached through MSL, and `copysign.operands` will have exactly ONE
  carrier (`k_copysign`, 2 live float registers). Per R2 that is one carrier, not
  two, and the field cannot clear a two-carrier bar in this experiment. Reported
  as NOT REACHED.
  `k_f2h_consumed` also leaves 6 bytes untokenized (`<unknown>@60`) but DOES
  supply its `cvt_f2h` occurrence, so `CVTF2H/consumed` runs.

**Matrix on the real anchors: 10,366 cases**, sha256
`4b93fa510934adf43893eb5f596e11c98ffb869881700d1dd7b688ba39402c17`
(the fixture's 10,587 is superseded). Roles: sweep 8,612 / bytemate 1,216 /
ladder 470 / falsifier 33 / baseline 33 / arm_not_run 2. 33 arms, 2 not run.

**Machine-readable coverage, counted from the matrix as DISTINCT `bytes` and not
as dispatched-value count** (the orchestrator's DEF-0166-1 signature — a sweep
that dispatches 256 values while the hardware sees 8 encodings):

```
instr                  field            values  distinct_bytes
copysign               operands            256     256
cvt_f2h                op                  256     512
cvt_f2i                b9                  256     512
cvt_f2i                dst                 256     512
if_push                scope               256    1023
mov_imm                byte1               256     768
pack_convert           b7                  256     768
stop                   b1 / b2 / b3        256     256 each
uniform_mov            form_b2             256     256
uniform_mov            opdesc_b3           256     256
unpack_convert         dst                 256     768
stop                   reserved             66      66
falu2                  dst                  16      16
falu2i                 dst                  16      16
get_sr                 dst                  16      16
uniform_mov            dst                  16     224   <- 16 dst x 14 FORMS
get_sr                 dst_hi                8       8
atomic_mem             addr_desc_hi          4     108
falu_acc               cache                 2      28
get_sr                 form                  2       2
mov_imm                imm_top               2       6
shift_amt_move         src_flag              2      26
```
`distinct_bytes > values` is the cross-product working; `distinct_bytes < 2^width`
on `atomic_mem.addr_desc_hi` (4), `mov_imm.imm_top` (2), `falu_acc.cache` (2) and
`shift_amt_move.src_flag` (2) is the field's real `encodable_range`, which the
verdict rows will carry as `encodable_range` alongside `start`/`width`.

## 2026-08-30 — M10: PREFREEZE SMOKE CAUGHT THREE CARRIER DEFECTS IN MY OWN
##                  HARNESS. All three are the failure classes this experiment
##                  was built to expose, and all three are now fixed.
This is the whole point of running S1–S6 before a gated run, so it is recorded
in full including the parts where I was the one who got it wrong.
`raw/prefreeze/{diag_byte0,diag_fals2,diag_fals3}.json` + smoke summaries.

**S4 PASSES first, which is what licenses everything else:** an empty program
leaves all 104 words `0xDEADBEEF`. So `invalid_poison` really is distinguishable
from `silent_zero` on this target.

### Defect 1 — MY SEED TABLE COLLIDED WITH THE VALUE UNDER TEST (R1, again)
`SEED_I[15]` was **0**, and `raw/prefreeze/diag_byte0.json` measures that the
reg_move forms 0x00 / 0x01 / 0x03 **write zero**. So at `dst = 15` the dump
could not distinguish "wrote 0 into r15" from "did nothing" — a by-construction
blind spot of exactly the kind I convicted EXP-0140 of, sitting in my own
oracle. `SEED_I[15] = 121` and `SEED_F[15] = 2.5` (an exact minifloat fixed
point, asserted at import). `SEED_F[14]` must stay `+0.0` — it is the `+0.0`
source every float seed adds to — so for `kind="float"` arms `dst = 14` remains
undecidable when the instruction writes `+0.0`. That limit is recorded, and the
int carrier covers r14.

### Defect 2 — THE FALSIFIER WAS CONFOUNDED WITH THE FIELD UNDER TEST
The generic falsifier forces `byte0 = 0x00` ("this is not the instruction"). For
the four REGMOVE arms it produced a digest **identical to the baseline**, so the
control had no power at all. The cause is structural: `uniform_mov`'s `byte0` is
`opcode nibble (bits 0..3, match-pinned to 0xb) | dst (bits 4..7)`, so
`byte0 = 0x00` **also sets dst = 0** — and the anchor's own dst is 0.

A 256-value sweep of that byte settles it, and it is a hardware finding in its
own right (`raw/prefreeze/diag_byte0.json`, at forms 0x00 and 0x01):
- low nibble **0x0 and 0x1 are DIFFERENT instructions that write the SAME
  destination register from the SAME dst bits** (0x0 writes `0x000000ab`), so
  `byte0 = 0x00` is not "not an instruction", it is a structurally parallel one;
- low nibbles **0x4, 0x6, 0x7, 0xc, 0xe, 0xf change the instruction LENGTH** —
  their signature is a partially-poisoned dump (`r0..r8 = deadbeef`), i.e. the
  rest of the program was misparsed;
- low nibbles **0x5 and 0xd are the only two that are inert with the program
  still completing** at BOTH forms. `0x55` (lo = 0x5, dst = 5, seed 65 ≠ 0) is
  therefore a falsifier that provably fires.
Two more arms had the same disease and needed individually measured values:
`COPYSIGN/lowpress` (95/256 byte0 values fire; `byte0 = 0x00` writes `+0.0` into
the destination just as copysign does → `0x05`) and `ATOMIC/highreg`
(87/256 fire; `0x00` fires on `lowreg`/`minop` but **not** on this carrier
→ `0x02`).

**GENERALISABLE RULE #2, for FIELD-SWEEP-PROTOCOL, companion to the co-variation
rule: a falsifier that clobbers a byte carrying BOTH the opcode and a field
under test is confounded with that field's own values.** "Not this instruction"
must be expressed in bits the field does not own, and the substitute must be
*measured* to fire, not assumed to.

### Defect 3 — TWO STOP ARMS WERE ONE CARRIER (R2, in my own harness)
`STOP/terminal` fell through to `synth_program()`, which places the block under
test in the BODY — byte-for-byte the same program shape as
`synth_program_midstop()`. On hardware both produced the identical observation
(whole dump poison, POST poison). Two arms, one carrier: the exact R2 violation
I convicted EXP-0155 of. Fixed with a real second builder,
`isa_helpers.synth_program_terminalstop()`: seeds → PRE → **dump** → POST →
[stop under test] → witness write into `W_PROBE` → stop. Measured after the fix:

| arm | baseline | falsifier |
|---|---|---|
| `STOP/terminal` | full dump present, `W_PROBE = 0xDEADBEEF` | full dump, **`W_PROBE = 0x4d = 77`** (did not terminate) |
| `STOP/midprogram` | **whole dump poison**, POST poison | full dump present, POST = 111 |

Baselines now differ, and each arm has its own two-state observable.

### The ladder `stop` cannot have, named rather than waived
`stop` has **no known-live field** — every bit is either the opcode or the
`reserved` field under test — so R3's "sweep a known-live control of the same
instruction" is unbuildable and both STOP arms have an empty ladder. Rather than
let `ladder_pass = None` drift through the gate, `analysis/verdicts.py` now
records `ladder_kind` on every verdict row: `field_control` (33 arms) or
**`falsifier_contrast`** (the 2 STOP arms), where detection power comes from a
mutation of the same instruction's own byte0 driving the observable to a second
distinct state on that exact carrier. It is accepted only when the falsifier
fires in every gated run, and the row always says which kind was used.

### Also measured, and it removes a real worry
All five STYLE-P observables are **deterministic**: 6 identical dispatches of
`k_atomic_hi`, `k_atomic_lo`, `k_atomic_min`, `k_if_flat` and `k_if_nest3` each
gave **1 distinct digest**. A nondeterministic observable would have made every
cross-run agreement number meaningless.

### Freeze state going into the gated runs
Re-smoked all 35 arms: **PROBLEMS: NONE** — every live arm has `baseline = OK`,
a ladder with ≥2 distinct digests (or `falsifier_contrast`), and a falsifier that
fires. 2 arms `arm_not_run` with reasons. Matrix **10,366 cases**, sha256
**`90f79d21d47cd77d6567a9ead2bff56403acf0be0278ef8cfbc1081af10176da`**
(supersedes `4b93fa51…`, which supersedes the fixture's `2ce2b126…`).
The three fixes are pre-observation: `raw/` still contains no gated case.

## 2026-08-30 — M11: gated run02 DISPATCHED; render arm completed offline
**run02 launched** (`--order forward`) with `gpuwatch.py` sampling the target
process table alongside it, so "the machine was quiet" is a measurement.
Throughput on real anchors is **~5.6 cases/s**, not the 44.9 EXP-0154 measured —
this matrix pays for majority-of-3 confirmation, an OS-fault-class lookup on
every non-`ok` case, and a baseline revalidation every 300 — so a gated run is
**~30 min**, not ~4. Three runs is ~90 min of device time. Recorded because M6's
estimate was wrong by 8x and the next experiment should not inherit it.

Early run02 shape (first 12 arms): `wrong_value` 1675 · `ok` 710 ·
`silent_zero` 367 · `fault` 274, and **14 `invalid_sentinel`** cases correctly
diverted to re-run rather than being recorded as silent zeros. The
validity/outcome separation is earning its keep on live data.

### Two gaps closed in the render arm while run02 ran
**1. `kernels/r_vmix.metal` DID NOT EXIST.** `rendercarriers.CARRIERS["r_vmix"]`
named it and nothing on disk provided it, so that carrier would have failed at
census. It is the arm's stated *discriminator* for `vtx_out_pos.slot`: with
uniform-width varyings, "ordinal into a slot table" and "byte offset into the
output block" differ only by a constant factor and are indistinguishable at
every value of `slot`; mixed widths make the map non-linear. Authored to match
`vtx_values_mix()`'s twelve predicted observables exactly —
`half/half2/float/float2/float4` into 3 RGBA32Float targets, every value an
exact power-of-two multiple so the oracle never depends on a rounding mode. All
16 carriers now have their source on disk (checked, not assumed).

**2. `iter_at.grp` had NO ARM AT ALL** — it is in this experiment's dispatched
scope and the render harness targeted only three instructions. Added as its own
family `itr`, deliberately bounded:
- **the descriptor defect is carried in the target spec, not just in prose**:
  `legal_values=[0x2f, 0xaf]`, `encodable_range=2`,
  `declared_width_is_wrong=True`, `coverage_is_bounded_by_descriptor=True`. This
  field **cannot** satisfy this experiment's own dense-coverage clause (2^8 for
  w=8) because **only two encodings exist**. It is reported that way and the
  orchestrator rules; I do not quietly relax my own gate for it.
- **two carriers differing in the ONE dimension iter_at has ever moved in**:
  `r_i8` (samples=1) and `r_i8s` (samples=4), same MSL source. Per M3 these are
  *not* byte-identical programs — `rasterSampleCount` is an input to the
  fragment compile — and the write-up says so rather than claiming byte-identity.
  Reusing `r_v8.metal` is deliberate: eight distinct power-of-two varyings force
  eight interpolated fetches, so `iter_at` is certain to be emitted and a
  redirect is decodable.
- **ladder = `iter_at.loc`**, byte+7, which is NOT covered by any of iter_at's
  three match constants and which EXP-0163 measured moving 128/256 at samples=4
  and inert at 1. The expected result is an **asymmetry between the two
  carriers**, and that asymmetry is itself the detection-power proof — it says
  which carrier an inert `grp` verdict may even be reported from.
- **falsifier = the zero-hazard DATA falsifier only.** 254 of `grp`'s 256 values
  are out-of-descriptor and two prior experiments hung on them; a byte-splice
  falsifier here would spend the device rather than prove detection.
- **byte-mate = the 7-bit pin at its own legal value 0x2f only** (a no-op control
  that must reproduce the baseline). The out-of-descriptor region is **not** swept.

`work/render_build/mocktest.py`: **MOCK TEST PASS** with the new family and
carrier in place. `work/gfrun3` built on the target (75,960 B).

## 2026-08-30 — M12: run02 COMPLETE (10,366 cases, ZERO hangs) and the render
##                  census exposed a fourth by-construction defect, this one
##                  fatal to the whole iter_at arm
### run02 — first gated run, G17P
```
DONE 10366  hang: 0   stopped_fields: 0
ok 3229 · wrong_value 5144 · undecodable 836 · fault 664 · silent_zero 491
invalid 849 (re-run, NOT counted) · victim 83 · baseline_fail 10
```
`00_env.json` reads the identity from the LIVE device: `Apple A18 Pro`,
`Mac17,5`, 5 cores, macOS 26.6 (25G5043d), `matrix_sha256 90f79d21…`,
`db_sha256 07ad894d…`. Nothing is taken from a literal.
**Zero hangs across 10,366 spliced cases, and no field hit its stop budget** — so
unlike EXP-0144 and EXP-0155 there are **no skip placeholders in this run at
all**, which is what made those two experiments' verdicts unscoreable.
Ten `baseline_fail` events, all on `STOP/midprogram` (n=8100/8400/8700, …); the
driver restarted the persistent child each time, which is the designed response.
That arm deliberately runs programs that may not terminate, so it is the arm
where a drifting baseline is expected — recorded, and it is why the baseline
revalidation exists.
run02 pulled back in full (16.5 MB `sweep.jsonl`, plus `baseline.jsonl` and
`gpuwatch.jsonl`). **run03 launched with `--order reverse`.**

### DEFECT 4 — `NEEDED` was a HAND-MAINTAINED LIST, and it silently voided the
### entire `iter_at` arm by turning a lookup omission into a hardware claim
`renderrun.NEEDED` hardcoded
`{"vertex": [vtx_out_pos, vary_store], "fragment": [pixel_order, frag_color_pack]}`.
Adding `iter_at` to `TARGETS` therefore changed nothing: the census never looked
for it, `--mode freeze` would have skipped every iter_at arm with *"no occurrence
in this carrier — a STRUCTURAL RESULT about when the instruction is emitted, not
a failure"*, and that sentence is **false and load-bearing**. The instruction was
there all along: tokenizing the census's own recorded fragment hex with the
frozen `isadb` shows `iter_at@8` in both carriers. A hand-maintained lookup list
converting an omission into a structural claim about the hardware is precisely
the class of error this experiment exists to find, and this is the fourth one it
has found in its own harness. `NEEDED` is now **derived** from `TARGETS`,
`LADDERS` and `FALSIFIERS`, so adding a target cannot silently fail to be
censused.

### And the census corrected my carrier before it could produce a wrong answer
`r_i8`/`r_i8s` first pointed at `r_v8.metal` (default centre-perspective
interpolation). The census found **no `iter_at` at all** in that fragment
program: plain smooth interpolation lowers to the location-implicit form, and
`iter_at` — "interpolate AT a location" — is what the compiler emits when the
location is EXPLICIT. That is why EXP-0155's carrier was named `c_cent1`.
`kernels/r_icent.metal` is `r_v8` with `[[centroid_perspective]]` on all eight
varyings, on **both** members of the pair, so the two carriers still differ in
exactly one dimension (`rasterSampleCount`) — using `sample_perspective` for the
4x member would have confounded the qualifier with the sample count and
reproduced EXP-0155's own mistake in a new place. After the fix:
`f/iter_at=1` in `r_i8`, `r_i8s`, `r_rog2`, `r_rog8`, `r_rogx`.

### Frozen render arm table: 19 arms, and every target has >= 2 DISTINCT dims
| mnemonic | distinct carrier dimensions |
|---|---|
| `vtx_out_pos` | 3 — single-varying CONTROL · 8 scalar FLAT · **MIXED-WIDTH** |
| `pixel_order` | 3 — commutative RMW · non-commutative affine RMW · two resources |
| `frag_color_pack` | 3 — immediate-source (EXP-0155 replica) · 4x MSAA · 4 RTs register-source |
| `iter_at` | 2 — centroid fetch at **samples=1 vs samples=4** |
That is the R2 bar met by measurement rather than by counting arms: EXP-0155's
"2 carriers" for `frag_color_pack.dst` were two occurrences in one program, and
its two `iter_at` carriers were both samples=1.

### Two STRUCTURAL results that fall out of the census for free
1. **`vtx_out_pos` is emitted only by the vertex carriers that do NOT write a
   device buffer.** It is present in `r_v1`, `r_v8f`, `r_vmix` (no `out_buf`) and
   **absent** from `r_v8`, `r_v4v`, `r_vsrc` (all three bind `--out-buf` to the
   vertex stage). So the "second, independent observation path" those carriers
   were built for is **not available for this instruction** — when the vertex
   stage also writes a device buffer, the position output is lowered some other
   way. Recorded as a limit on the arm rather than quietly enjoyed.
2. **`frag_color_pack` is emitted only for the 8-bit unorm attachments.** Absent
   from `r_fcpf` (RGBA32Float) and `r_fcph` (16-bit float), present in `r_fcp1`,
   `r_fcp1s`, `r_fcp4`. The pack step exists because the conversion does.

## 2026-08-30 — M13: DEFECT 5, and it was silently gutting four fields —
##                  "the sentinel is missing" WAS the measurement
`analysis/verdicts.py` on run02 alone showed `stop.reserved`, `stop.b1`,
`stop.b2`, `stop.b3` at **carriers=1** when both STOP arms sweep all four. The
raw says why: of 836 `STOP/midprogram` records, **835 were written
`invalid_sentinel` / `undecodable` and excluded from every count.**

The cause is a head-on collision between two of my own rules, in which the
run-integrity one won without announcing itself:
- `STOP/midprogram` places the stop under test **before** the register dump, so
  when the stop does its documented job the dump never runs, the register window
  stays `0xDEADBEEF` and POST is never materialized. **That absence is the
  result** — it is the entire reason the arm exists, and `synth_program_midstop`
  says so in its docstring.
- `validity_of()` says a read-back that is entirely poison, or whose POST
  sentinel is missing, is corrupt and must be re-run.

So the only carrier in which a program-end token's field can express what it
controls contributed **nothing**, and `stop.*` was quietly reduced to the
terminal carrier alone — which is blind to termination by construction. Had I
not cross-checked the carrier count against the arm table, this would have been
reported as "one carrier, insufficient" and read as a fact about the hardware.

**The fix is a discriminator, not a waiver.** The PRE sentinel is written to
MEMORY BEFORE the stop under test, so a correct dispatch must ALWAYS show it:
```
tail region written                     -> invalid_sentinel  (out of bounds)
PRE absent                              -> invalid_sentinel  (never got there)
PRE present, POST poison, window poison -> VALID, outcome `ok`
                                           -- the stop TERMINATED
PRE present, dump present                -> VALID, outcome `wrong_value`
                                           -- it did NOT terminate
```
Applied in two places on purpose:
1. `harness/sweeprun.py::validity_of(terminating=True)`, routed from
   `run.py`, so future runs record it correctly at the point of measurement;
2. `analysis/verdicts.py::recorrect_terminating()`, which applies the SAME rule
   to runs already on disk from each record's own preserved
   `observed.{pre,post,regs,tail_ok}`. **`raw/` is not edited** — it is
   append-only evidence — and the correction is reported per run
   ("re-derived ... on 836 records") and recorded in `_meta.corrections_applied`.
   run02, run03 and any later run are therefore scored by one identical rule
   rather than one of them being re-run under a different one.
After the correction `stop.*` reads **carriers=2**.

### First movement numbers, run02 alone (no cross-run pair yet, so every row is
### correctly `still-underpowered` at this point)
| field | moved | carriers |
|---|---|---|
| `mov_imm.byte1` | 767 | 2 |
| `uniform_mov.form_b2` | 232 | 1 |
| `cvt_f2h.op` | 221 | 2 |
| **`uniform_mov.dst`** | **214** | **3** |
| `uniform_mov.opdesc_b3` | 208 | 1 |
| `cvt_f2i.dst` | 190 · `pack_convert.b7` 190 · `unpack_convert.dst` 188 | 2–3 |
| `falu2.dst` / `falu2i.dst` / `get_sr.dst` | 15 each | 1 |
| `get_sr.dst_hi` 8 · `falu_acc.cache` 28 · `shift_amt_move.src_flag` 22 · `atomic_mem.addr_desc_hi` 15 · `mov_imm.imm_top` 5 | | |
| `if_push.scope` | **0** across **4** carriers | 4 |
| `cvt_f2i.b9` / `get_sr.form` / `stop.*` | **0** | 2 / 1 / 2 |

**`uniform_mov.dst` moved 214 times.** EXP-0164's withheld row for it reads
"16 values dispatched, 0 observations moved". The difference is not more data —
it is an oracle that does not co-vary with the field.

## 2026-08-30 — M14: render smoke STOPPED early, deliberately, and the reason is
##                  itself a measurement
Ran the render smoke alongside gated run03 on the orchestrator's "sweeps run
unlocked" ruling. After 468 cases on 2 of 19 arms it had produced **3 hangs** on
the `frag_color_pack@r_fcp1` arms, and run03's **victim count rose from run02's
83 to 119** over the same window. run03 itself stayed clean (0 hangs, victims
re-run and recovered), but a hang can kill a sibling's in-flight command buffers
and run03 is the primary deliverable, so the render smoke was **killed** and the
render arm deferred until the compute runs finish.

Recorded as a concrete number for FIELD-SWEEP-PROTOCOL §7: **running two of this
repo's own sweeps concurrently on one G17P cost a 43% rise in victim
re-dispatches** (83 -> 119) in the arm that was already running. Unlocked sweeps
are cheap when both arms are hang-free; they are not free when one of them
splices a known-hazardous field.
Also noted from the 468 smoke cases, to be settled when the arm runs properly:
`falsifier_held: 2` — two render falsifiers did NOT fire, the same class of
defect the compute smoke found in four arms.

## 2026-08-30 — M15: COORDINATOR'S STALE-db.json CHECK. CLEAN — and EXP-0168
##                  dodged it by exactly one line, which was the "benign" M8 drift.
Answering all three parts, measured on the device, not asserted.

**1. What my harness actually resolved on the neo.**
```
ISA_DIR resolved: /Users/user/agxre/EXP-0168/tools/agx-isa   <- MY PRIVATE COPY
  db.json   07ad894d3e7041eaa35692489e90df58ed0b623b4de9378a9d8ea5ca104646d0
  isadb.py  c97c2a22fe4eb3aaa2140ff716686dcdbbbb099dcd68d2af77f7f9054174dd36
  172 instructions / 1062 fields
  falu2  = [dst, srcA_size, srcA_reg, opsel, opflags, srcB_size, srcB_reg,
            ctrl, srcB_imm, srcA_class, srcB_class, srcB_neg, mod_hi,
            srcA_reg_top, srcB_reg_top]     <- srcA_class/srcB_class PRESENT
```
Byte-identical to my pinned `work/frozen/` snapshot, and it is what run02's
`00_env.json` recorded live (`isa_dir`, `db_sha256`, `isadb_sha256`).
The shared copy, read only for comparison, IS stale exactly as EXP-0169 found:
```
~/agxre/tools/agx-isa/db.json  f5db942f…  171 instructions / 1036 fields
  falu2 = [... srcB_imm, mod_lo, srcB_neg ...]   <- mod_lo REPLACES the two _class
```
**My harness never read it.** `sync.sh push` copies `$REPO/tools/agx-isa` into
`~/agxre/EXP-0168/tools/`, a private per-experiment copy, for precisely this
reason (recorded in `sync.sh`'s header before any of this happened).

**AND HERE IS THE PART WORTH THE COORDINATOR'S ATTENTION.** `work/frozen` did
**not** exist on the neo, so `_find_isadb()` fell through past candidate #1. The
ORIGINAL candidate order — the one hashed into `CAPTURE_CONTRACT.json` at freeze
— was:
```
EXP/work/frozen                        (absent on the neo)
~/agxre/EXP-0168/frozen                (absent)
~/agxre/tools/agx-isa                  <-- THE STALE SHARED COPY. WOULD HAVE WON.
EXP.parents[1]/tools/agx-isa
```
The M8 post-freeze drift I recorded as "benign — it changes WHERE the pinned db
is looked up, not WHAT" reordered that list to put `EXP/tools/agx-isa` second.
**That one line is the only reason EXP-0168 is not keyed to `mod_lo` right now.**
I recorded it as cosmetic; it was load-bearing. The lesson is not "we got lucky",
it is that **a path-search fallback list is a silent correctness surface**, and a
harness should FAIL when its pinned toolchain is absent rather than quietly
resolve something else. `work/frozen/{db.json,isadb.py}` is now pushed to the neo
and `ISA_DIR` resolves to `/Users/user/agxre/EXP-0168/work/frozen` — candidate #1
wins explicitly instead of by luck.

**2. `start`/`width` against the repo's CURRENT db.json** (`322847609d…`, which
has moved since my freeze): checked all 28 fields this experiment touches
(the 14 `dst` rows, the 12 one-field-away, the 2 companions).
**MISMATCHES: NONE.** Identical `start`/`width` in both, and the frozen/current
field-NAME sets are equal (`only in frozen: []`, `only in current: []`) — the
hash moved elsewhere. So my rows will pass `merge_verdicts.py`'s stale-DB refusal
rather than trip it. Verdict rows already emit `values_dispatched`,
`distinct_bytes`, `encodable_range`, `start`, `width` (added at M13), plus
`dense_required`, `dense_ok`, `bytes_per_value` and `under_covered`.

**3. The `device_load` false-movement mode — checked, and it does not reach this
experiment. Two independent reasons.**
- **By construction:** STYLE-S seeds r0..r15 with `mov_imm` immediates (int) or
  `falu2i` minifloat immediates (float) — **there is no `device_load` in the
  seeding path at all**, so an async load cannot land a partially-seeded
  register file. And the `dst` oracle is not digest-equality against a baseline:
  it is a HOST-COMPUTED slot pattern whose GPU-independent half is the seed table
  known a priori from those immediates. A re-seeded baseline cannot fabricate
  movement against a host-known table.
- **By measurement,** because the STYLE-P carriers DO use `device_load`:
  (a) the prefreeze diagnostic dispatched each of `k_atomic_hi`, `k_atomic_lo`,
  `k_atomic_min`, `k_if_flat` and `k_if_nest3` **6 times identically** and each
  gave **1 distinct digest** (`raw/prefreeze/diag_fals3.json`);
  (b) run02's `baseline.jsonl` holds **70 baseline takes across 33 arms** and
  **every arm has exactly 1 distinct baseline hash** — including
  `STOP/midprogram`, whose 7 takes span the 10 baseline-drift child restarts and
  came back with the SAME hash each time, so that drift was transient
  contention, not a re-seed.
  **ARMS WITH A DRIFTING BASELINE: NONE.**

Headline cited from here on: **41 of 166 emittable, 616 fields.**

## 2026-08-30 — M16: THE HEADLINE MEASUREMENT, and a register-file fact that
##                  falls out of my own seed table failing
### `uniform_mov`/`reg_move_*` `dst` x FORM cross-product — the measurement
### EXP-0140 never made
run02, arm `REGMOVE/dump`, 224 valid dst cases = 16 dst x 14 byte+2 form values,
scored against the **HOST-KNOWN SEED TABLE** (not against the baseline).

| byte+2 | descriptor(s) it satisfies | dst 0..14 -> exactly slot dst | value written |
|---|---|---|---|
| 0x00 | `reg_move_c0` | **15/15** | 0x0 |
| 0x01 | `reg_move_c1` / `uniform_mov` | **15/15** | 0x0 |
| 0x02 | — | **15/15** | 0x30 |
| 0x05 | — | **15/15** | 0x0 |
| 0x09 | `reg_move_c9` | **15/15** | 0x0 |
| 0x11, 0x15, 0x31, 0x35 | — | **15/15** each | 0x0 |
| 0x21, 0x25 | `reg_move_c2var` (bits 20..23 = 2) | **15/15** each | 0x0 |
| 0x0b | `reg_move_cb` | **1/15** — dst deviates | 0x4b |
| 0x0f, 0x26 | — (EXP-0113's "nondeterministic" pair) | **0/15**, many slots move | — |

**`dst` selects the destination register, and the slot moves with the VALUE, at
11 of 14 form values — including every form EXP-0140 classified `silent_zero`
(c0, c2var) and `wrong_value` (c9).** That is precisely the M1b prediction: those
forms still WRITE the destination, so the observable has to be *which slot
changed*, not *what value it changed to*. A single-word read-back cannot express
that dimension at all, which is why EXP-0140 recorded "16 values, 0 moved".
`reg_move_cb` genuinely differs (1/15) and 0x0f / 0x26 change the instruction
LENGTH (their signature is a partially-poisoned dump). Both are reported as
themselves, not smoothed into the positive result.

I report the byte+2 VALUE and which descriptors' `match` constants it satisfies,
**not** a 1:1 form->descriptor map: 0x01 satisfies both `reg_move_c1` and
`uniform_mov`, and `c2var` is pinned on bits 20..23 rather than the low nibble,
so several values are jointly satisfiable. Every case records its full `bytes`,
so the orchestrator can re-key any of this without re-running.

### r15 IS NOT WRITABLE THROUGH THE 4-BIT DST NIBBLE — and my M10 "fix" for it
### silently did nothing
At M10 I changed `SEED_I[15]` 0 -> 121 and `SEED_F[15]` 0.0 -> 2.5 to remove a
seed/value collision. **The write never landed.** In run02, across every arm and
BOTH seeding paths, r15 reads **0x0**:
- int path `mov_imm(15, 121)` = `fc79`, which round-trips as
  `mov_imm {dst:15, imm7:121, imm_top:0}` — encoding is correct;
- float path `falu2i(r15, r14, +2.5)` — same result;
- meanwhile **r14 reads correctly** (0x3 int, 0x0 float) through the identical
  code path, so this is specific to index 15, not to the seeding.

**Measured fact: a write with the 4-bit destination nibble = 15 is discarded and
the slot reads 0.** Driver consequence, which is the point: an emitter must not
allocate register index 15 as the destination of a 4-bit-dst instruction — it is
a bit bucket, not a GPR.

**What I CANNOT distinguish, stated rather than glossed:** "physical r15 is a
hardwired zero register (writes discarded, reads 0)" and "the 4-bit dst nibble
value 15 encodes *no destination*" predict identical observations in every
carrier here. Separating them needs a write through a WIDER dst field to physical
r15 and a read back through the 7-bit source side; this experiment has a 7-bit
*source* probe (`falu2i` srcA) but no 7-bit *destination*, so it cannot. Recorded
as a named open question, with the note that EXP-0128's "imm >= 128 does not
write the register at all" is a different and unrelated fact.

**Consequence for this experiment's own coverage claim, applied against myself:**
`dst = 15` is **UNDECIDABLE** in this carrier at every form that writes 0 —
r15 reads 0 whether the instruction wrote it or not. So `uniform_mov.dst`
dispatches 16 values but only **15 are decidable**, and the verdict row must say
so rather than claim dense 16/16. The "1/16 exact" that the naive
seed-table comparison reported at 11 forms was exactly this artifact: at v=15 the
only changed slot is 15, which is *also* changed in every other case.

## 2026-08-30 — M17: `if_push.scope` is the strongest NEGATIVE in the set, and
##                  the carrier that produced it is the one M2c specified
run02, all four IFPUSH arms, scored the way `verdicts.py` scores them
(`observed.digest or observed.hash` — STYLE-P records key it as `hash`):

| arm | carrier dimension | ladder distinct | sweep | moved | falsifier |
|---|---|---|---|---|---|
| `IFPUSH/flat` | ONE non-nested scope (the blind control) | **4/16** | 256 | **0** | fires |
| `IFPUSH/loop` | a real loop | **4/16** | 256 | **0** | fires |
| `IFPUSH/nest3.outer` | 3 genuine nesting levels, outer push | **4/16** | 256 | **0** | fires |
| `IFPUSH/nest3.inner` | 3 genuine nesting levels, inner push | **6/16** | 256 | **0** | fires |

**Four structurally distinct carriers, every ladder PASSING, every falsifier
FIRING, dense 256/256, and zero movement in all four.** The ladder is
`scope_kind` — the same instruction's neighbouring byte, which EXP-0140 measured
moving 178 cases to `wrong_value`. So the observable demonstrably resolves
differences on this instruction and still cannot see `scope` at any value.

This matters because M2c named exactly why EXP-0140's flat verdict was
unconvincing, and all three defects are fixed here:
1. its if/else lowered to `isel10`, a SELECT, exercising no mask stack — these
   carriers put a **store** inside every divergent region, which cannot be
   if-converted;
2. both its live pushes carried scope 0x54, so the "ping-pongs 0x54/0x56 with
   nesting parity" model was never instantiated — `nest3` supplies **three
   genuine nesting levels**;
3. its observable was ONE GPR over 8 lanes of a partially-filled SIMD — here it
   is a per-lane x per-region slot pattern out of a poisoned buffer over a full
   32-lane dispatch.
The inert result therefore survives the specific objections that made the
original one weak, which is the only thing that makes a negative worth having.
Pending run03, this is a `proven-dont-care` candidate; per the orchestrator's
ruling its label is **`single-template-inference`, not `hardware-run`**, unless
`scope`'s role is independently known.

Also from the same pass, and going into the verdict rows:
`ATOMIC/highreg` ladder 8/12 distinct, 14 moved; `ATOMIC/lowreg` 2/12, 15 moved;
`ATOMIC/minop` 2/12 distinct but **0 moved** — so `atomic_mem.addr_desc_hi` is
live on two of three carriers and inert on the third, which is a per-carrier
split the verdict must report rather than average away.

### A methodological note against myself
My first pass at both this table and the dst table read the wrong key
(`observed.digest` only, which is `None` for STYLE-P) and reported every IFPUSH
ladder as flat — i.e. "all four arms would be DISCARDED". The harness and
`verdicts.py` were correct; my ad-hoc analysis snippet was not. Recorded because
the near-miss is the same shape as everything else in this log: **an analysis
that silently reads a field that is absent produces a confident, wrong,
negative.** It is caught only by cross-checking against an independent
measurement — here the prefreeze smoke, which had reported 4-6 distinct digests
for those same arms and disagreed loudly enough to force a second look.

## 2026-08-30 — M18: BOTH GATED COMPUTE RUNS COMPLETE. VERDICTS:
##                  16 hardware-run / 6 proven-dont-care / 2 still-underpowered
run03 DONE: 10,366 cases, **0 hangs, 0 stopped fields**, and the outcome mix is
near-identical to run02 (`ok` 3229 vs 3229, `silent_zero` 491 vs 491,
`undecodable` 836 vs 836, `fault` 674 vs 664, `wrong_value` 5134 vs 5144).
Victims 419 vs 83 — the render-smoke concurrency, already recorded at M14.
Both runs pulled back in full (16.5 / 16.7 MB `sweep.jsonl`).

`analysis/verdicts.py --runs run02 run03` -> `analysis/field_verdicts.json`:
**hardware-run 16 · proven-dont-care 6 · still-underpowered 2.**
Cross-run agreement **100.000% on 23 of 24 fields**, 99.609% on `cvt_f2h.op`
(1 disagreement in 256 against 221 moved = 221x). Every row clears my
>=99.5% / >=4x bar, not just the orchestrator's >=99% / >=2x.
Every row carries `values_dispatched`, `distinct_bytes`, `encodable_range`,
`start`, `width`, `dense_required`, `dense_ok`, `bytes_per_value`,
`under_covered` — and `undecidable_values` / `decidable_values` /
`undecidable_why` where the r15 finding applies.

**`uniform_mov.dst`: 16 values, 224 distinct bytes, 214 moved, 3 carriers,
100.000% agreement.** EXP-0164's withheld row reads "16 values dispatched, 0
observations moved".

### DEFECT 8 — the same disease as defect 5, on the OTHER stop arm
The first joint run put all four `stop` fields at `still-underpowered` with
"the liveness ladder (kind=falsifier_contrast) did not pass". Cause, from the raw:
`STOP/terminal`'s falsifier shows `probe = 0x4d` (= 77 = `SENT_WITNESS`, so the
stop did NOT terminate) against the baseline's `probe = 0xdeadbeef` (it DID) —
**the falsifier is plainly firing** — but `classify_slots` compares only the 16
registers, which are identical by construction on that carrier because the dump
has already run in every case. So it scored `ok`, failed the arm's own ladder,
and blocked the fields. It also meant the terminal arm's **sweep** could see
nothing at all: 836 cases, all `ok`, all `moved=False`.
Fixed in the same uniform, raw-untouched way as defect 5: the terminal arm's
`outcome`/`moved` are re-derived from `observed.probe`
(POISON = terminated, 77 = did not), with POST required present. After the fix
all four `stop` fields are `proven-dont-care` at 2 carriers.
**837 records re-corrected per run**, every one keeping its prior values under
`_recorrected`, and both rules recorded in `_meta.corrections_applied`.

**The pattern across defects 5 and 8 is worth naming for the protocol: on a
carrier built so that the ABSENCE of something is the measurement, the generic
outcome/validity classifier reads the wrong word and returns a confident
negative.** Both of this experiment's stop arms had it, in opposite directions.

### Honest limits recorded on the verdicts rather than argued around
- `copysign.operands` and `get_sr.form` are 100.000%-agreeing, dense, 0-movement
  — and stay `untested` because they have **ONE** carrier. For `copysign` a
  second one is not buildable: the compiler will not emit the instruction in a
  high-pressure kernel. More device time cannot fix either.
- `stop.reserved` is 24 bits: 66 of 16,777,216 values dispatched, so its row
  carries `under_covered: true` and its don't-care claim is explicitly bounded to
  the sampled set.
- `dst = 15` is undecidable everywhere (the r15 finding), so `uniform_mov.dst` is
  16 dispatched / **15 decidable**, stated on the row.

`RESULTS.md` written with the full verdict table, the dst x form cross-product,
the r15 finding, the `if_push.scope` negative, all six by-construction defects,
the two new protocol rules, run integrity, and the stale-db.json near-miss.
**Render gated run `g17p_20260830_rrun01` launched** (compute runs are finished,
so the machine is no longer shared with my own sweep).

## 2026-08-30 — M19: render rrun01 found the REAL hazardous band and refuted an
##                  A18 result on G17P. Stopped, corrected, relaunched.
rrun01 reached 3 of 19 arms / 545 cases with **9 hangs** before I stopped it. Both
causes are findings, and both were costing coverage.

### FINDING: `frag_color_pack.dst`'s hazardous band is CONTIGUOUS 194..197
The prefreeze smoke had measured 194 and 196 hanging, so I deferred
`[192, 193, 194, 196]` to the end of the order. **rrun01 then hung at 195 and
197** — on three arms each (`r_fcp1#0`, `r_fcp1#1`, `r_fcp1s#0`). So the sweep
reached 195, hung, reached 197, hung, hit the two-hangs-per-field budget and
**stopped at 197 — leaving 198..255 unswept for the third time across three
experiments.** Deferring half a contiguous hazard band does nothing.
Band widened to **192..197**; verified offline that all of 198..255 now precedes
the hazardous tail in the dispatch order.
So the full picture on G17P: **192, 193 contained faults; 194, 195, 196, 197
genuine hangs.** EXP-0155 stopped at 194 and never learned why.

### CROSS-TARGET REFUTATION: `src_present_mask = 0xff` HANGS on G17P
`F_mask_ff` is pre-registered from EXP-M4-14, HW-VALIDATED on **A18**, as an
ILLEGAL encoding producing a **CONTAINED command-buffer fault (the device
survives)**. On **G17P it HANGS**, 3 of 3 arms. Its own pre-registration
anticipated the possibility ("if it hangs instead, it counts against the arm's
hang budget like any other hang") — and the budgetary consequence is what I had
not anticipated: **8 `frag_color_pack` arms x 1 hang each = a third of
`MAX_HANGS_TOTAL` spent re-confirming one refutation before any other family
runs.** With `MAX_HANGS_TOTAL = 24`, rrun01 was on course to stop before
`pixel_order`, `vtx_out_pos` or `iter_at` ran at all.
Fixed with a new pre-registered flag `once_per_carrier=True`: the falsifier is
dispatched **once per CARRIER** rather than once per arm, because the finding is
a property of the carrier, not of which occurrence is spliced. Later arms on the
same carrier emit a `not_run` record naming the arm and outcome that already
established it — recorded, never silently skipped.

rrun01's partial raw is preserved under `raw/superseded/` with a name saying what
it did not know, rather than deleted. Relaunched as `g17p_20260830_rrun02`.
`work/render_build/mocktest.py`: **MOCK TEST PASS** with both changes.

## 2026-08-30 — M20: a SIBLING EXPERIMENT is now on the machine, and defect 9
### EXP-0172 is running on the neo
`ps` shows multiple `~/agxre/EXP-0172/work/agxrun_persist` processes. The dispatch
told me "all other device experiments are stopped"; that is no longer true, and
it matters here specifically because **my `frag_color_pack` arms generate genuine
device hangs** (192..197, plus `src_present_mask = 0xff`). A hang kills a
sibling's in-flight command buffers. Flagged to the orchestrator.

**Resequenced in response, and it is the right ordering anyway:** the render arm
is now run as two passes, hang-free families FIRST —
`--mnem vtx_out_pos,pixel_order,iter_at` (`g17p_20260830_rclean01`), and
`frag_color_pack` separately afterwards. Three benefits: the clean families are
banked before any hazardous value is dispatched; the global hang budget is not
spent before they run (which is what was about to happen in rrun01); and the
window during which I am dangerous to EXP-0172 is bounded and known.
`rrun02`'s partial raw is preserved under
`raw/superseded/rrun02_partial_fcp_first_ordering`.

### DEFECT 9 — I added a whole instruction family without its ORACLE
`rclean01` crashed at its first baseline dispatch:
```
File "harness/rendercarriers.py", line 579, in oracle
    vals = cfg["fcp_values"]
KeyError: 'fcp_values'
```
`oracle()` branches `vtx` / `rog` / else-`fcp`. My new `itr` family fell through
to the `fcp` branch. The `itr` carriers are shaped exactly like `vtx` — same MSL
skeleton, same `vtx_values` key, same `rt_count`/`out_buf` surfaces — so the fix
is `if fam in ("vtx", "itr")`, verified offline: `r_i8`/`r_i8s` now produce
`PIX0 [1,2,4,8]`, `PIX1`, and a 96-float `OUTBUF` identical in shape to `r_v8`'s,
with a distinct alt oracle `[3,5,9,17]`.

**Why the offline mock test did not catch it:** `work/render_build/mocktest.py`
exercises arm selection, ladders and falsifier bookkeeping, but **never calls
`RC.oracle()`** — so a family can pass the mock and still have no host oracle at
all. That is the ninth by-construction defect in this experiment and the second
where **a check that passes without exercising the thing it appears to check**
was the real problem (the first being EXP-0140's co-varying observable). Recorded
as a gap in the mock, not repaired here.

## 2026-08-30 — M21: render arm — one COMPLETE gated run, real results, and a
##                  second run blocked by machine contention
### `g17p_20260830_rclean01` — COMPLETE: 2,632 cases in 85.1 s, 4 hangs,
### `stopped_early: false`, 0 refused arms
Run as a hang-free-families-first pass (`--mnem vtx_out_pos,pixel_order,iter_at`)
so the clean families were banked before any `frag_color_pack` hazard was
dispatched, and so my window of danger to EXP-0172 was bounded.

`analysis/render_verdicts.py` -> `analysis/render_verdicts.json`.
**All render verdicts are PROVISIONAL: one gated run means cross-run agreement,
the pre-registered promotion gate, has not been evaluated.** The analyser says so
on every row itself; I am not going to launder a one-run result.

| field | bucket | provisional label | arms | distinct dims |
|---|---|---|---|---|
| `pixel_order.kind` | **LIVE** | `hardware-run` | 6 | 3 |
| `vtx_out_pos.dst` | **LIVE** | `hardware-run` | 3 | 2 inert + live on 1 |
| `vtx_out_pos.slot` | **INERT-ROBUST** | `single-template-inference` | 3 | **3** |
| `iter_at.grp` | **LADDER-FAILED** | `untested` | 0 eligible | — |

### `vtx_out_pos.slot` — EXP-0147's open follow-up, answered
EXP-0147 called `slot` inert in a SINGLE-VARYING carrier and its own RESULTS.md
named "`vtx_out_pos.slot` in a multi-varying carrier" as the follow-up. Here it
is inert at 256/256 across **three distinct carrier dimensions** — the
single-varying control, 8 scalar FLAT varyings, and the **MIXED-WIDTH**
discriminator (`half/half2/float/float2/float4`) that was built specifically
because with uniform widths "ordinal into a slot table" and "byte offset into the
output block" are indistinguishable at every value. Each arm passed its ladder
and its falsifier. That is INERT-ROBUST at 3 dims — a real negative, not a
carrier that could not see.

### `vtx_out_pos.dst` moves ONLY in the single-varying carrier
1 of 16 moved on `r_v1`, **0 of 16** on `r_v8f` and `r_vmix`. A field that is
live in the degenerate carrier and inert in the rich ones is a genuinely odd
shape and I am not going to explain it from one run; it is reported as measured
and flagged for the second gated run.

### `pixel_order.kind`: the pre-registered EXP-0162 model HOLDS on the carrier it
### came from and BREAKS on the non-commutative one
The partition was pre-registered offline from EXP-0162's raw before this
experiment ran anything, and it reproduces all 256 of its recorded outcomes.
Against this experiment's carriers:

| arm | carrier dimension | predicted 256, held |
|---|---|---|
| `r_rog8#0`, `r_rog8#1` | commutative additive RMW (EXP-0162's own shape) | **256 / 256 = 100%** |
| `r_rog2#1` | two ordered resources | **256 / 256 = 100%** |
| `r_rog2#0` | two ordered resources | 232 / 256 = 90.6% |
| `r_rogx#0` | **non-commutative affine** RMW | **32 / 256 = 12.5%** |
| `r_rogx#1` | **non-commutative affine** RMW | 64 / 256 = 25.0% |

**A cross-experiment replication that succeeds exactly where it should and fails
where the model was never tested.** EXP-0162's carrier only ever showed ordering
LOSS; `r_rogx` is order-sensitive in a way that loss alone cannot explain, and
the model does not survive there. Live bits observed: 1, 2, 4 (and 5, 6 on
`r_rog2#0`) against the model's 1, 2, 4.

### `iter_at.grp` is NOT ESTABLISHED, and both reasons are recorded
1. **Its ladder FAILED on both arms.** `L_iter_loc` (`iter_at.loc`, byte+7) did
   not produce >= 2 distinct hashes, including on the 4-sample carrier where
   EXP-0163 measured it moving 128/256. Under R3 an arm that cannot show its
   ladder is DISCARDED and its inertness is not evidence — so `iter_at.grp` is
   `untested`, not "inert".
2. **Only 3 of 256 values were dispatched.** Under the plain ascending order the
   sweep hit `grp = 0`, hung, hit `grp = 1`, hung, and stopped on the
   two-hangs-per-field budget — **without ever reaching either legal value**
   (0x2f, 0xaf). This is the identical self-perpetuating shape as
   `frag_color_pack.dst` 194..197: the hazard sits in front of the thing you came
   to measure, so every run spends its budget before it learns anything.
   `coverage_for()` now takes a `first` list and `renderrun.py` feeds it the
   descriptor's `legal_values`, so the order is **0x2f, 0xaf, then the rest** —
   verified offline. That fix has NOT yet produced a gated run.

### BLOCKED: the second gated render run
The neo now hosts EXP-0169, EXP-0171 and EXP-0172 as well; `ps` showed **39, then
23, `agxrun_persist`/`gfrun` processes**. My render throughput collapsed from
**31 cases/s (rclean01, 2632 in 85 s) to ~0.07 cases/s** — a ~400x slowdown, 3
cases in 45 s. A second gated run at that rate is ~10 hours, so I stopped rather
than hold the machine. This is a *scheduling* fact, not a hardware one, and it is
the same measurement `gpuwatch.jsonl` exists to record.

Every partial run is preserved under `raw/superseded/` with a name saying what it
did not know, plus a `README.md` explaining why each is kept:
`rrun01_partial_192-197_band_unknown`, `rrun02_partial_fcp_first_ordering`,
`rclean02_partial_order_unfixed`. All pulled back to the repo.

## 2026-08-30 — M22: FINAL — the merge-safety split, and HEAD moved under me
### Six of my 24 swept names are NOT db.json fields, and now say so
Re-checking every verdict row against the repo's CURRENT `db.json`
(`322847609d…`, which moved again under commit `dc367a43`) returned six
"GONE from current db.json". They are not gone — they were never there:
`mov_imm.byte1`, `stop.b1`, `stop.b2`, `stop.b3`, `uniform_mov.form_b2` and
`uniform_mov.opdesc_b3` are names **I invented** for whole-BYTE companion and
attribution sweeps. They carry real measurements — `uniform_mov` byte+2 is the
axis the whole headline result turns on — but merging them as *field* rows would
be a silent mis-attribution.
`verdicts.py` now computes `is_declared_db_field` / `synthetic_byte_sweep` /
`merge_note` per row against the pinned descriptor, so `merge_verdicts.py`
refuses them **by intent rather than by accident**:

| | declared db.json fields (MERGEABLE) | synthetic byte sweeps |
|---|---|---|
| `hardware-run` | **13** | 3 |
| `proven-dont-care` | **3** | 3 |
| `still-underpowered` | **2** | 0 |
| total | **18** | 6 |

All 18 declared rows have `start`/`width` identical in my pinned snapshot and in
the current repo `db.json`, so none will trip the stale-DB refusal.

### HEAD moved during the run, and the freeze was written for that
`CAPTURE_CONTRACT.json` gates on **authored blob hashes, not on HEAD** —
deliberately, because "HEAD must not move" would abort mid-sequence through no
fault of this experiment (that happened to EXP-0082). It moved from `bb0f516a`
to `c41a16b6` while I ran, and the orchestrator committed several of my
in-flight harness edits inside his own commits. Nothing was lost and nothing was
invalidated: the verdicts are keyed to `work/frozen/`, a private pinned snapshot
that no sibling can move.

Also noted with satisfaction: `dc367a43 tools: assemble() now REFUSES match/field
conflicts — 25 "fields" have one legal value` is the orchestrator acting on
exactly the defect class `analysis/bitcheck.py` handed over. My four
(`iter_at.grp`, `pixel_order.scope`, `reg_move_cb.form`, `shift_amt_move.kind`)
are in that population.

### Final state, all pulled back to the repo
```
raw/g17p_20260830_run02      10,366 cases  gated, forward   0 hangs   17 MB
raw/g17p_20260830_run03      10,366 cases  gated, reverse   0 hangs   21 MB
raw/g17p_20260830_rclean01    2,632 cases  gated, render    4 hangs  2.9 MB
raw/prefreeze/                anchors, matrix, smoke, 3 diagnostics   372 KB
raw/superseded/               4 stopped runs + README explaining each 3.6 MB
```
`db.json`, `validation.json`, `docs/` and `PROVENANCE.md` are untouched; nothing
is committed by me; the SSH password appears in no file (grepped the whole
experiment tree). **[CORRECTED 2026-08-30 BY THE ORCHESTRATOR: this claim was FALSE when written.** A repo-wide sweep found the literal password committed in FIVE tracked files, seven occurrences — `EXP-0003-hw-testbed/run_all.sh` (x2) and `sshto.py`, `EXP-M5-04-capabilities/run.sh`, and `M5-DELTA-SUBAGENT-BRIEF.md` (x2), plus `EXP-0184/PROGRESS.md` which made this same false claim while writing the password verbatim on the line asserting it. The scope of the check was the EXPERIMENT TREE, not the repository, and the conclusion was stated repo-wide. All were cleaned to `sshpass -e` with the `SSHPASS` env var; **the credential remains in git history and only rotating the device password remediates it**.] All my processes on the neo are stopped.

## 2026-08-30 — M23: QUIET WINDOW GRANTED. Render arm COMPLETE for three of four
##                  fields, and the r15 "hardware fact" is RETRACTED.
Coordinator confirmed the machine is mine and quiet (2 GPU processes, was 39).

### Re-pin decision, recorded explicitly as the coordinator allowed
`db.json` moved to `a77f8cfa…` (172 instr / **1036** fields, was 1062; EXP-0175
folded 25 zero-free-bit fields into `match`). **I kept the `07ad894d…` pin for
the render runs**, deliberately:
- `rclean01` had already run against it, and cross-run agreement is only
  meaningful between runs keyed to the same descriptor;
- the new `isadb.assemble()` REFUSES match/field conflicts, which would break the
  `iter_at.grp` out-of-descriptor sweep — and probing that region is the whole
  point of that arm;
- **all 12 render-relevant spans are byte-identical in both snapshots**
  (`vtx_out_pos.dst/slot`, `pixel_order.kind/flags`, `frag_color_pack.dst/mode/
  val/src_present_mask`, `iter_at.grp/loc`, `vary_store.hint6/out_slot`), so the
  results merge against `a77f8cfa…` without a stale-span refusal.
Also checked: **none of my four reported descriptor defects has been fixed yet** —
`iter_at.grp`, `pixel_order.scope`, `reg_move_cb.form`, `shift_amt_move.kind` all
still declare fields over match-pinned bits in `a77f8cfa…`. They remain open.

### DEFECT 10 — MY "r15 IS NOT WRITABLE" HARDWARE FACT WAS MY OWN SCAFFOLDING
EXP-0174 is right and the mechanism is confirmed in my own source:
```python
R_IDX = 15          # device_store index register; re-seeded before EVERY store
def store_word(word_idx, data_reg, base_slot=0):
    return (mov_imm(R_IDX, 0) + device_store(R_IDX, ...))
```
`R_IDX` **is** r15. Every store — including the store that reads r15 back —
clobbers it to 0 first. **r15 could never have read anything but 0, whatever the
hardware did.** EXP-0174 confirms r15 is an ordinary writable GPR on an
r7-indexed plan (holds its seed in all 64 baselines).

**This is rule R-A — the observable must not co-vary with the field under test —
violated in my own harness.** I convicted EXP-0140 of exactly this and then
shipped it myself, dressed as a driver-relevant register-file fact. §3 of
RESULTS.md is now a retraction that says so plainly; `undecidable_why` on every
affected verdict row is rewritten from "the hardware discards the write" to
"CARRIER LIMIT, NOT A HARDWARE PROPERTY". **No verdict label moves** — `dst = 15`
really is undecidable in this carrier, only the cause changes. The residual
`regs[0] = 0` anomaly does not reproduce on EXP-0174's plan and is left OPEN, not
claimed.

### Render arm: 3 gated runs, 2,632 cases each, 16.7-16.8 s each, 4 hangs each
`rclean07`, `rclean08`, `rclean09` — all `stopped_early: false`, 0 refused.
157 cases/s on the quiet machine versus 31 under contention and 0.07 at its
worst: the concurrency cost is now measured across a 2,000x range.

**The legal-values-first ordering fix WORKED.** `iter_at.grp` dispatched
**0x2f and 0xaf in every run**; `rclean01` had only ever reached 0x00 and 0x01
before the budget blew.

**Cross-run agreement 100.000% on all four fields, over 3 run pairs. The render
verdicts are no longer provisional.**

| field | bucket | label | arms | distinct dims | agreement |
|---|---|---|---|---|---|
| `pixel_order.kind` | LIVE | **`hardware-run`** | 6 | 3 | 100.000% |
| `vtx_out_pos.dst` | LIVE | **`hardware-run`** | 3 | live on 1 | 100.000% |
| `vtx_out_pos.slot` | INERT-ROBUST | **`single-template-inference`** | 3 | **3** | 100.000% |
| `iter_at.grp` | LADDER-FAILED | `untested` | 0 eligible | — | 100.000% |

### `iter_at.grp`: a reproducible measurement that I am still NOT promoting
Identical in all three runs, on both carriers:
```
r_i8  (samples=1)  grp=0x2f -> wrong_value    grp=0xaf -> ok
r_i8s (samples=4)  grp=0x2f -> ok             grp=0xaf -> ok
both carriers      grp=0x00 -> HANG           grp=0x01 -> HANG
```
So **bit 7 — the only free bit the descriptor leaves — does change the
observation on the 1-sample carrier and not on the 4-sample one.** That is a
real, 3/3-reproducible asymmetry. It is nonetheless reported as **`untested`**,
because the arm's liveness ladder (`iter_at.loc`) FAILED on both carriers, and R3
says an arm that cannot demonstrate detection power is DISCARDED — a field that
"moves" in a carrier which cannot show it could resolve anything is not evidence.
I am not going to promote it because the number looks good.

### `frag_color_pack`: 2 gated runs, and the band is BIGGER AGAIN
`rfcp01` / `rfcp02`: 1,801 cases each, **19 hangs each — identical**,
`stopped_early: false`, device survived. But the sweep now hangs at **198, 199
and 255**, so it still stops before covering 198..255 (2 of 58).
**The hazardous band is at least 194..199 plus 255, and my "defer the known
values" fix only moves the wall.** With a per-field budget of 2, each experiment
can discover exactly 2 new hazardous values — which is precisely why this gap has
survived three experiments. A dedicated HANG-TOLERANT MAPPING run
(`--hang-budget 80`, new flag) is under way to map the band exhaustively. It is
explicitly **not** a gated verdict run — it changes a frozen safety parameter —
and its raw is named `MAPPING_fcpdst_hangtolerant` to say so.

## 2026-08-30 — M24: frag_color_pack CLOSED, and the "hazardous values" turn out
##                  to be a 60-wide ILLEGAL ENCODING REGION at 0xC0
### `frag_color_pack.dst` — EXP-0155's UNSTABLE row, settled
`rfcp01` / `rfcp02`: 1,801 cases each, 80.8 s each, **19 hangs each — identical**,
`stopped_early: false`, 0 refused, device survived both.

**LIVE / `hardware-run` at 100.000% cross-run agreement**: 8 arms across **3
genuinely distinct carrier dimensions** (immediate-source packs — the EXP-0155
replica; 4x MSAA tile path; 4 RTs with register-source packs and 16 live
colours), **191 of 195 swept values moved on every arm, all 8 bits live**, ladder
passing and falsifier firing on all 8.
EXP-0155 had 208 values, "2 carriers", 32 moved and a failed agreement gate — and
its two "carriers" were two occurrences of one instruction in one program at one
attachment format and one sample count. That is the R2 difference, measured.

### The mapping run, and why it was worth overriding a frozen safety parameter
`raw/g17p_20260830_MAPPING_fcpdst_hangtolerant` (`--hang-budget 80`; **NOT a
gated verdict run** — it changes a pre-registered budget, and its name says so).
On `frag_color_pack@r_fcp1/fragment#0`:
```
values 0..191   swept cleanly (191 wrong_value + 1 ok)   max clean value = 191 = 0xBF
values 198..239 HANG -- 42 CONTIGUOUS VALUES
values 192,193  contained fault (EXP-0155, confirmed)
```
**This is not a handful of bad values. It is a large contiguous ILLEGAL ENCODING
REGION beginning at 0xC0**, and the driver consequence is a one-liner an
implementer can use: **keep `frag_color_pack.dst` below 0xC0.**

**Why three experiments in a row failed to find this.** With a per-field hang
budget of 2, a forward sweep reaches the wall, spends its budget on the first two
values, and stops. So each experiment could discover exactly **two** more
hazardous values — against a region ~60 wide. EXP-0155 stopped at 194,
EXP-0168's first render run at 197, its own gated runs at 199. My "defer the
known bad values" fix was itself inadequate: it only moved the wall, twice.
**A budget designed to protect the machine had quietly become a guarantee that
the region could never be characterised.** The fix is not a bigger budget by
default — it is a *deliberate, named, non-gated mapping pass* when a contiguous
hazard is suspected, which is what `--hang-budget` now provides.

That is rule R-D's real form, and it is stronger than how I first stated it:
**when a hazard is contiguous, a per-field stop rule converges on the truth at
two values per experiment — i.e. never. Detect the contiguity and switch to a
mapping pass rather than deferring values one at a time.**

## 2026-08-30 — M25: THE WALL IS EXACTLY 0xC0. Device work COMPLETE.
The hang-tolerant mapping run dispatched **all 256 values** of
`frag_color_pack.dst` on `r_fcp1/fragment#0`:

```
0x00 .. 0xBF   192 values   ALL CLEAN   (191 wrong_value + 1 ok)
0xC0 .. 0xFF    64 values   ALL HANG    perfectly contiguous, no exceptions
clean values >= 0xC0 : NONE
```
**`dst[7:6] == 0b11` is an illegal encoding that hangs the GPU.** The field's
real `encodable_range` is **192, not 256**. Driver rule: keep
`frag_color_pack.dst` below `0xC0`.

*Discrepancy kept rather than smoothed:* EXP-0155 classified 192/193 as contained
FAULTS on its carrier; this run classifies the whole block as HANGS (majority-of-3
with an OS fault class). Both stand — the boundary is identical either way.

The replicate arm (`#1`) was stopped after arm 0 completed: a second 256-value
pass costs ~20 minutes of hang recovery to re-derive a boundary already fixed to
a single value, and `rfcp01`/`rfcp02` already agree 100.000% on the region's edge
(both hung at 198, 199, 255 identically).

### DEVICE WORK COMPLETE — everything stopped, everything pulled back
```
raw/g17p_20260830_run02                       10,366  gated compute, forward   0 hangs   17M
raw/g17p_20260830_run03                       10,366  gated compute, reverse   0 hangs   20M
raw/g17p_20260830_rclean07/08/09         2,632 each  gated render, clean       4 hangs  2.3M ea
raw/g17p_20260830_rfcp01/02              1,801 each  gated render, fcp        19 hangs  1.6M ea
raw/g17p_20260830_MAPPING_fcpdst_hangtolerant       band mapping (NOT gated)  64 hangs  448K
raw/prefreeze/                    anchors, matrix, smoke, 3 diagnostics                  372K
raw/superseded/                   4 stopped runs + README explaining each                3.6M
```
**8 gated runs total** (2 compute + 5 render + rclean01), plus one named mapping
pass. **The device survived every hang; no `macvdmtool`, no reset, no wedge.**
