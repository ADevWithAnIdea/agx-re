# EXP-0174 — PROGRESS

Append-only. One entry per milestone. Assume the session is killed at any moment;
re-orient from this file, `PRE_REGISTRATION.md`, `CAPTURE_CONTRACT.json` and what is
actually in `raw/`.

## M0 — 2026-08-30 — orientation complete (no device work yet)

Read: `CLAUDE.md`, `CODEX.md`, `experiments/SUBAGENT_BRIEF.md`,
`experiments/FIELD-SWEEP-PROTOCOL.md` (incl. the four rules added 2026-08-30),
`tools/agx-isa/db.json` descriptors for `n3_mov` / `mov_zext16` / `frame_marker` /
`n2_op6` / `reg_move_c0` / `device_store`, `tools/agx-isa/validation.json` labels,
EXP-0168 (`RESULTS.md`, `harness/isa_helpers.py`, `harness/sweeprun.py`,
`harness/anchors.py`, `harness/casematrix.py`), EXP-0173 §7, EXP-0166
`analysis/decomposed_fields.json`.

Pinned state at orientation:
- repo `HEAD` = `f3c91a01c9fdfabb7f16051259c04390084556fb`
- `tools/agx-isa/db.json` sha256 `322847609de79055b651b79fbd630948bb97120bcefd037a3c7ae5a301ba64a5`
  (172 instructions, 1062 fields)
- `tools/agx-isa/isadb.py` sha256 `9cda47a1d4b3857c9f20423ab5d63c38050d37220da06bc5d2dc12a77d6ef1a8`
- `tools/agx-isa/validation.json` sha256 `09842bad7b647f3828544d76a1708df1fc38d151de3fd82ea11b936af8a8a990`
- neo reachable, `users-MacBook-Neo.local`, macOS 26.6, load ~1.5 (siblings active).

Target field labels confirmed as dispatched: `n3_mov.dst`, `.srcA_reg`, `.srcA_uni`
are all `corpus-correlation` (target M4, evidence EXP-M4-13, COMPILE-ONLY).
`n3_mov.subform` / `.companion` are `hardware-run` from EXP-0157 but in the
`u64eq` carrier, which is not register-observable.
`n3_mov` has **no** rows in `tools/agx-isa/match_overlap.json`, so `dst`,
`srcA_reg` and `srcA_uni` are fully free bits — the descriptor `match` is only
byte0's low nibble == 3.

### TWO PREDECESSOR DEFECTS SUSPECTED BEFORE ANY DEVICE WORK (to be measured, not assumed)

1. **EXP-0168's "r15 is not writable through a 4-bit dst nibble" is very likely a
   harness artifact.** In `EXP-0168/harness/isa_helpers.py`, `R_IDX = 15` and
   `store_word()` emits `mov_imm(R_IDX, 0)` immediately before EVERY
   `device_store` — including the store whose `data_reg` is 15. So r15 is zeroed
   by the read-back path itself, one instruction before it is read. r15 reading
   `0x0` is what that program must produce whether or not r15 is writable. This
   is structurally the same by-construction blindness (observable co-varies with
   / destroys the thing observed) that EXP-0168 itself exposed in EXP-0140.
2. **EXP-0168's r0 slot may also be dead.** Its committed
   `raw/g17p_20260830_run02/baseline.jsonl` records `regs[0] = 0` while
   `SEED_I[0] = 10`; every other slot except 15 matches its seed. Candidate
   cause: `device_store` is issued with `extmode = 2*data_reg`, which is `0x00`
   for `data_reg = 0`, and `db.json` records the ALU-forwarded data-source
   encoding as `2*R` **or** `2*R|0xC0`. `extmode == 0` may not name a source
   register at all.

Both are treated as HYPOTHESES to be measured in this experiment's own
calibration, not as findings. If confirmed, they are first-class results and are
reported as such; EXP-0168's `dst` verdicts for slots 0 and 15 would need
re-reading.

Next: write `PRE_REGISTRATION.md` + `CAPTURE_CONTRACT.json`, then the harness.

