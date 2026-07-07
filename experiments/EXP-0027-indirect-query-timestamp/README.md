# EXP-0027: cmdstream completeness — indirect commands, occlusion queries, timestamps (G-14)

- **Date:** 2026-07-07
- **Clean-room category:** DATA-TRACE (primary) + HW-PROBE (MSAA per-sample, timestamp correlation) + OWN-SHADER.
- **Phase / question:** Phase 2 cmdstream decode acceptance-gate gaps (G-14). Extends
  EXP-0011 (compute CDM), EXP-0014/-0019/-0024 (graphics VDM/state), EXP-0021 (MSAA/TBDR).
- **Device state:** A18 Pro / G17P, SoC T8140, macOS 26.6 (25G5043d), SIP disabled, 5 GPU cores.

## Hypothesis
The command stream encodes four not-yet-characterized capabilities discoverably by
change-one-Metal-parameter diffing of registered BOs:
1. Indirect (device-generated) commands — an args-in-a-buffer draw/dispatch must place a
   pointer to the args buffer in the VDM/CDM (vs an inline count), and a full
   `MTLIndirectCommandBuffer` must carry fully-encoded commands.
2. Occlusion queries — a visibility-result-buffer pointer, a per-draw mode field
   (Boolean vs Counting), and a per-draw counter offset live in the 3D/tiler state.
3. GPU timestamps — a counter sample buffer receives uint64 timestamps at pass boundaries;
   the format/period is measurable by correlation to wall-clock.
4. (Stretch) MSAA — N samples are independently maintained; interleave is tile/firmware side.

## Method (clean-room legality)
DATA-TRACE: interpose the IOKit user↔kernel boundary (`tools/iotrace`, read-only, built
`-arch arm64e`) and snapshot the registered GPU BOs of **our own** Metal programs, then
byte-diff (`bodiff.py`) captures that differ in exactly one Metal parameter. Command
buffers/descriptors are non-copyrightable hardware data. OWN-SHADER: every shader is our
own MSL compiled at runtime. HW-PROBE: MSAA per-sample readback and the timestamp/wall-clock
correlation observe hardware behaviour. **No Apple binary was disassembled.** Where the
indirect-dispatch path or ICB uses a Metal-generated helper shader, it was *located, not
disassembled* (clean-room rule 5).

## Procedure
Four parametric harnesses (device `~/cleanroom_work/exp0027/`; artifacts pulled back here):
- `ivar.m` + `run_ivar.sh` — direct vs args-in-buffer vs full-ICB draws/dispatches.
- `qvar.m` + `run_qvar.sh` — `setVisibilityResultMode:offset:` (none/bool/count/offsets/two-draw).
- `tvar.m` + `run_tvar.sh` — `MTLCounterSampleBuffer` timestamp sampling (compute/render) +
  `[dev sampleTimestamps:gpuTimestamp:]` correlation.
- `mvar.m` — MSAA per-sample write (`[[sample_id]]`) + resolve + per-sample read-back.

Each `run_*.sh`: builds `iotrace.dylib` + the harness, captures a one-parameter matrix under
`DYLD_INSERT_LIBRARIES=iotrace.dylib … --dump`, and diffs with `bodiff.py`/`dumpscan.py`/
`bograph.py`. Reproduce: `sh run_ivar.sh` (etc.) on the device, then pull `ana*/`, `capi*/…hex`.

## Raw results
`raw/ivar/` (INDIRECT_FINDINGS.txt + ana/ diffs + curated hex), `raw/qvar/`
(OCCLUSION_FINDINGS.txt + anq/ + hex), `raw/tvar/` (TIMESTAMP_FINDINGS.txt + ant/ + hex),
`raw/MSAA_FINDINGS.txt`. See `RESULTS.md` for the decoded fields.

## Analysis / Established facts → docs
See `RESULTS.md`. Feeds `docs/cmdstream/` (indirect draw/dispatch opcodes + args pointer,
occlusion query fields), `docs/pipeline/` (timestamp sampling points, MSAA per-sample),
`docs/kernel-interface.md` (indirect-dispatch grid-setup, sample-buffer address handoff),
`docs/hypotheses.md` (capability rows). Orchestrator merges + adds `PROVENANCE.md` rows.

## Follow-ups
See `RESULTS.md` §7.
