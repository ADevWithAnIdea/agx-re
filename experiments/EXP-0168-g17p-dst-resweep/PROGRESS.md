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