## M1 — 2026-08-30 — PREFREEZE CALIBRATION: the move EXISTS, and the descriptor is wrong

`raw/prefreeze/cal01..cal04` (NEVER evidence; exploratory).

**C1 dump fidelity — the observable works, and BOTH suspected EXP-0168 defects resolve.**
All 16 slots read back their host-known `mov_imm` seeds, in both register plans and with
both `extmode` encodings (`2*R` and `2*R|0xC0`), 3 repetitions each, `moved_slots == []`.
- **`r0` reads 10 correctly here**, with `extmode = 0x00` as well, so EXP-0168's
  `regs[0] = 0` is NOT reproduced by this harness and is NOT explained by `extmode`.
  Left as an open question about that experiment, not a finding of this one.
- **`r15` reads 121 correctly in plan `idx7`.** `mov_imm(15, 121)` lands. EXP-0168's
  "a write whose 4-bit destination nibble is 15 is discarded, and the slot reads 0" is
  contradicted: in a plan where the read-back path does not use r15 as its index
  register, r15 holds exactly what was written to it.

**C2/C3/C4 — `n3_mov` IS a register move, and the db.json operand model is off by one bit.**
`23 0a 01 00` (dst=2, byte+1=0x0a, byte+2=0x01, byte+3=0x00) puts r5's value into r2.
Dense maps (`raw/prefreeze/cal04/n3map.jsonl`):
- byte+1 = `2*srcReg + srcHalf`: even values 0,2,...,28 select r0..r14; 128..156 select
  r64..r78 which alias to r0..r14 -> **source aliasing period 64**; ODD values select the
  source's **HIGH 16 bits** (byte+1 = 0x13 yields `0x4020`, the high half of r9 =
  `0x40200000`; byte+1 = 0x12 yields `0x0000`, its low half). db.json models
  `srcA_reg` = byte+1 bits 0..6 and `srcA_uni` = bit 7; measured, the register is bits
  **1..7** and bit **0** is the half-select. **DB DEFECT.**
- byte0 high nibble = dst, confirmed for r0..r14 (r13/r15 are this plan's masked/blind
  slots and are covered by plan `idx7`).
- **The move is 16-BIT GRANULAR.** With dst = r9 (pre-set to `0x40200000`) and src = r5
  (=65): `93 0a 01 00` -> `0x40200041` (low half written, HIGH HALF PRESERVED) and
  `93 0a 01 01` -> `0x00410000` (high half written, low half zeroed).
- byte+2 is an OP selector, not a "source-class/size sub-form": `& 3 == 0` is the
  in-place narrow (`mov_zext16`, byte+1 inert -- reproduces EXP-0161), `& 3 == 1` is the
  move, `== 3` behaves as XOR and `== 4` as OR of byte+1 and byte+3 operands
  (`93 0a 04 08` -> `0x41 | 0x3a = 0x7b`).
- **byte+2 bit 3 releases the source**: b2 in {0x09,0x0d,0x19,0x1d} additionally modify
  the SOURCE register r5. Release-on-read, as EXP-0086/0089/0099 documented elsewhere.
- Falsifiers fire: byte0 low nibble 1/2/4/9/b/c/e all give different observations, so the
  method demonstrably resolves differences on this instruction.

Next: test the composed 32-bit copy (`hi` then `lo`), then freeze.

## M2 — 2026-08-30 — PREFREEZE: full 32-bit GPR-to-GPR copy GENERATED and executed

`raw/prefreeze/cal05/copy32.jsonl` (still calibration, not evidence).

Two generated `n3` instructions, no byte copied from any compiled shader, compose into a
complete 32-bit register copy:

    X3 (2*S+1) 01 01     ; r[X].hi <- r[S].hi   (low half PRESERVED)
    X3 (2*S+0) 01 00     ; r[X].lo <- r[S].lo   (high half PRESERVED)

`23 13 01 01 | 23 12 01 00` puts r9's full `0x40200000` into r2, in BOTH register plans,
for 8 (dst, src) pairs, and in either instruction order (the two halves are independent
partial writes, so order does not matter). Single-half controls confirm the preservation:
`23 13 01 01` alone gives `0x40200022` -- r2's own low half `0x0022` survives.

