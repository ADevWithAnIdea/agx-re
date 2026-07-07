# EXP-0014: graphics/draw command stream — first pass

- **Date:** 2026-07-06
- **Clean-room category:** DATA-TRACE (+ OWN-SHADER for shader-code identification)
- **Phase / question:** Phase 2 (control/command stream) — the graphics follow-up to
  EXP-0011 (compute CDM). ROADMAP: VDM/tiler/fragment control words + pipeline/state packets.
- **Device state:** Apple A18 Pro / G17P, SoC T8140, macOS 26.6 (25G5043d), 5 GPU cores,
  Metal 4 / Apple9. Command Line Tools only (runtime MSL compile). No boot-args changes.

## Hypothesis
A Metal draw uses the same shared-memory+doorbell submission path as compute (EXP-0009), but
builds a graphics control stream with distinct structures for the two G17P graphics channels:
a **tiler (TA)** command list (vertex/primitive work) and a **fragment (3D)** command list
(render-target/attachment + fragment work). We expect to locate: draw-parameter fields
(vertex/index count, primitive type, instances), viewport/scissor/RT descriptor + clear/format,
fixed-function state pointers, and how the vertex+fragment shaders are referenced (is it
compute's `shaderVA>>6`, or two pointers?).

## Method (why it is clean-room legal)
**DATA-TRACE.** We run our **own** minimal Metal triangle draw under the `iotrace` DYLD
interposer and snapshot the *registered GPU buffer objects* (command buffers / descriptors) —
non-copyrightable hardware data crossing the userspace↔kernel boundary. We change exactly one
Metal parameter at a time and byte-diff the snapshots (`bodiff.py`) to localise each field, and
reconstruct the pointer graph (`bograph.py`). Shader-*code* BOs are identified by the AGX
constant-program stub validated against **our own** `shdump` output in EXP-0011 (OWN-SHADER).
No Apple binary is disassembled or introspected.

## Procedure (reproducible)
On the device under `~/cleanroom_work/exp0014/` (files: `dvar.m`, `iotrace.c`,
`iohello_compute.m`, `bodiff.py`, `bograph.py`, `dumpscan.py`, `run.sh`, `cdiff.sh`,
`shptr.py`, `curate.sh`):

```sh
sh run.sh          # build + capture the change-one-parameter matrix + on-device analysis
sh cdiff.sh <label...>   # control-plane-only diffs vs base for the given capture labels
sh curate.sh       # produce curated/key_diffs.txt + trimmed control-BO hexdumps
```

`dvar.m` flags: `--w/--h` (RT size), `--vpw/--vph` (viewport), `--verts`, `--prim
tri|strip|line|linestrip|point`, `--inst`, `--indexed`, `--fmt bgra8|rgba8|rgba16f|rgba32f|r8`,
`--cr/--cg/--cb/--ca` (clear), `--blend`, `--depth`, `--vshader/--fshader small|big`, `--two`,
`--dump`. The render target is buffer-backed so its GPU VA is printable for correlation.

## Raw results
See `raw/`:
- `raw/analysis/` — per-capture BO inventories (`list_*`), pointer graphs (`graph_*`),
  full BO diffs vs base (`diff_*`), selector histogram (`selhist.txt`).
- `raw/hexdumps/` — `key_diffs.txt` (curated one-parameter diffs), `vdm_two_second_draw.txt`,
  and trimmed raw hex of the key control BOs (`base_lo_18000/58000/68000.hex`,
  `base_3d_attachment_110000.hex`, `base_usc_130000.hex`, `base_vtxtable_100000.hex`).
- `raw/stdouts/` — each capture's printed CONFIG + resource GPU VAs.
- `raw/base.trace`, `raw/compute.trace` — IOKit call/selector sequences.

Key observations are summarised in **`RESULTS.md`**.

## Analysis
See `RESULTS.md`. Established (HW-clean, zero noise floor): the draw BO set and TA/3D split;
the VDM/tiler draw-command framing with primitive-type / vertex-count / instance-count / index
fields; the viewport transform floats + depth range; the 3D attachment descriptor's pixel
format + clear color; the fixed-function state pool location with per-state (raster/depth/blend)
field offsets; and the shader-code + USC-binding BO identities. Draw references shaders
*indirectly* (USC bind pairs), not via compute's single `shaderVA>>6` word.

## Established facts → docs
- Graphics command-stream framing + field locations → `docs/cmdstream/` (graphics section);
  add provenance rows (DATA-TRACE, EXP-0014) to `PROVENANCE.md`. (Orchestrator owns docs.)

## Follow-ups
See `RESULTS.md` §7: shader-entry word isolation; USC bind-pair grammar + per-packet bit
decode; attachment dims/stride; tiler parameter buffer; ZLS / partial-render.
