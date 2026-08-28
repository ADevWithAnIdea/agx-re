# PRE_REGISTRATION — EXP-0114 m4-texture-deferred

Pinned revision (frozen at pre-registration; do NOT gate on live `HEAD`): see
`CAPTURE_CONTRACT.json`'s `pinned_git_revision`. Per `SUBAGENT_BRIEF.md`, this experiment gates
captures on the **authored blob hashes** recorded in `CAPTURE_CONTRACT.json`, not on `HEAD` or
tree cleanliness — the orchestrator commits other experiments concurrently.

Target: **local Apple M4 (G16G) only**, macOS 26.6.2, arm64, Metal 4. A18 Pro/G17P is hands-off
(no data collected here). Boundary: OWN-SHADER MSL compiled via `newLibraryWithSource:`
(`tools/shdump`), our own Mach-O/Metal-fat container parsing (`agxparse.py`, PUBLIC container
format, not Apple code), our own byte-splice-and-dispatch harnesses
(`harness/texsplice.m`, `harness/gradsplice.m`, modeled on the proven `tools/agxtest`/
EXP-0016/EXP-0094 splice-and-reload technique, independently authored for this experiment).
`tools/*` used strictly READ-ONLY (invoked as external processes; never edited).

## 0. Scope: the dispatched item set and cover/defer decision

The dispatch names 11 items: TEX-01, TEX-12, TEX-15, TEX-19, TEX-20, TEX-21, TEX-22, TEX-26,
TEX-27, TEX-28, the raw-descriptor-splice half of TEX-16, plus EXP-0094's OPEN gradient-operand
register field. Priority order given: **TEX-15 first, then TEX-16's splice half, then the
gradient field.** Per `CODEX.md` §10 / the dispatch's explicit permission, this contract freezes
a **coherent high-value subset** covering the three prioritized items with full CONSTRUCTION
(not just observation) evidence, and explicitly DEFERS the remaining eight with named successor
reasons — none silently dropped.

