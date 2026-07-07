# EXP-0021: TBDR pipeline specifics (tile size, imageblock, MSAA, memoryless, load/store)

- **Date:** 2026-07-07
- **Clean-room category:** DATA-TRACE + HW-PROBE (log/observe data crossing the userspace↔kernel
  boundary from our OWN Metal draws; never disassemble Apple code)
- **Phase / question:** Phase 4 (TBDR & compute specifics) → feeds `docs/pipeline/`.
  Follows up EXP-0014 §7 open items (attachment dims/tile config, 3-segment load/render/store,
  tiler parameter buffer) and EXP-0019 (state packets).
- **Device state:** A18 Pro / G17P, macOS 26.6 (25G5043d), SIP off. No boot-args changes.

## Hypothesis
The G17P is a Tile-Based Deferred Renderer. The userspace-visible TBDR configuration a driver
must emit is encoded in the control BOs already located in EXP-0014: the **tiling context**
(`0x68000`), the **3D attachment descriptor** (`0x10000110000`), the **FF-state pool**
(`0x58000`), and the **tiler geometry/parameter heap** (`0x10000018xxx` / `0x10000140000`).
We expect: a fixed fragment tile size (32×32) whose count scales with RT dimensions; an
on-chip imageblock budget that scales with attachment count/format; sample count + programmable
sample positions in the attachment/tiling state; a memoryless flag that drops the main-memory
backing; and a 3-segment (load/render/store) attachment chain.

## Method
Extend the EXP-0014 `dvar.m` change-one-parameter draw harness into **`tvar.m`**, adding TBDR
knobs: `--samples {1,2,4}`, `--sampos` (programmable sample positions), `--mrt {1..4}`,
`--mldepth` / `--mlcolor` (memoryless), `--nocolor` (depth-only / partial render),
`--load/--store/--dload/--dstore` (per-attachment actions), plus the existing `--w/--h`
(RT size) and `--fmt` (pixel format) sweeps. Capture the registered GPU BOs under the
**read-only `tools/iotrace` interposer** (arm64e) and **byte-diff** snapshots with
`bodiff.py` (change exactly one Metal parameter; noise floor is 0 real words — determinism
proven by `base` vs `base2`).

**Clean-room legality:** every shader is our own MSL compiled at runtime; we only log *data*
(command-buffer / descriptor bytes) our own process hands the kernel. No Apple binary is
disassembled or introspected. (Per CLAUDE.md allowed techniques 1–3.)

## Procedure
On the device (`~/cleanroom_work/exp0021`):
```sh
sh run.sh            # builds iotrace.dylib + tvar (arm64e), captures the matrix, diffs on-device
```
`run.sh` captures ~34 one-parameter-changed draws (+4 extra probes: rgba32f×4MSAA budget case,
non-multiple-of-32 RT sizes) and produces `analysis/diff_*.txt`, `analysis/focus_*.txt`, and
curated `hex/*.hex` + `hex/KEY_DIFFS.txt`. Pull back text only.

Harness: `tvar.m`. Reused tools (copied to the device dir): `iotrace.c`, `bodiff.py`,
`bograph.py`, `dumpscan.py`.

## Raw results
`raw/hex/` — curated control-BO hexdumps (tiling ctx `0x68000`, attachment `0x10000110000`,
tiler heap `0x10000018200`, FF-state `0x58000`) for base and each key variant, plus
`KEY_DIFFS.txt` (the clean per-field diffs). `raw/analysis/` — full `bodiff` diffs and
`focus_*` per-BO diffs (large allocation-shift diffs trimmed to a bounded head; the clean
single-field diffs are in `focus_*.txt` and `KEY_DIFFS.txt`).

Key observations are summarized in `RESULTS.md`.

## Analysis
See `RESULTS.md` for the full bit-level encoding tables and the HW-validated / inferred marks.

## Established facts → docs
All findings in `RESULTS.md` are ready to drop into `docs/pipeline/` (TBDR configuration) with
DATA-TRACE/HW-PROBE provenance (EXP-0021). The orchestrator owns `docs/`.

## Follow-ups
- Programmable sample-position *values* are not in any captured userspace BO → locate the
  firmware/register path (kernel-team coordination).
- Depth store-action is not captured (ZLS/firmware-managed) → confirm the ZLS control path.
- Full bit decode of the packed pixel-format word (`+0x20` in the attachment/tiler descriptor)
  belongs to `docs/descriptors/` (EXP-0015).
- Parameter-buffer overflow / partial-render *trigger* config (firmware-managed) — no
  userspace-visible knob found; document as kernel-owned.
