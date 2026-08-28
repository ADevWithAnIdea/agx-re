# EXP-0129 Progress Log

## Milestone: pre-registration frozen

Read `CLAUDE.md`, `CODEX.md`, `experiments/SUBAGENT_BRIEF.md`, and the two
prerequisite RESULTS.md (EXP-0109, EXP-0117) plus EXP-0111/EXP-0097 for
context. Confirmed via `docs/isa/encoding-tables.md` that the `iter`
instruction family already documents perspective-correct interpolation as
a MULTI-instruction lowering (linear component + W-denominator + `fspecial`
rcp + fmul) — this became the concrete H1c mechanism hypothesis.

Extensive PILOT exploration was done under `work/scratch_debug/` (never
`raw/`) before freezing: built `harness/struct_extract.m`,
`harness/struct_extract_vonly.m`, `harness/render.m`,
`harness/compute_callret.m`, `analysis/isahelper.py`, and every
`kernels/*.metal` file, then manually ran each through the real M4 to
confirm the shapes actually compile, render, and disassemble as intended
BEFORE committing to the frozen case matrix in `casematrix.py`. This
surfaced and fixed two real pilot bugs (both disclosed, not silently
fixed):

1. `f_count3_vary`'s original draft used a bare `float4 vtag
   [[user(locn0)]]` FRAGMENT PARAMETER (not wrapped in a `[[stage_in]]`
   struct). It compiled with NO error, but the value silently failed to
   connect to the vertex shader's output — readback was exactly the
   render pass's clear color, not the interpolated vertex data. Confirmed
   via a dedicated isolated probe (`work/scratch_debug/vtagcheck.metal` vs
   `vtagcheck2.metal`): wrapping the SAME field in a
   `struct FSInExtra { float4 vtag [[user(locn0)]]; }` consumed via
   `FSInExtra in [[stage_in]]` fixes it (own-compiler finding: MSL
   requires `[[stage_in]]` for a plain user varying; true builtins
   `[[barycentric_coord]]`/`[[position]]` are exempt). `kernels/bary.metal`
   was fixed to the `[[stage_in]]` form before freezing.
2. `harness/render.m`'s `splitprolog` mode originally built a
   `rasterizationEnabled=NO` pipeline but the vertex function
   (`v_split_prolog`) returned a non-void struct — Metal rejected this
   ("RasterizationEnabled is false but the vertex shader's return type is
   not void", own-compiler diagnostic). Fixed by making `v_split_prolog`
   `vertex void` and mirroring EXP-0109's `rp.renderTargetWidth = 1;
   rp.renderTargetHeight = 1; rp.defaultRasterSampleCount = 1;`
   render-pass pattern (no color attachment at all) instead of a
   throwaway dummy texture.

**A major structural discovery during pilot, load-bearing for H2** (full
detail deferred to RESULTS.md): `tools/shdump/shdump.m`'s `--render` mode
only configures `colorAttachments[0]` — ONE attachment — regardless of how
many outputs the fragment function declares. Using it directly to extract
multi-output bary variants (`f_pos3`, `f_count3_const`, etc.) silently
produced WRONG structural bytes (attachments 1/2 have no bound format, so
the compiler dead-store-eliminates writes to them — `f_base` (2 outputs)
and `f_count3_const` (3 outputs) came back BYTE-IDENTICAL, which would
have been a false "count doesn't matter" structural non-finding). This is
why `harness/struct_extract.m` (this experiment's own, adapted from
EXP-0117's, generalized to a `--natt` CLI flag) is used for ALL bary
structural cases instead of raw `shdump.m` — `shdump.m` remains used
correctly, unmodified, only for the genuinely single-attachment-shaped
`split_callret.metal` compute kernel.

**A second major structural discovery, load-bearing for H2**: contrary to
a literal reading of EXP-0109 §5.1 ("No third region ever appears"),
`kernels/split_prolog.metal`'s `fetch_attr` (called once) and
`kernels/split_callret.metal`'s `mk4` (called twice) BOTH compile to a
genuinely separate, out-of-line Mach-O local symbol (`l__Z10fetch_attrP...`
/ `l__Z3mk4fffff`) distinct from `_agc.main`, reached via a real `call`
instruction (`tools/agx-isa`'s `call` descriptor: byte0=0x0f,
byte1=0x05, byte4=0x8f). `kernels/split_epilog.metal`'s
`do_blend_epilog` (called ONCE, from a FRAGMENT entry point), by contrast,
gets INLINED despite an identical `[[clang::noinline]]` attribute (also
re-tested with the exact `static ... __attribute__((noinline))` spelling
EXP-0109/EXP-0117 used successfully elsewhere — same result, inlined) —
confirmed via `isadb.disassemble()` showing the would-be call site decodes
as a 4-byte `if_push`, not the 14-byte `call` (byte+4 was `0x87`, not the
required `0x8f`). This is disclosed as an observed fact (Apple's own
compiler's inlining heuristic is not simply "count>=2" or "stage==vertex")
without claiming to explain WHY — flagged out of scope per
`PRE_REGISTRATION.md`.

Both pilot findings are DISCLOSED here (not silently smoothed over) per
this project's standing practice (EXP-0109's H7/H9, EXP-0117's blend/bary
corrections).

`harness/fixtures/recorded_reality.json` built from 2 REAL M4 GPU/compiler
calls (`barystruct_base`, `baryrender_base`) made via the FINAL, frozen
backends. `verify.py --selftest` (11/11) and `--seqtest` (3/3) both PASS
with zero `raw/` captures present.

Frozen: `PRE_REGISTRATION.md`, `CAPTURE_CONTRACT.json` (state `PRE_GPU`,
git revision `6987e19ee2ca1c6b8b4816e1ad568882edd8a858`, 17 authored files,
29 frozen cases).

## Milestone: two official captures complete, all gates green

`python3 run.py --run m4-20260828-run01 --out raw/m4-20260828-run01` and
`--run m4-20260828-run02` (separate process invocations): 29/29 `OK` each.
`python3 verify.py --crossrun raw/m4-20260828-run01 raw/m4-20260828-run02`
→ 29/29 byte-identical, 0 mismatches. `verify.py --selftest` (11/11) and
`--seqtest` (3/3) both re-run and still PASS post-capture. All 17
authored-file sha256 hashes verified unchanged from `PRE_GPU` freeze
through this point. `CAPTURE_CONTRACT.json` updated to state
`RUN02_PRESENT`.

`analysis/decode.py` run against `raw/m4-20260828-run01`: H1's full
discrimination table and both CONFIG1/CONFIG2 model fits confirm the
pre-registered H1a/H1b/H1c/H1d hypotheses exactly as predicted (position-
consumption is the trigger, not count, not any-varying, not harness;
`Model B`/`Model C` cleanly separate baseline vs. position-touching cases
in both geometries). H2's epilog/prolog/callret/negctrl checks all pass
(`all match: True` for every group). `RESULTS.md` written with the full
per-item verdicts, discriminating evidence, driver contract, OBSERVED vs.
INTERPRETED split, and P0.8 nine-item status table.

No BLOCKED state entered. No host wedge, reboot, or `macvdmtool` use at
any point. No excursion outside the repository.
