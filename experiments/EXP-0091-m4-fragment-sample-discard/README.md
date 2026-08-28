# EXP-0091 — M4 fragment sample/coverage/discard/demote/helper state machine

**Bundle A** of the OpenGL-addendum triage (`work/ADDENDUM-TRIAGE-20260828.md`). Closes
addendum items **GLFS-A01, GLFS-A02, GLFS-A03, GLFS-A05, GLFS-A06, GLFS-A07**
(`APPLE9_RE_OPENGL_TEXTURE_ADDENDUM.md`) and primary-list item **OPT-09**
(`APPLE9_RE_IMPLEMENTATION_GAPS.md:501-505`).

**Question:** what Apple9 instruction (if any) kills fragment samples and submits
coverage; does `discard_fragment()` have SPIR-V demote semantics (helper lanes keep
executing for derivatives/implicit-LOD); which side effects does a demoted/helper lane
automatically suppress; how do early/late depth-stencil tests order against discard;
and how does per-sample shading actually launch invocations on real M4 hardware.

**Method:** own-shader differential compilation to locate candidate encodings
(`kernels/loc_*.metal`), HW splice-and-observe validation with a triple independent
channel (color + fixed-function depth + hardware occlusion count) for the located
kill/mask-submission op, and ordinary compiled-and-executed render probes (no splice
needed) for the demote/helper/depth-ordering/sample-shading behavioral questions, using
an authored render+readback harness (`harness/fsrun.m`, a superset of the read-only
`tools/agxtest/agxrender.m`: MSAA sample counts, depth attachment+compare, occlusion
query, N device buffers, checker textures — all needed capabilities `agxrender.m`
doesn't have and which this experiment does not modify).

**Clean-room category:** OWN-SHADER (every inspected/spliced byte is our own compiled
MSL) + HW-PROBE (device execution/readback) + PUBLIC (one MSL-spec-surface check, §6
of RESULTS.md, for the MinSampleShading-absence finding).

## Layout

```
PRE_REGISTRATION.md   frozen hypotheses (H1-H7), exact addendum wording quoted, case
                       matrix reference, pilot findings that informed the freeze
CAPTURE_CONTRACT.json machine-readable freeze: hashes, schema, timeouts, gate classes
RESULTS.md             per-item response blocks (GLFS-A01/02/03/05/06/07 + OPT-09),
                       exact numbers, verdicts, clean-room attestation
PROGRESS.md            timestamped milestones
schema.py               ONE shared gated/non-gated record key-set (imported by run.py
                       and verify.py -- never restated)
run.py                  the frozen 78-case matrix + runner (compile_scan and
                       gpu_render case kinds)
verify.py               --selftest / --seqtest / --smoke / --crossrun (standing gate set)
harness/fsrun.m         authored render+readback tool (plain compile OR archive+splice
                       modes; MSAA/depth/occlusion/buffers/textures)
kernels/*.metal         30 authored MSL probes (loc_*, s_kill_probe, d_*, e_*, g6_*, f_*)
analysis/gen_e_kernels.py  generator for the 6 GLFS-A05 depth-ordering kernel variants
analysis/scan57.py      standalone byte-scan helper used during pilot localization
raw/m4_20260827_run01/  first frozen capture (78 gated+78 nongated JSON records)
raw/m4_20260827_run02/  second frozen capture (byte-identical gated records, verified)
raw/supplementary_single_run/  ONE post-freeze supplementary probe (d_helper_relay),
                       explicitly flagged as NOT part of the two-run gate
work/                   regeneratable build scratch: work/bin (compiled shdump/fsrun),
                       work/archives (*.bin Metal binary archives from shdump --
                       compiled outputs of our own MSL, not committed evidence in the
                       usual convention, kept here as regeneratable build cache),
                       work/hex (extracted fragment-main hex, duplicates the
                       frag_main_hex field already embedded in raw/loc_*.gated.json),
                       work/pre_reg_hashes.txt (hash manifest referenced by
                       PRE_REGISTRATION.md), work/trial/ (the pilot capture --
                       IMPORTANT, referenced at runtime by verify.py's
                       load_pilot_shapes() as the gate-class-(e) "recorded reality"
                       fixture source; do not delete)
```

## Reproduce

```sh
cd experiments/EXP-0091-m4-fragment-sample-discard
xcrun clang -fobjc-arc -o work/bin/shdump tools/shdump/shdump.m -framework Metal -framework Foundation   # (path adjusted; see PROGRESS.md for exact commands used)
xcrun clang -fobjc-arc -o work/bin/fsrun harness/fsrun.m -framework Metal -framework Foundation
python3 verify.py --smoke                                    # before any raw/ exists
python3 run.py --run run01 --out raw/m4_<date>_run01
python3 run.py --run run02 --out raw/m4_<date>_run02
python3 verify.py --crossrun raw/m4_<date>_run01 raw/m4_<date>_run02
python3 verify.py --selftest
python3 verify.py --seqtest
```

## Headline findings (see RESULTS.md for full response blocks and evidence)

- **GLFS-A01:** a dedicated 6-byte submission op (`byte0=0x57`, `byte2=0x54`) + 6-byte
  companion (`byte0=0x07,byte1=0x02,byte2=0x54,byte3=0x01`) exists, is present if and
  only if the source calls `discard_fragment()` or writes `[[sample_mask]]`, and is
  register-sourced (splice-validated: byte+4 bits[4:0] = source-register-select,
  HW-VALIDATED via a 3-channel color+depth+occlusion readout). Mask width is exactly N
  = rasterSampleCount (N∈{1,2,4}); excess bits are silently inert, never faulting.
  Currently mis-tokenized in `tools/agx-isa/db.json` as an 8-byte vertex-stage
  `vary_store` — a fragment/vertex opcode-byte collision, flagged for correction.
- **GLFS-A02 / OPT-09:** **Yes**, Apple9 discard has SPIR-V demote semantics on M4. A
  demoted lane provably continues executing ALU (a neighbor's `fwidth()` reads exactly
  `999.0`, matching a post-discard `+1000` mutation), is retrievable via
  `quad_shuffle_xor` with its own live post-discard register value, and its
  continued participation measurably changes a surviving neighbor's implicit-LOD
  texture sample.
- **GLFS-A03:** helper status flips true immediately upon a lane's own discard (relayed
  via quad-shuffle since the lane's own write is suppressed); the pre-discard read is
  not spatially uniform in one supplementary single-run probe — flagged PARTIAL/OPEN.
- **GLFS-A05:** ordinary and shader-depth-output testing are LATE (shader always
  launches); `[[early_fragment_tests]]` is EARLY (shader launch itself is skipped for
  the depth-fail region, `ran=0/32`). A later discard undoes an already-passing
  occlusion contribution under LATE testing but NOT under EARLY testing — a concrete,
  previously-undocumented ordering fact.
- **GLFS-A06:** device buffer store, atomic increment, color output, and depth output
  are ALL automatically, completely suppressed from a demoted lane — no compiler
  predication required for any of the four tested channels.
- **GLFS-A07:** per-sample shading launches exactly one invocation per covered
  `(pixel,sample)`; per-pixel (no `[[sample_id]]`) shading still re-executes N times per
  pixel at sample count N (no broadcast fast path observed). Metal exposes no
  MinSampleShading-style fractional rate at all.

All findings are M4/G16G only; A18 Pro/G17P is `INFERRED`-by-family per target
discipline, not independently validated.
