# RT-2a — Red-team falsification of the command-stream field maps

**Role:** adversarial verifier. Assume `docs/cmdstream/README.md` field offsets/values may be
subtly wrong. Run change-one-Metal-parameter + byte-diff tests **designed to break the claims**,
plus large/unorthodox programs (MRT×4/8, 16 viewports, huge/0 counts, base-vertex/instance,
mismatched bind counts). Report discrepancies with evidence. **Does not edit `docs/` or tools.**

**Clean-room category:** DATA-TRACE + OWN-SHADER. Every shader is our own MSL compiled at runtime
(`newLibraryWithSource:`). We byte-trace the command buffers/descriptors our own Metal process hands
the kernel via the `tools/iotrace` DYLD interposer (built `-arch arm64e`). No Apple binary is
disassembled. Command buffers / descriptors are non-copyrightable hardware data.

## Claims under test (docs/cmdstream/README.md)
1. **CDM compute launch descriptor** (0x100000b0000, 0x2c-byte record): shader ptr = shaderVA>>6 @+0x08;
   grid xyz @+0x10.. in *threads*; threadgroup xyz @+0x1c..; tgmem not here; config word @+0x00.
2. **VDM draw record** (0x18000): primitive @+0x65, vertexCount @+0x68, instanceCount @+0x6c;
   indexed opcode 0x61c4→0x61f2 + index-buf VA @+0x70.
3. **USC bind grammar** (arg buffer 0x10000248000): 2-ptr header; num_tex=(samp−tex)/0x20;
   num_samp=(term−samp)/8; buffers → 0x10000100000+0xa0.
4. **State packets** (0x58000): depth +0x38, stencil +0x3c, raster +0x70, PPP output-select +0x20;
   PPP header = monotone length word (+0x400 on depth/stencil append).
5. **Programmable blend:** a blend factor/op change rewrites the fragment shader, not a state packet.

## Method
Reuse the *exact* parametric harnesses that produced the claims (`cvar` EXP-0011, `dvar`/`dvar2`
EXP-0014, `svar` EXP-0019, `uvar` EXP-G1a, `ovar` EXP-O2A) driven with **adversarial inputs they were
never run with**, plus two new harnesses (`dvar2` = base-vertex/base-instance/vertexStart draws;
`mrtvar` = 1..8 render targets). For each variant: capture every registered GPU BO under the
interposer (`--dump` → SIGUSR1 snapshot), then `bodiff.py` word-diff by GPU VA / dedicated readers
(`cdmread.py`, `uscread2.py`) to localise each field.

Device: `user@192.168.170.254`, A18 Pro / G17P, macOS 26.6 (25G5043d). Workspace `~/cleanroom_work/rt2a/`.
All draws/dispatches completed (status=4); no GPU faults/reboots.

## Layout
- `harness/` — harnesses (`*.m`), drivers (`phase*.sh`), readers (`cdmread.py`, `uscread2.py`, `uscread.py`), tool copies.
- `raw/analysis{A,B,D}/` — `bodiff.py` word-diffs per variant.
- `raw/hex{A,B,C,D}/` — curated hexdumps of the key control BOs.
- `raw/raw_summ/` — CDM threadgroup probe table, USC stride sweep, viewport count outputs.
- `RESULTS.md` — per-claim verdict (CONFIRMED / DISCREPANCY) with evidence.

## Phases
| script | claim | what it stresses |
|---|---|---|
| `phaseA_cdm.sh` + `phaseA2_tg.sh` | 1 | non-cube 3×5×7, grid>tg, 1D/3D, huge 0x123456, tgmem 256..32768, threads-vs-groups equivalence, 2-pipeline, config word |
| `phaseB_vdm.sh` | 2 | all prims, inst 7/256/huge, vertexCount 6/99/huge/0, indexed u16/u32, vertexStart, base-vertex, base-instance, idx offset |
| `phaseC_usc.sh` + `phaseC2_stride.sh` | 3 | 8tex+4samp+4buf, mismatched (3t1s,1t3s,4t0s), buffers-only, texture/sampler stride sweep |
| `phaseD_state.sh` | 4,5 | all depth/stencil compare+op, per-face, raster, PPP length word, output-select, MRT 1/2/4/8, blend factor/op + dual-source |
| `phaseE_final.sh` | 1,2,4 | true 0-vertex, clean base-instance isolation, indexed+instanced+basevert combo, 16-viewport count word |
