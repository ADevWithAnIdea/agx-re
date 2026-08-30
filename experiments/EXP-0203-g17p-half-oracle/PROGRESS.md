# EXP-0203 progress log (append-only)

- **M0 2026-08-30 ~11:50Z** — read SUBAGENT_BRIEF / NEO-TARGET-BRIEF / FIELD-SWEEP-PROTOCOL /
  CODEX / evidence-classification. Device verified alive (`macbookneo.lan`, macOS 26.6,
  uptime 14 min).
- **M1 2026-08-30 ~12:00Z** — OFFLINE model fit from our own committed EXP-0180 raw
  (`analysis/fit_model_offline.py`). Result: `abs(a)*b - c` matches **256/256 on each of two
  carriers**; six competing models match strictly fewer. Also established that EXP-0180's
  `byte+4 = 0x93` zeroes the byte+5 source lane and `0x13` does not, so this experiment's
  base instance uses `0x13`. **Also found: EXP-0196's "768 records over 256 distinct values"
  for `half_alu_fma12.dst` are records of bits 8..15 (the field EXP-0183 renamed `srcA`),
  not of bits 4..7. The 12-byte form's destination nibble has never been swept.**
- **M2 2026-08-30 ~11:58Z** — `PRE_REGISTRATION.md` frozen (before any harness code existed).
- **M3 2026-08-30 ~12:08Z** — harness + kernels + gate written; 16 offline gates pass locally
  and **on the neo** (Python 3.9.6). Matrix: 5296 cases,
  sha256 `d34b2f121afb6d1308bd30a749802593f41a8f63f5f41288b2b059f410ad8e00`.
- **M4 2026-08-30 ~12:09Z** — pushed to `~/agxre/EXP-0203`; `harness/verify_remote.py` reports
  **all 16 files match** (verified SEPARATELY from the push, per SUBAGENT_BRIEF).
  `CAPTURE_CONTRACT.json` + `raw/FREEZE_MARKER.txt` frozen.
- **COURTESY NOTE (FIELD-SWEEP-PROTOCOL §7):** the `F12_EXT_*` arms sweep byte+4 of the
  `byte0`-low-nibble-0 half family through all 256 values, which drives the family's LENGTH
  SELECTOR (byte+4 & 3) through all four settings. Instruction-stream desync is expected by
  design. EXP-0180 ran the same sweep on this machine with zero hangs.
- **M5 2026-08-30 ~12:11Z** — `pilot01` (752 cases, 0 faults): all 8 arms ADMISSIBLE; the
  pre-registered fma12 oracle reproduced on a fresh carrier; all falsifiers fired; the 7 frozen
  `half_pack` candidates were refuted by a source-lane RELEASE none of them expressed, and the
  corrected model scored 80/80. Amendment 02 frozen before any gated run.
- **M6 2026-08-30 ~12:14Z** — two run ids BURNED (`g17p_run01`, `g17p_run11`): `procsample.py`
  created the run directory before `run.py`, whose own guard then refused to write into it.
  Both retained with `BURNED.md`; launch order corrected.
- **M7 2026-08-30 ~12:20Z** — gated runs `g17p_run21` (fwd), `g17p_run22` (fwd), `g17p_run23`
  (rev), 5296 cases each. Gate result: `dst` 16/16 covered, `dstlo`/`b3` 256/256, all with
  100% oracle match and 0 cross-run disagreements.
- **M8 2026-08-30 ~12:26Z** — `RE_EXPERIMENT_PROCESS_CORRECTIONS.md` read. Scored the captured
  runs against it: Gates B, C, E met; **Gate A (actual-byte ledger) NOT met**. Amendment 03
  frozen: per-case actual-byte ledger, per-case Gate C semantic class, a second disjoint
  readback plan (new arms HP_C, HP_D, F12_EXT_C), and the G7 tokenizer-conjunct correction.
  Matrix 8410 cases, sha256 `e8325420acc4…`.
- **M9 2026-08-30 ~12:35Z** — gated runs `g17p_run31` (fwd) and `g17p_run32` (rev), 8410 cases
  each. Ledger: **16820/16820 bytes_match, 16512/16512 requested == decoded**, independently
  re-verified offline. 1 fault, 1 InnocentVictim, both in `ext` arms. Cross-run: 1 disagreement
  in 8410.
- **M10 2026-08-30 ~12:45Z** — verdicts, six-axis classification, db_defects, ext byte map,
  RESULTS.md, README.md, manifest.json. `tools/agx-isa/wave_audit.py` run: no constant oracles,
  no aliasing, 100% cross-run agreement, hard outcomes counted separately.
