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