Also measured: `subform` bit 3 (0x08) RELEASES the source -- b2 in {09,0d,19,1d} leave
r5 = 0 as well as writing the destination; b2 in {01,05,11,15} leave the source intact.

Model to be FROZEN and tested (falsifiable):
  for `X3 b1 b2 b3` with (b2 & 0x03) == 1, (b2 & 0xE0) == 0, b3 in {0x00, 0x01}:
      S = (b1 >> 1) mod 64 ; hs = b1 & 1 ; hd = b3 & 1
      r[dst] = (r[dst] & ~(0xFFFF << 16*hd)) | (((r[S] >> 16*hs) & 0xFFFF) << 16*hd)
      if (b2 & 0x08): r[S] released
Next: PRE_REGISTRATION.md + CAPTURE_CONTRACT.json, then two gated runs.

## M3 — 2026-08-30 — FROZEN. `PRE_REGISTRATION.md` + `CAPTURE_CONTRACT.json` committed.

Case matrix sha256 `f6d2a2199c33f84e1ef6568eeb4edbb9e803b62a0dab945fbdcb53308bf9bc87`,
5822 cases across 14 arms, plus a 65536-case `I/grid` (full byte+2 x byte+3 cross-product).
Pinned toolchain `work/frozen/db.json` sha256 `3228476…`, resolved with NO fallback.

One thing to flag for the reviewer: this experiment dispatches at ~1400 cases/second,
roughly 70x EXP-0168's rate, because the carrier is a 1-thread 1-group dispatch of a tiny
program on a persistent runner. That is fast enough that "the child cached a pipeline and
re-ran an earlier program" is a live alternative explanation, so arm `X/alternate` was added
BEFORE freezing: two distinct blocks dispatched alternately 20 times each in both plans,
which must never converge. Every case also records `gputime_ns` from the runner.

Starting run01 (forward) and run02 (reverse).

## M4 — 2026-08-30 — GATED RUNS COMPLETE, analysis and write-up done

`raw/g17p_20260830_run01` (forward, 5822 cases + 65536 grid),
`raw/g17p_20260830_run02` (reverse, 5822 + 65536 in the other plan),
`raw/g17p_20260830_run03` (65536 grid, same plan as run01, reverse order).
0 hangs, 0 stopped arms, `carrier_hangs = 0`, 2 invalid cases (both the byte0-low-nibble-0xe
falsifier, which over-consumes and poisons the dump -- correctly excluded).

**Every field clears the gate on both clauses**: 100.000% cross-run agreement, ZERO
disagreements, >= 2 carriers. `n3_mov.dst`, `.srcA_reg`, `.srcA_uni`, `.subform`,
`.companion` and `._instruction` are all `hardware-run`.

**840 generated 32-bit GPR-to-GPR copies and 1680 generated half-moves passed a
host-computed 16-register prediction with 0 failures, in both runs.**

Controls: the stale-pipeline control never converged (65 in all 40 dispatches of one block,
10 in all 40 of the other, both plans, both runs); `gputime_ns` non-zero on 5820/5822;
the two same-plan grid runs agree on 65536 of 65536 records.

Two parts of this experiment's OWN frozen model were refuted by its own pre-registered
falsifiers and are recorded as corrections, not smoothed: the move mask is
`(b2 & 0xC0) == 0` (16 values, bit 5 free), not `(b2 & 0xE0) == 0` (8); and byte+3's accept
rule is `(b3 & 0x1E) == 0`, not `b3 < 2`.

Also written: `analysis/field_verdicts.json` (6 hardware-run rows + 4 db_defects),
`analysis/gate.json`, `analysis/maps.json`, `analysis/grid_census.json`, `RESULTS.md`,
`README.md`, `manifest.json`.

NOT done, by instruction: no `git commit`; no edit to `db.json`, `validation.json`, `docs/`
or `PROVENANCE.md`.
