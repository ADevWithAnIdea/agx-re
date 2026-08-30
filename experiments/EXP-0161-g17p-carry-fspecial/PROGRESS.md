# EXP-0161 — PROGRESS (append-only, one entry per milestone)

Target **G17P** (A18 Pro, `192.168.10.243`). `macvdmtool` forbidden. If the neo stops
answering: STOP and report BLOCKED.

## 2026-08-29 23:2x — dispatch read; scope fixed
Task: (1) redo EXP-0154's `CARRY_GEN` and `MOV_ZEXT16` arms, which promoted nothing
because their seeds were all <= 127 and the instruction was a no-op in that carrier;
re-test `ibfe.offset`/`ibfe.width` in a strongly-live carrier. (2) Open `fspecial`
(11 fields, never swept; byte+3 >= 192 hangs).

## 2026-08-29 23:3x — pre-registration written and frozen
`PRE_REGISTRATION.md` (H1..H7, falsifiers F1/F1b/F2/F3/F4, stop rules) committed before
any build or run.

## 2026-08-29 23:4x — anchors extracted on the neo
`work/anchors/anchor_report.json`. All needed anchors exist in OUR OWN MSL:
`k_u64add` -> `iadd2@32 carry_gen@42 psel@48 iadd2@52 iadd2@62` (block [32:72],
carry_gen at +10); `k_zext16` -> `mov_zext16@18`; `k_bfe` / `k_shr_const` -> `ibfe@18`
(two independent lowerings); `k_rsqrt` / `k_log2` / `k_exp2` / `k_sqrt` / `k_floor` /
`k_rcp@fm` -> a single `fspecial@18`; `k_rsqrt_precise` -> `fspecial_est@18`.
`k_zext16_two` produced NO mov_zext16 (folded), so only `k_zext16` anchors it.

## 2026-08-29 23:5x — SMOKE #1: found a defect IN MY OWN HARNESS, not the hardware
Seeding r0..r14 by 15 `device_load`s delivered only r5..r14; r0..r4 read 0.
`harness/pilot_seed.py` (8 variants) isolated it: **a `device_store`'s data-register
read is NOT interlocked against a pending `device_load` on G17P** — the first ~5
stores issued after a load wave return the register's PRE-LOAD value, and the effect
follows the STORE order, not the load order (P5: dumping r15..r0 moved the stale set to
r11..r14). Fixed by two load waves plus 6 drain stores.
Raw: `raw/prefreeze/pilot_seed.json`.

## 2026-08-29 23:5x — SMOKE #2 (post-fix): every gate passes
* seeding 15/15 correct, **stable over 8 consecutive dispatches**;
* **F1 `carry_gen byte0:=0x00` FIRES**, **F1b `byte+2:=0x00` FIRES** — the exact test
  EXP-0154 failed. The carrier fix works.
* **F2 `mov_zext16 byte0:=0x00` FIRES**, and the instruction is visibly live:
  r1 `0x8f4e7a15 -> 0x00007a15`. (Note: the anchor's `src_reg` byte is 0x00, which
  would name r0, but the value extracted is r1's — flagged for the sweep.)
* **F4 `fspecial byte0:=0x00` FIRES**; r0 `4.0 -> 0.5` (rsqrt).
* all 7 INPLACE carriers reproduce their host-computed oracle unmutated.
Raw: `raw/prefreeze/smoke_postfix.json`.

## 2026-08-29 23:5x — CAPTURE_CONTRACT frozen
11,942 unlocked cases, `matrix_sha256 38965f91...`; 65 lease-only danger cases,
`danger_sha256 b2976008...`. Authored-input sha256s, anchors, stimulus, raw schema,
timeouts and gates all frozen.

## 2026-08-30 00:0x — gated runs run01 (forward) + run02 (reverse) COMPLETE
11,942 cases each, 0 watchdog hangs, 0 baseline failures, ~100-125 s per run.
Counters agree to within 0.2% on an identical matrix executed in opposite arm order;
`ok` is **identical** at 3,531 in both. 175 victim-class cases excluded, **13
disagreements** (all `fault` <-> `wrong_value`).
**All 11 baselines `ok`. 10 of 11 arms passed their falsifier gate.**
The one that did not is `B_ZEXT_INPLACE` — EXP-0146's own carrier — where deleting the
whole instruction (`byte0 := 0x00`) STILL produces the correct answer. That is a
first-class negative: it explains EXP-0146's "byte+1 INERT" as a carrier artefact.

## 2026-08-30 00:2x — GENERATION PROOF (gen01/gen02/gen03)
Encodings the compiler never emitted, predicted HOST-SIDE and then executed:
* `fspecial` **20/20 pass** — `r_i = rsqrt(r_j)` for arbitrary i,j.
* `carry_gen` **48/48 pass** — 32-bit AND 16-bit compares, bit7 set and clear.
  gen02 first failed 9/16 with an `is32 = 0` model; every one of the 16 outcomes is
  explained exactly by the size bit being real, and gen03 tests the corrected model.
* `mov_zext16` **11/16** — `r[n] = r[n] & 0xFFFF` for n = 0..10 driven by byte0's HIGH
  NIBBLE, a field `db.json` does not model; nibbles 0xB..0xF are a no-op.

## 2026-08-30 00:3x — COURTESY NOTICE (FIELD-SWEEP-PROTOCOL section 7, "Courtesy, not a rule")
About to sweep `fspecial` byte+3 (`src`) **192..255**, the region EXP-0138 recorded three
reproducible GPU hangs in. Run in its own process, 12 s watchdog, unlocked per the current
NEO-TARGET-BRIEF ("Concurrency: unrestricted. There is no lease."). **Stop rule armed: two
genuine hangs end the arm.** If the device resets, EXP-0161 is the likely cause.