| item | decision | reason |
|---|---|---|
| **TEX-15** (selector field width, 0-127) | **COVERED** | Priority 1. See §1. |
| **TEX-16** (raw-descriptor-splice half) | **COVERED** (folded into TEX-15's construction sweep) | Priority 2. Same field, same splice apparatus — an out-of-population injection on the field IS the raw-descriptor-splice test. |
| EXP-0094 gradient-operand register field | **COVERED** | Priority 3. See §2. |
| TEX-01 (native `txp` projective-divide form) | **DEFER** | Needs `op+2` bit-space fuzzing on a spliced sampler bundle beyond every compiler-reachable value — a dedicated opcode-fuzzing campaign (EXP-0106's own successor spec, unchanged: no new evidence gathered here). Out of this contract's frozen construction work, which is scoped to the texture-slot and gradient-operand fields specifically. |
| TEX-12 (sparse-texel residency) | **DEFER** | Needs `MTLHeap`-backed sparse textures + `updateTextureMapping:` residency lifecycle — a materially larger, different harness (resource lifecycle, not a single dispatch) than anything else in this contract. EXP-0106's successor spec stands unchanged. |
| TEX-19/20 (bindless texture ceiling to 1,000,000 / behavior beyond) | **DEFER** | EXP-0095 already established the qualitative *shape* (silent zero, no aliasing, no mirroring) at `CAP=256`; confirming it holds at the documented 1,000,000 ceiling needs allocating/binding at that scale, a large campaign distinct in kind from this contract's byte-splice constructions. EXP-0106's successor spec (reuse EXP-0095's GLIMG-A02 methodology at boundary values near 1,000,000) stands unchanged. |
| TEX-21/22 (bindless sampler ceiling to 499,999 / 500,001st reuse) | **DEFER** | EXP-O2B's finding is A18-only (pre-dates the M4-only directive) and never swept the boundary. An M4 re-run at boundary values near 499,999 is a distinct, large-scale campaign (sampler-heap allocation at that count) outside this contract's byte-splice scope. EXP-0106's successor spec stands unchanged. |
| TEX-26/27/28 (raw sampler-descriptor field injection: anisotropy/max-LOD/address-border-swizzle codes) | **DEFER** | These need locating the **sampler**-side per-stage binding table for inline byte patching (the texture side was proven reachable in EXP-0016; EXP-M4-08 found the sampler side unreachable via the explicit-argument-buffer path specifically). This is a different table/mechanism from the AGX-instruction-level `op+4` register field this contract's Group A/B work characterizes — locating it is a `tools/iotrace`-based BO-capture investigation, not a shader-byte splice, and was not attempted here for time. EXP-0106's successor spec (locate the direct `[[sampler(n)]]` table analogous to EXP-0016's texture-table proof) stands unchanged. |

## 1. TEX-15 / TEX-16 — texture-read selector field (`op+4`) construction

### 1.0 Pre-freeze exploration finding that reframes the question

Pre-registration exploration (own-shader-diff on fresh, freely-authored 2/3/4/127-texture
`access::read` kernels, `work/` scratch, not committed as evidence) found that the AGX texture
"read" bundle's `op+4` byte (identified in EXP-0016 as "texture-slot ref, bit7 = tex-index bit")
is **not a stable per-resource identifier**. A 3-texture kernel that reads non-contiguously
declared textures `[[texture(5)]]`, `[[texture(50)]]`, `[[texture(100)]]` in that source order
compiles to `op+4` sequence `0x00, 0x80, 0x00` — the **compiler's own local register/uniform
allocator**, reusing a small slot as soon as its previous occupant is dead, not the literal MSL
binding index (which would predict `5, 50, 100`) and not even a stable compacted use-order index
(which would predict `0, 1, 2`, not `0, 1, 0`). A 4-concurrent-read kernel (each result to its own
output, no accumulation) shows the same 2-slot ping-pong: `0x00, 0x80, 0x00, 0x80`. This directly
falsifies the gap-doc's framing of TEX-15 as "decode which of 0-127 is encoded here" — the
compiler is reusing a REGISTER-LIKE slot, and the true per-texture 0-127 selector must live in a
**preceding pointer-materialization instruction** not yet decoded (exactly analogous to
EXP-0094's finding that the bias operand's real register-select lives in a preceding instruction,
not the sampler bundle itself).

Given this, this contract's TEX-15/16 construction work is **retargeted and precisely scoped**:
characterize `op+4` itself (its true bit width, which sub-bits matter, its legal/populated range
in a controlled program, and its failure mode outside that range) by CONSTRUCTION (splice, not
mere observation), while explicitly documenting — as a corrected, falsified premise, a first-class
negative result per `CODEX.md` — that `op+4` is not the field a driver should treat as "the
texture index." A successor spec for decoding the true preceding pointer-load instruction is
given in §3.

### 1.1 Hypothesis (falsifiable)

H1: `op+4`'s **upper nibble** (bits 7:4) is the operative register-slot field (16 possible values);
the **lower nibble** (bits 3:0) is inert/don't-care to the hardware. H0 (refuter): any lower-nibble
value, holding the upper nibble fixed, changes the observed dispatch output.

H2: in a minimal 2-live-texture kernel, exactly the two nibble values the compiler itself emits
(`0x0`→t0, `0x8`→t1) are "populated" (read back the correct bound texture); every other of the 14
nibble values reads back a **silent zero** (matching the project-wide silent-zero convention,
`docs/isa/register-move-and-liveness.md`), not a fault, not an alias to t0/t1, not garbage. H0
(refuter): any unpopulated nibble value produces a nonzero, non-t0/t1 result, a fault, or a
command-buffer hang.

H3 (positive control / detectability): splicing `op+4` between its two native values on either
bundle direction (t0-bundle→t1's value and t1-bundle→t0's value) reproducibly and bidirectionally
changes the dispatch's output word to the OTHER texture's canary — proves the splice mechanism
itself can detect a real change (required per dispatch: "give every null result a positive
control proving detectability").

Independent variable: the single spliced byte value (0x00-0xFF). Controlled: kernel source
(fixed 2-texture `access::read` sum kernel), bound texture contents (fixed, distinguishable
1x1 `r32uint` canaries `0x11111111`/`0x22222222`), dispatch shape (1 thread), fresh process per
case. Confounders considered: Metal's compiler recompiling per-process would defeat the splice —
avoided by loading the archive with `MTLPipelineOptionFailOnBinaryArchiveMiss`, the project's
standard proof technique (fails closed if the archive's own bytes aren't what ran); allocator
placement — irrelevant here since only a single already-compiled byte is touched, not a new
allocation.

### 1.2 Cases (frozen in `CAPTURE_CONTRACT.json`)

- **`diff_*` family (8 cases, compile-only, no GPU dispatch):** own-shader-diff census of the
  read-bundle `op+4` byte across N = 2, 4, 8, 16, 32, 64, 127 declared/used textures, plus the
  N=128-declared/3-used sparse/non-contiguous case. Deterministic; no splicing, no HW risk.
- **`splice_tex` family (31 cases, HW dispatch, each its own process):** on the HW-validated
  2-texture baseline (`kernels/read_n2.metal`): native control, bidirectional flip control, a
  full 16-value upper-nibble sweep (min legal 0x0, max representable 0xF, holes = the 14
  unpopulated values, first-invalid = any of them), and 12 low-nibble-invariance cases (6 values
  at the populated nibble-0 slot, 6 at nibble-8) confirming H1's "don't-care" claim across the
  representable low-nibble space, not just a single sample point.

## 2. EXP-0094 gradient-operand register field — cleaner differential design

EXP-0094 sec 3.3/3.6 HW-validated the **bias** operand's register-select byte via a minimal
varying-routed differential pair (2 named operands, one feeds `bias()`, the other is sunk into an
unused output channel; source-identical except which name feeds which role) — a clean 4-byte
diff, single-byte splice-validated. The analogous **gradient** attempt used a `constant float*`
buffer with `tid.x`-offset addressing and produced 116 differing bytes — not a clean isolate,
left OPEN.

### 2.1 Hypothesis

H4: routing `gradient2d()`'s two operand vectors (`dx`, `dy` — 4 scalar components total) through
**per-vertex-interpolated varyings** (the same mechanism that produced bias's clean isolate,
instead of a buffer+address-computation path) produces a small, systematic differential — NOT
necessarily as small as bias's 4 bytes (gradient carries 4x the scalar payload), but decomposable
into a small number of INDIVIDUALLY splice-provable causal byte positions, not a diffuse 116-byte
smear. H0 (refuter): the diff remains large (>50 bytes) or no single byte/small byte-set is
independently causal under splice.

H5: whichever byte offset(s) are found causal are **stable across different register-pressure
contexts** (a second differential pair with an inserted filler varying, shifting overall register
allocation) — i.e., a genuine encoding-position fact, not an artifact of one specific compiled
program's happenstance layout. H0 (refuter): the causal offset(s) differ between the two pairs.

Independent variable: which named varying (`gA`/`gB`) feeds `gradient2d()` vs. is sunk (dead) in
the fragment. Controlled: same texture (2-level, solid-color oracle: level0=red, level1=green,
nearest mip filter — a DISCRETE, unambiguous LOD readout, chosen over EXP-0094's continuous
LOD-recovery ramp because this experiment only needs "which operand won", not a precise LOD
value), same sampler, same render-pipeline shape, fresh process per case. `gA` is fixed to a tiny
gradient (selects level0) and `gB` to a huge one (selects level1) so the readback color
unambiguously reveals which operand the hardware actually used.

### 2.2 Cases (frozen in `CAPTURE_CONTRACT.json`)

Pre-freeze exploration (own-shader-diff, `work/`, not committed as evidence) found the
varying-routed differential pair produces exactly **16** differing fragment bytes (down from 116),
in a clean, systematic, mirrored pattern (8 byte positions + 8 positions with near-inverted
values) — and that splicing individual bytes from that set shows exactly **two** of them
(fragment-relative offsets `_agc.main+33` and `+63`) are EACH independently sufficient to flip the
oracle from red to green, reproduced at the SAME relative offsets in a second, differently
register-pressured differential pair. `CAPTURE_CONTRACT.json` freezes: 2 native-baseline controls
(pair1, pair2), 4 positive single-byte splices (offsets 33/63, both pairs), 2 negative-control
single-byte splices (offset 43, both pairs, which do NOT flip the result), 1 both-causal-offsets
case, and 1 all-16-bytes-spliced consistency case (should exactly reproduce the B-native/green
outcome). 10 cases total.

## 3. Successor spec for the still-undecoded preceding pointer-load instruction (TEX-15 remainder)

Not attempted here (time-boxed out of this contract): each texture "read"/"sample" bundle is
preceded by 4-byte instructions whose byte0 low nibble is `0xb` (matching the "compact move"
family family described in `docs/isa/register-move-and-liveness.md` §1, though with different
`byte+2` values than that chapter's validated `0x01`/`0x08` — these may be a sibling
uniform/pointer-materializing variant of the same family, or a distinct encoding; not
determined). These are the instructions that plausibly carry the REAL 0-127 texture selector (as
a preloaded-uniform-table index or similar), with `op+4` merely naming which already-loaded
register holds the result. A successor should: (a) build a differential pair analogous to §2's
gradient design but isolating `[[texture(N)]]` for two DISTINCT single-texture kernels (texture
index only, no second live resource) to see whether the declared MSL index changes any preceding
instruction byte; (b) if so, splice-validate that byte's causal effect the same way; (c)
cross-reference `docs/isa/register-move-and-liveness.md`'s open `byte+2` semantics work
(EXP-0087) since this may be the same instruction family under a different addressing mode.

## 4. Standing gates implemented

- **`--selftest`**: `verify.py --selftest` — state-agnostic (works against the committed
  `PRE_GPU` tree with no `raw/`), exercises one authoritative shared key-set (`DIFF_KEYS`,
  `SPLICE_TEX_KEYS`, `SPLICE_GRAD_KEYS`) against synthetic in-process fixtures derived live from
  `CAPTURE_CONTRACT.json` (RECORDED REALITY, never hand-copied).
- **`--seqtest`**: builds three isolated fixture trees (`PRE_GPU` / `RUN01_PRESENT` /
  `RUN02_PRESENT`) and subprocess-invokes the real gate sequence against each.
- **Non-recorded pre-capture smoke gate**: `run.py`'s `smoke_gate()` runs the `tex_native` case
  once, checks it, BEFORE `raw/` is created for that run id; that invocation is never itself
  written into a byte-compared record.
- **No nondeterministic field in byte-compared records**: every case receipt's `stdout` payload
  is a fixed-key JSON object with no timestamp/pointer/PID fields; cross-run comparison
  (`verify.py --between-runs`) requires the full row list byte-identical between run01/run02.
- **RECORDED REALITY fixtures**: `--seqtest`'s fixture case list and expected payloads are
  derived live from `CAPTURE_CONTRACT.json`, never hand-copied into `verify.py`.

Two capture run IDs, chosen fresh and never reused: `m4-20260828d-run01`, `m4-20260828d-run02`.

## 5. Clean-room provenance (pre-registration statement)

Clean-room provenance: OWN-SHADER + PUBLIC
Inputs inspected: our own MSL (`kernels/*.metal`), our own compiled AGX bytes (extracted via the
project's own `tools/shdump/agxparse.py`, a public-Mach-O-format parser, not Apple code), our own
splice-and-dispatch harnesses (`harness/texsplice.m`, `harness/gradsplice.m`).
Apple binary introspection: NONE.
