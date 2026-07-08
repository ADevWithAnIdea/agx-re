# EXP-M4-09 — cmdstream / pipeline coverage closure (CMD-1..CMD-8)

**Goal:** close the cmdstream/pipeline parameter-coverage gaps CMD-1..CMD-8 from
`reviews/COVERAGE-GAPS-01.md` §4 — rules that were validated at one or two points of a
parameter space and then stated for the whole space.

**Primary device:** LOCAL **Apple M4** (Mac16,10, 10-core GPU, Metal 4 / Apple9). Captures
run directly on this host. A18 (G17P) cross-confirmation is done by the orchestrator for any
CORRECTION; the M4 layout matched the A18-derived docs byte-for-byte on every gap here (all
CONFIRM), so no A18 correction was required.

**Clean-room category:** DATA-TRACE (iotrace IOKit interposer over our OWN Metal programs) +
OWN-SHADER + HW-PROBE. No Apple binary disassembled. **CMD-1 note:** blend factor/op is
lowered into the fragment-shader blend microprogram, which is compiler-generated code and is
**deliberately NOT disassembled** (CLAUDE.md rule 5). We decode only the traceable `0x58000`
state-pool bytes; the FS code BO (`0x10000000000`) is touched only to *count* how many words
change (a classification signal — state-only vs FS-rewrite), never to interpret instructions.

## Method
Reuses the RT-2a / EXP-0019 / EXP-0021 / EXP-0027 harnesses (`svar.m`, `mrtvar.m`, `ovar.m`,
`qvar.m`) + `tools/iotrace -arch arm64e` + `bodiff.py`. New harness `dvar4.m` adds the u32-index
+ baseVertex/baseInstance draw forms so the u32 path (opcode `0x61f4`, previously inferred) is
actually RUN. Each gap: change-one-parameter sweep → capture registered BOs → `bodiff` the
relevant control BO → decode the field. Every dispatch confirmed `status=4` (GPU-completed).

## Layout
- `harness/` — copied + extended harnesses, build/sweep scripts, `b_caps/` `d_caps/` `o_caps/`
  (text hex captures), `b_an/` `d_an/` `o_an/` (diffs/analysis). Owned by the CMD-1/4/5 work.
- `cmd2-stencil/`, `cmd3-mrt/`, `cmd7-msaa-query-ts/`, `cmd8-tg-occupancy/` — one subdir per
  gap run by a dispatched subagent (M4-only sweeps + decode).
- `RESULTS.md` — consolidated findings + CONFIRM/CORRECT verdict per gap.

## Gaps & owners
| gap | topic | driver |
|---|---|---|
| CMD-1 | Blend STATE-POOL side across all 19 factors × 5 ops + dual-source | `harness/cmd1_blend.sh` |
| CMD-2 | Stencil ops 0–7 on all three fields | `cmd2-stencil/` |
| CMD-3 | MRT 5–8 attachments + mixed formats | `cmd3-mrt/` |
| CMD-4 | Primitive × index-type × instanced matrix (RUN u32 index) | `harness/cmd4_draw.sh` |
| CMD-5 | Multi-viewport/clip to max + restart comparand | `harness/*` (ovar) |
| CMD-7 | MSAA 8× reject / occlusion offset / timestamp breadth | `cmd7-msaa-query-ts/` |
| CMD-8 | Threadgroup rounding + occupancy tier GPR flip | `cmd8-tg-occupancy/` |

(CMD-6 = firmware/kernel-managed submit params; out of userspace scope, not addressed here.)
