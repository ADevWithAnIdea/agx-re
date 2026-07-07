# EXP-O2H: tessellation — native HW tessellator, mesh-path, or compute-emulated?

- **Date:** 2026-07-07
- **Clean-room category:** DATA-TRACE + OWN-SHADER
- **Phase / question:** objective-2 residue O2-H — the last Metal-exposed geometry-pipeline stage not
  independently probed on A18. `docs/capability-matrix.md` §2 currently *assumes* tessellation is
  **emulate** (carried from the M1/M2 default); §4 lists "GS/tessellation/XFB A18-native status" as an
  open probe. `docs/porting-guide.md` §7/§8. This experiment decides it.
- **Device:** Apple A18 Pro / G17P, macOS 26.6 (25G5043d), SIP off. Command Line Tools only (runtime MSL).

## Hypothesis
Metal exposes tessellation on Apple9 via `drawPatches:` + a tessellation-factor buffer + a
**post-tessellation vertex function** (`[[patch(triangle|quad, N)]]`). Either (a) Metal lowers it to a
**compute pre-pass** (a CDM launch descriptor running a tessellator that generates domain vertices) + a
regular VDM draw — the Asahi M1/M2 model, in which case A18 has no native tessellator and a Mesa driver
must emulate; or (b) it reuses a **graphics/tiler-path stage** (like the mesh grid-dispatch record
`0x70000600`, EXP-0030) — a native path; or (c) a dedicated new work type. The discriminator is whether
`drawPatches` **alone** (no user compute encoder) causes a compute (CDM) launch descriptor BO to appear.

## Method
Change-one-Metal-parameter DATA-TRACE + OWN-SHADER, the exact method of EXP-0030 (mesh):
1. Build a minimal, canonical Metal tessellation pipeline from **our own MSL** (`kernels/tess.metal`):
   a compute kernel that writes per-patch half tessellation factors, a post-tessellation vertex function
   (`[[patch(triangle,3)]]` / `[[patch(quad,4)]]`) consuming `[[position_in_patch]]` + patch control
   points, and a fragment shader. Render it and **HW-validate** the readback (coverage + a bulge
   displacement whose silhouette must grow with the tessellation level — proves subdivision ran).
2. Trace the submission with the read-only `iotrace` interposer (built `-arch arm64e`). The crux is a
   **`--cpu-factors`** mode: the CPU writes the factor buffer so there is **no user compute encoder** —
   then any CDM launch descriptor in the trace is `drawPatches`'s own tessellator.
3. Enumerate the registered BOs (`dumpscan --list`), diff the VDM/tiler record at `0x18000` against a
   plain draw and against the tri/quad/level/partition variants (`bodiff`), decode the tessellation-factor
   buffer, and census the post-tessellation vertex shader's opcodes (our own compiled bytes).
Clean-room-legal: our own MSL, our own draws; logging non-copyrightable command-buffer/descriptor bytes;
Metal-generated tessellator/helper code is **located, never disassembled** (CLAUDE.md rule 5).

## Procedure
```sh
# on host: stage harness + read-only tools onto the device (tools used verbatim from tools/)
cp tools/iotrace/{iotrace.c,bodiff.py,bograph.py,dumpscan.py,iohello_draw.m,iohello_compute.m} \
   tools/shdump/agxparse.py experiments/EXP-O2H-tessellation/harness/
scp experiments/EXP-O2H-tessellation/harness/* experiments/EXP-O2H-tessellation/kernels/tess.metal \
    experiments/EXP-O2H-tessellation/run.sh  user@DEVICE:~/cleanroom_work/exp_o2h/
# on device:
cd ~/cleanroom_work/exp_o2h && sh run.sh     # builds, captures baselines + tess variants, diffs, censuses
# pull back text diffs + curated hex + own-shader hex only (raw BO dumps stay on-device)
scp -r user@DEVICE:~/cleanroom_work/exp_o2h/{analysis,hex,code} .../raw/
```
`tess.m` flags: `--patch tri|quad`, `--level F`, `--bulge F` (subdivision proof), `--cpu-factors`
(no compute encoder — the crux), `--partition int|pow2|fo|fe`, `--w/--h`, `--iters N`, `--dump`.

## Raw results
- `raw/analysis/bo_inventory.txt`, `bo_vaset.txt` — full registered-BO inventory per capture (draw /
  compute / tess_cpu / tess_comp / tess_q_cpu). **The deciding evidence.**
- `raw/analysis/callcounts.txt` — IOKit call counts (draw 58, compute 49, tess_cpu **62**, tess_comp 66).
- `raw/analysis/vdm_*` — VDM `0x18000` record diffs (draw-vs-tess, tri-vs-quad, cpu-vs-comp).
- `raw/analysis/factorbuf.txt`, `factordiff_*` — tessellation-factor buffer format (half floats).
- `raw/analysis/part_*` — partition-mode localization.
- `raw/hex/*_18000.hex` — the raw patch-draw VDM records.
- `raw/code/tess_*_report.txt`, `*_vertex.hex`, `*_fragment.hex` — our own compiled post-tess VS bytes.
- `raw/stdout/*` — per-capture logs (all `status=4`, `STATUS OK`, zero faults/reboots).

## Analysis
See **`RESULTS.md`**. Verdict: **A18 implements tessellation as a native graphics/tiler-path stage — NOT
a compute pre-pass, NOT the mesh record** (drawPatches with CPU-written factors registers the *same BO
set as a plain draw*, with **no CDM launch descriptor**); it uses a distinct VDM patch-dispatch record
(opcode high-byte `0x40`) carrying the patch domain type (`+0x8c`: tri=1/quad=2) and a packed config word
(`+0x68`: control-point count + partition mode). Factors are IEEE half-floats. The post-tessellation
vertex function is an ordinary vertex shader (no novel opcode). This **revises** `capability-matrix.md` §2
(tessellation "emulate") to a native tiler-path stage, structurally analogous to mesh shading.

## Established facts → docs
- Tessellation = native tiler-path stage (no CDM) → `docs/capability-matrix.md` §2/§4, `docs/cmdstream/`,
  `docs/porting-guide.md` §7/§8 → add rows to `PROVENANCE.md`. (Orchestrator owns docs.)

## Follow-ups
- Full bit-decomposition of the `+0x68` packed patch-config word (single-variable matrix over
  cp-count × partition × winding); exact tessellation-factor-buffer pointer field in the VDM record.
- How the post-tess VS receives `[[position_in_patch]]` (get_sr vs firmware-buffer load) — needs the
  vertex-stage tokenizer (shared with mesh follow-ups).
- Isoline patches; `drawIndexedPatches`; `tessellationFactorStepFunction perPatch/perInstance`;
  factor-buffer instanceStride; `maxTessellationFactor` 64 cap; whether the domain-point generator is
  hardened silicon vs firmware microcode (below the userspace boundary — a kernel-interface item).
