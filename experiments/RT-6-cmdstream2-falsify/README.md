# RT-6 — Red-team falsification of indirect commands, queries, timestamps, geometry-output

**Role:** adversarial verifier. Assume the EXP-0027 (indirect/query/timestamp) and EXP-O2A
(geometry-output) command-stream findings — as merged into `docs/cmdstream/README.md`
("Completeness…" and "Geometry-output pipeline" sections) and `docs/pipeline/README.md` — may
be **subtly wrong**, and run tests designed to **break** them: change-one-Metal-parameter
byte-diffs, adversarial multi-command / edge cases, and a cross-check against RT-2a's
indexed-record-shift finding.

**Device:** Apple A18 Pro / G17P, macOS 26.6 (25G5043d). Workspace `~/cleanroom_work/rt6/`.
**Clean-room:** DATA-TRACE + OWN-SHADER only. Every shader is our own MSL compiled at runtime;
`tools/iotrace` (read-only, built `-arch arm64e`) snapshots the GPU BOs our own Metal process
registers into the GPU VM; we byte-diff those. No Apple binary was disassembled or introspected.
Metal-injected helper shaders (indirect-dispatch grid-setup, blend/a2c microprograms) were
*located, never disassembled*.

## Method
`iotrace.dylib` (arm64e) is `DYLD_INSERT_LIBRARIES`-interposed over the IOKit user-client surface;
each harness renders/dispatches its own minimal MSL, prints the GPU VAs of its own resources, then
`kill(SIGUSR1)` triggers a full BO snapshot after `waitUntilCompleted`. Fields are localised by
diffing the control BOs (`0x18000` VDM/tiler, `0x58000` 3D fixed-function state, `0x68000`
viewport/tiling context, `0x100000b0000` CDM, `0x10000100000` vertex-attr/vis-buffer,
`0x10000080000` control) between a baseline and a one-parameter-changed capture, and by correlating
inline pointers to the printed resource VAs. All 40+ draws/dispatches returned `status=4`
(completed); **zero faults, zero reboots.**

## Claims under test
1. Indirect draw/dispatch: opcode `0x61c4→0x6404` (non-indexed) / `0x61f2→0x6432` (indexed);
   args-ptr @VDM +0x68(hi)/+0x6c(lo); indexed keeps idxVA inline @+0x70, args @+0x74/+0x78;
   indirect dispatch = 2nd CDM record + grid-setup helper, args staged @`0x10000080000+0xb0`.
   **Cross-check:** does RT-2a's indexed-record-shift (instanceCount@+0x78, u32 opcode 0x61f4)
   apply to the indirect-indexed form?
2. Full ICB: command-count @`0x18000+0x04`; per-command inline state+draw (same 0x61c4);
   mesh-in-ICB → `0x70000600`.
3. Occlusion query: result-buffer ptr @`0x10000100000+0x00`; mode bit14 @`0x58000+0x8c`;
   offset @`+0xa0 = byteOffset<<14`.
4. Timestamps: u64 ns / period 1.0 / stage-boundary-only.
5. Geometry-output: multi-viewport array @`0x68000+0x900` (count word, 0x18-byte stride);
   clip mask @`0x58000+0x20` bits[7:0]; point_size bit18; viewport-idx bit19; primitive-restart
   cut index @`0x18000+0x68`.

## Adversarial cases added
- Indexed indirect draw (the RT-2a cross-check); multiple indirect draws in one pass.
- ICB execute-range **subset** (`executeCommandsInBuffer:withRange:` a proper sub-range).
- **Mixed** draw+mesh ICB (`commandTypes = Draw | DrawMeshThreadgroups`).
- Occlusion: counting vs boolean, two queries, **large** offset (4096).
- Timestamps: compute dispatch-boundary sampling (confirm zero/unsupported).
- Geometry: 16 viewports, 8 clip planes, restart with strips (u16 & u32), `[[viewport_array_index]]`.

## Files
- `harness/icbx.m` — ICB adversarial harness (execute-range subset + mixed draw/mesh). **new.**
- `harness/midraw.m` — multiple indirect draws in one render pass. **new.**
- `harness/hexreg.py`, `harness/opscan.py` — BO region dumper / opcode scanner. **new.**
- `harness/gen_evidence.sh` — regenerates `raw/RAW_EVIDENCE.txt` from the captures.
- Reused (RT-6 rebuilt them arm64e in `~/cleanroom_work/rt6/`, unchanged sources): `ivar.m`
  (EXP-0027 indirect), `qvar.m` (EXP-0027 occlusion), `tvar.m` (EXP-0027 timestamp),
  `ovar.m` (EXP-O2A geometry-output), `micb.m` (EXP-O2G mesh-in-ICB), plus `tools/iotrace`,
  `bodiff.py`, `dumpscan.py`.
- `raw/RAW_EVIDENCE.txt` — consolidated field dumps for every claim (primary evidence).
- `raw/hex/curated_regions.txt` — curated VDM/CDM/state hex regions for the load-bearing cases.

## Verdict
**All 5 claim groups CONFIRMED. Zero discrepancies.** See `RESULTS.md`. Two positive adversarial
extensions (mixed draw+mesh ICB is accepted; multiple indirect draws each emit their own 0x6404
record) and one clarification (ICB `+0x04` is the *encoded* command count, independent of the
execute range) — none contradict the docs.
