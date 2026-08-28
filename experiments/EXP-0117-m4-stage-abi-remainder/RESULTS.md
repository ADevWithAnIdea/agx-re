# EXP-0117 Results — M4 stage-ABI remainder (DRV-ABI-01 / P0.8)

**Target: Apple M4/G16G, local host only** (Mac16,10, 10 GPU cores). macOS
26.6.2 (25G82), Metal 4 (Apple9), Apple clang 21.0.0, `xcrun` 72, Python
3.14.6. **A18 Pro: no data collected** (hands-off per `CLAUDE.md`); every
fact below is `INFERRED`-by-family for A18/G17P per `docs/m4-deltas.md`'s
ISA-identity finding, never independently confirmed on A18.

**Two official captures**, `raw/m4-20260828-run01/` and
`raw/m4-20260828-run02/`, **148 cases each** (142 `OK` + 1 designed negative
control (`int [[stencil]]` compile rejection) + 5 designed fatal-abort
cases, each a fully separate `run.py` process invocation).
`python3 verify.py --crossrun raw/m4-20260828-run01 raw/m4-20260828-run02`
→ **148/148 byte-identical, 0 mismatches**, including the deterministic
assertion text of every `PROCESS_ABORT` case. Zero unexpected failure, zero
`CMDBUF_ERROR` in either official capture, zero host instability anywhere
in this experiment.

---

## Standing-gate results

| Gate | Result |
|---|---|
| `--selftest` | **11/11 PASS** (runnable with zero `raw/` captures present; re-run and still passing after both official captures) |
| `--seqtest` | **3/3 PASS** — `PRE_GPU → RUN01_PRESENT → RUN02_PRESENT` all correctly detected |
| Non-recorded smoke gate | `verify.py --smoke` (wraps `run.py --smoke-only`, writes only to `work/`) — one real structural-adjacent case + one real HW-PROBE case, both `OK`, run **before** either official capture and before `raw/` existed |
| No-nondeterministic-field | `run.py`'s `check_no_nondet()` statically forbids `{duration_ms, pid, timestamp, started_utc, address, elapsed}` inside any case's `gated` record, recursing into nested dicts **and lists of dicts** (needed for the `calls[]` array shape); enforced at capture time |
| Fixtures from recorded reality | `harness/fixtures/recorded_reality.json` — 2 records built from real M4 GPU/compiler calls made during this experiment's own harness development, used by `--selftest` |
| Cross-run byte-exact gate | **148/148 PASS**, 0 mismatches |

Other CODEX/SUBAGENT_BRIEF discipline followed: append+`fsync` after every
case record (`run.py`); `PROGRESS.md` per milestone (including two disclosed
kernel/harness bugs found during pilot, one disclosed operational hazard
—fatal process aborts— and one disclosed unresolved anomaly in the
barycentric item, all with the exact evidence); a full 148-case dry run into
`work/dryrun1/` (never `raw/`) before spending either official run id; one
process per case; hard 30s per-case / 60s per-build timeouts; one CLI-driven
parameter family varied per case; `raw/` run-directory creation refuses to
overwrite/reuse an existing dir; `CAPTURE_CONTRACT.json` pins authored-file
sha256 hashes (verified unchanged from `PRE_GPU` freeze through
`RUN02_PRESENT`) rather than live `HEAD`.

---

## TL;DR — per-item verdicts

1. **Programmable-blend-epilog spec** — **CLOSED, HW-VALIDATED across the
   full advertised surface.** All 19 `MTLBlendFactor` values (23/23 including
   dst-role spot checks) and all 5 `MTLBlendOperation` values match the
   standard blend-equation formula to float precision (`analysis/decode.py`,
   `blend_factor: 23/23`, `blend_op: 5/5`). The blend-constant is **NOT
   clamped** to `[0,1]` by the classic API (raw IEEE floats pass through,
   including negative and `>1` values). NaN/±Infinity propagate through the
   Add blend op with **bit-exact IEEE semantics**, payload preserved.
   `blendingEnabled=YES` on a non-blendable integer format is rejected via a
   **fatal process-aborting assertion**, not a graceful error (paired
   positive control on the same format with blending disabled succeeds).
   sRGB attachments blend **in linear space** (confirmed to the nearest
   8-bit quantization step both for a pure store and a real blend).
   Structurally, `blendingEnabled=YES` alone does **not** change the
   compiled bytes when the configured factors reduce to a compile-time
   identity (byte-identical to `blendingEnabled=NO`); a pure
   dst-passthrough configuration compiles to a much shorter stub with **no**
   `tile_read`, while a genuinely data-dependent configuration (both factors
   non-constant) is longer and **does** contain `tile_read` — the compiler
   performs blend-equation constant-folding at pipeline-creation time and
   only emits a tilebuffer read when the destination's actual value is
   needed. The programmable-epilog mechanism itself (`tile_read` +
   ordinary ALU + `frag_color_store`, driven via a `[[color(n)]]` fragment
   **input**) was independently constructed to implement **logic ops**
   (AND/OR/XOR/INVERT) — a Vulkan `VK_LOGIC_OP_*`-class capability the
   fixed-function-shaped blend descriptor cannot express at all — and
   verified bit-exact against 8/8 constructed cases including the
   all-zero/all-one boundary. Color-attachment count 1..8 all render
   correctly and independently (half-float exact); attachment index 8 (the
   9th, 0-based) is a **hard, fatal, API-level ceiling**. See §1 for the
   full construction-grade spec.
2. **CS sysvals beyond dynamic shared memory** — **CLOSED BY CITATION.**
   EXP-0092 (M4) already `HW-VALIDATED` this in full; not re-tested.
3. **FS output ordering** — **CLOSED, HW-VALIDATED.** Source-statement
   order of struct-field computation is provably irrelevant (two fragment
   functions computing identical final values in opposite source order
   compile **byte-identical**, not just functionally identical). A real
   depth-test failure (driven by the shader's own explicit depth output)
   completely suppresses color AND stencil writes, and the stencil op that
   fires is exactly the one configured for that pass/fail outcome — verified
   in **both** op-assignment directions as a paired control.
4. **Barycentric VALUE correctness** — **PARTIAL, decisive mechanism proof
   + one disclosed, unresolved anomaly.** `sum(b)==1.0` exactly; an
   in-shader manual recombination using `b` is internally self-consistent.
   The exact vertex-correspondence/linear-vs-perspective convention could
   **not** be reliably pinned down: a supplementary ad hoc probe found the
   observed `b` value is sensitive to an unrelated shader-source change
   (adding a position-echo output flips the result to match this
   experiment's own perspective-corrected host oracle almost exactly) —
   reported as a genuine anomaly, not resolved here.
5. **`primitive_id` VALUE correctness** — **CLOSED, HW-VALIDATED.** Tracks
   primitive **assembly order**, not raw vertex-index values (a shuffled
   index buffer's first-submitted triangle gets `pid=0` regardless of which
   vertex indices it uses). **Resets to 0 for each instance** of an
   instanced draw rather than accumulating globally.
6. **MSAA centroid-vs-sample differentiation** — **CLOSED, HW-VALIDATED.**
   Within one partially-covered pixel (N=4), the two live per-sample
   invocations report **identical** `centroid` values but **measurably
   different** `sample` values matching each invocation's own sub-pixel
   position — direct differentiation, not just both-differ-from-center.
   `[[sample_mask]]`'s finite bit width was independently swept (N=1,2,4):
   exactly `popcount(mask & ((1<<N)-1))/N`, bits ≥N silently inert (no
   aliasing/wraparound), 14/14 constructed cases exact.
7. **Full CALL-ABI byte decode** — **CLOSED.** EXP-0109's flagged
   `byte+6` `0x54`-vs-`0x56` discrepancy against EXP-0035's A18 record is
   resolved: on this M4/toolchain, **`byte+6` is uniformly `0x54` across
   every one of six constructed call topologies** (single call, 2 calls
   same/different callee, 3 calls, an inflated-callee-body distance probe,
   and a nested non-leaf frame reproducing EXP-0035's own "mid" shape
   byte-for-byte, including its `byte+5` `0x10`-then-`0x00` pattern across
   two nested calls) — directly refuting a "call-site count" or
   "leaf-vs-nonleaf" explanation (both would have to also explain a
   single-call-site kernel showing `0x54`, which it does). Call-nesting
   depth 1..128 (14 constructed depths) all execute correctly against the
   exact host oracle with zero faults — no depth limit found in range.
8. **Stencil-value overflow** — **CLOSED, HW-VALIDATED.** Values beyond 255
   **truncate to their low 8 bits** (`value & 0xFF`), not clamp — confirmed
   for `uint` (256→0, 257→1, 511→255, 65535→255, 4294967295→255) and
   `ushort` (300→44). `int` (signed) is **rejected at compile time**.
9. **Split prolog/epilog register-crossing mechanics** — **DEFERRED**, per
   DRV-ABI-01's own "specify, do not implement" scope; item 7's CALL-ABI
   decode is the necessary, now-closed, precursor.

---

## §1 Programmable-blend-epilog synthesis specification

### 1.1 Mechanism (public prior art + this experiment's structural confirmation)

Per Alyssa Rosenzweig's public M1-generation writeup (`gpu_knowledge/blog_posts/
alyssa_rosenzweig/dissecting-m1-gpu-part4.md`, PUBLIC): "Apple relies on
shader code in lieu of fixed-function graphics hardware for tasks like
vertex attribute fetch and blending." EXP-0029 already decoded the
mechanism structurally on A18 (`tile_read`, byte0 `0x67`, byte+1`==0x0e`, a
`[[color(n)]]` fragment-function **input** reading the tilebuffer's current
color; `docs/isa/encoding-tables.md`'s `tile_read`/`frag_color_store`
entries). EXP-0109 independently confirmed there is **no** separate
prolog/epilog code segment — every compiled fragment program is exactly
`["_agc.main.constant_program", "_agc.main"]`.

**This experiment's own structural contribution** (`blendstruct_*` cases,
`struct_extract` backend, same MSL source `f_solid` compiled through
identical pipeline-descriptor variation): whether `tile_read` appears in
the compiled bytes depends **only** on the pipeline-descriptor blend state,
not on any shader-source change —

| case | blend state | compiled length | `tile_read` present |
|---|---|---:|---|
| `blendstruct_off` | disabled | 56 B | no |
| `blendstruct_on_srconly` | enabled, src=One, dst=Zero (reduces to plain overwrite) | 56 B, **byte-identical to `off`** | no |
| `blendstruct_on_dstonly` | enabled, src=Zero, dst=One (reduces to pure dst-passthrough) | **16 B** (much shorter stub) | no |
| `blendstruct_on_both` | enabled, src=SourceColor(2), dst=DestinationColor(6) (genuinely data-dependent) | 84 B | **yes** |

**OBSERVED.** `off` and `on_srconly` compile to literally the same 56 bytes.
`on_dstonly` compiles to a 16-byte stub containing only a `frag_tile_setup`
(`0x87`) + fence (`0x07`) pair — no color computation, no store visible in
the extracted region. `on_both` is the longest and is the only variant
containing `tile_read`. Both runs byte-identical.

**INTERPRETED.** Metal's compiler evaluates the blend equation's
DEPENDENCE on the destination value **at pipeline-creation time**, using
the two selected `MTLBlendFactor`s and the op as compile-time constants: if
the whole equation reduces to "ignore dst" (source factor alone determines
the result), no `tile_read` is emitted and — in the extreme case observed
here — the compiler appears to eliminate essentially the entire fragment
output when the equation reduces to "keep dst unchanged" (a mathematical
no-op the driver's own generator should recognize and can equally choose
to elide). **Driver consequence — this is the actual synthesis rule a
future epilog generator must implement:** classify the configured
`(sourceFactor, destinationFactor, op)` triple at pipeline-build time;
emit `tile_read` **only if** the destination's true numeric value is
required to compute the result (i.e., the destination factor is not the
compile-time-constant `Zero`, or the op's own definition needs `dst`
regardless of factor, e.g. `Min`/`Max`/`Subtract`-family with a nonzero
dst factor); otherwise, skip the read and, when possible, skip the whole
store when the equation is provably a dst-identity. This mirrors exactly
what Metal's own compiler was observed to do.

### 1.2 Fixed-function blend-factor matrix — CONSTRUCTED for all 19 advertised factors

Method: `f_solid` (buffer-driven RGBA source color, no compiled-in
constant), real render to an `RGBA32Float` target (exact float32 readback,
no rounding ambiguity), `src=(0.7,0.4,0.2,0.9)`, `dst=(0.3,0.6,0.8,0.1)`
(via `clearColor`), `blendConstant=(0.25,0.75,0.5,0.6)`, `Source1=
(0.5,0.6,0.7,0.8)` (needs a dedicated `f_solid_dualsrc` fragment function —
Metal rejects a `Source1*`-selecting pipeline unless the shader declares an
`index(1)` output; own-compiler diagnostic captured verbatim, see
`PROGRESS.md`). Each of the 19 factors tested in the **source** role
(destination factor pinned to `Zero`, op=`Add`, isolating the tested
factor's exact contribution: `result = src * factorVec(id)`), plus 4
factors spot-checked in the **destination** role (source factor pinned to
`Zero`): **23/23 exact matches** (`analysis/decode.py`, tolerance 1e-3,
actual float32 agreement well under that) against the standard,
publicly-documented GPU blend-factor formula table (component-wise;
`SourceAlphaSaturated`'s RGB-role formula `min(srcA, 1-dstA)` correctly
diverges from its alpha-role formula, which is pinned to `1.0` — both
confirmed independently in the same case since the harness applies the
same factor id to both the RGB and alpha slots simultaneously).

**OBSERVED, HW-VALIDATED, exact, both runs byte-identical:** all 19
factors (`Zero, One, SourceColor, OneMinusSourceColor, SourceAlpha,
OneMinusSourceAlpha, DestinationColor, OneMinusDestinationColor,
DestinationAlpha, OneMinusDestinationAlpha, SourceAlphaSaturated,
BlendColor, OneMinusBlendColor, BlendAlpha, OneMinusBlendAlpha,
Source1Color, OneMinusSource1Color, Source1Alpha, OneMinusSource1Alpha`)
produce exactly the value the standard formula predicts, in **both** the
source and destination role where tested. **Driver consequence:** every
advertised `MTLBlendFactor` is genuinely, correctly implemented by real
hardware/API blend math on Apple9 — none require software emulation, and
the standard GPU blend-factor formula table (identical across GL/Vulkan/
D3D/Metal) applies without modification.

### 1.3 Fixed-function blend-operation matrix — all 5 advertised ops CONSTRUCTED

`src=dst-role factors both pinned to One` (chosen so `src+dst=(1,1,1,1)`
component-wise, uniquely distinguishing Add from Subtract/Min/Max/
ReverseSubtract): **5/5 exact matches.** `Add`→`src+dst`, `Subtract`→
`src-dst`, `ReverseSubtract`→`dst-src`, `Min`→`min(src,dst)`, `Max`→
`max(src,dst)`. A paired case with `rgbOp=Add, alphaOp=Subtract` on the
SAME pipeline confirmed RGB/alpha op independence (both runs OK, values
consistent with each op applying only to its own channel group).
**Driver consequence:** all 5 ops are native and independently selectable
per RGB/alpha channel group; no emulation needed.

### 1.4 Holes and boundaries — the new (macOS 26.0) `Unspecialized` sentinel family

Public-header research (`MTLRenderPipeline.h`, macOS 26.5 SDK) surfaced a
brand-new sentinel family: `MTLBlendFactorUnspecialized=19`,
`MTLBlendOperationUnspecialized=5`, `MTLColorWriteMaskUnspecialized=0x10`
(and, in a different Metal-4-native API, `MTL4BlendStateUnspecialized=2`),
each documented to "behave as" a specific concrete value "until you
specialize this pipeline value" — Apple's own new mechanism for deferring
per-blend-state shader-variant compilation. **Constructed and verified on
the classic (non-MTL4) pipeline API, exactly as documented:**

| sentinel | documented fallback | constructed test | observed | match |
|---|---|---|---|---|
| `MTLBlendFactorUnspecialized`(19), source role | behaves as `One` | `sr=19,dr=0,sa=19,da=0` (isolates src) | result == `src` exactly | **yes** |
| `MTLBlendFactorUnspecialized`(19), dest role | behaves as `Zero` | `sr=1,dr=19,sa=1,da=19` (isolates dst) | result == `src` exactly (dst contributes 0) | **yes** |
| `MTLBlendOperationUnspecialized`(5) | behaves as `Add` | `src/dst` chosen so ops are distinguishable | result == `src+dst` exactly | **yes** |
| `MTLColorWriteMaskUnspecialized`(0x10) | behaves as `All` | `blendingEnabled=NO, mask=0x10` | all 4 channels == `src` | **yes** |

**First-invalid, past the legal range (constructed, not just observed):**
`MTLBlendFactor=20` and `MTLBlendOperation=6` (one past `Unspecialized`)
both raise a **FATAL Metal API validation assertion that aborts the whole
process** (`blendFactorSource:4766: failed assertion 'Invalid blend
factor'`; `validateWithDevice:5044: ... func is not a valid
MTLBlendOperation.`) — not a graceful `NSError`, reproduced identically
both runs (`PROCESS_ABORT`, signal 6, deterministic stderr text
cross-run-compared and matched). A write-mask bit **past** the documented
range (`0x20`) is, by contrast, **silently inert** — no crash, behaves as
if unset (paired with `0x0`/`None` giving the identical clear-value
result) — the STRICTLY-validated enum fields (factor/op) and the
LOOSELY-tolerant bitmask field (write mask) have genuinely different
failure-mode contracts. **Driver consequence:** a compiler backend
targeting Metal 4's dynamic/deferred blend-specialization workflow can
rely on the documented Unspecialized fallback semantics exactly as
written, now independently HW-confirmed; a backend must NEVER construct a
blend-factor/operation value outside `[0,19]`/`[0,5]` since doing so is
fatal, not merely rejected.

### 1.5 Write mask — all single channels + combos + boundary, CONSTRUCTED

`src=(0.7,0.4,0.2,0.9)`, `dst=(0.3,0.6,0.8,0.1)` (via clearColor),
`blendingEnabled=NO` (isolating the mask itself from blend math):

| mask | requested bits | observed result | interpretation |
|---|---|---|---|
| `None`(0x0) | nothing | `dst` exactly, all 4 channels | nothing written |
| `Alpha`(0x1) | A only | `(dst.r,dst.g,dst.b, src.a)` | bit0 = alpha |
| `Blue`(0x2) | B only | `(dst.r,dst.g, src.b, dst.a)` | bit1 = blue |
| `Green`(0x4) | G only | `(dst.r, src.g, dst.b, dst.a)` | bit2 = green |
| `Red`(0x8) | R only | `(src.r, dst.g, dst.b, dst.a)` | bit3 = red |
| `All`(0xf) | RGBA | `src` exactly, all 4 channels | — |
| `Red|Alpha`(0x9) | R+A | `(src.r, dst.g, dst.b, src.a)` | combos compose bitwise |
| `Unspecialized`(0x10) | — | `src` exactly (== `All`) | confirmed §1.4 |
| invalid(0x20) | — | `dst` exactly (== `None`) | inert past range |

**HW-VALIDATED, exact, both runs.** **Driver consequence:** `writeMask`
is a genuine per-channel gate applied independently of blend math (works
identically with blending off), the bit layout is `A=0x1,B=0x2,G=0x4,
R=0x8` (note: NOT the naive `R=0x1` ordering), and out-of-range bits are
safe to leave set (e.g. by a naive `0xFFFFFFFF` mask) without risk of a
fault — unlike the strict factor/op enums.

### 1.6 Blend constant — unclamped, CONSTRUCTED at both boundaries and past them

`factor=BlendColor/BlendAlpha`, neutral `src=(1,1,1,1)`, `dst`-factor=Zero
(isolates the constant's raw contribution):

| constant | observed result | interpretation |
|---|---|---|
| `(0,0,0,0)` (min legal) | `(0,0,0,0)` | exact |
| `(1,1,1,1)` (max legal) | `(1,1,1,1)` | exact |
| `(-0.5,-0.5,-0.5,-0.5)` (below legal) | `(-0.5,-0.5,-0.5,-0.5)` | **unclamped** |
| `(1.5,1.5,1.5,1.5)` (above legal) | `(1.5,1.5,1.5,1.5)` | **unclamped** |

**HW-VALIDATED, exact, both runs.** **Driver consequence:**
`setBlendColor` accepts and the hardware blend math uses raw IEEE floats
with **no clamping to `[0,1]`** despite the documented `[0,1]` legal
range — a driver must not rely on hardware clamping to enforce that range
if the API contract requires it; out-of-range values propagate unclamped
into the framebuffer.

### 1.7 Format constraints — integer-format-blend REJECT, sRGB linear-space blend, spot formats

**Integer format + blending, paired positive/negative control:**
`MTLPixelFormatR32Uint` with a correctly-shaped `uint`-returning fragment
function (`f_logic_copy`): `blendingEnabled=NO` → pipeline creation
**succeeds** (positive control, proving the format/function pairing itself
is valid); `blendingEnabled=YES` → **fatal process-aborting assertion**
(`"Blending is enabled for render target 0; however, the pixelformat
MTLPixelFormatR32Uint for this render target is not blendable."`),
reproduced identically both runs. **Driver consequence:** a compiler must
never enable blending on an integer-valued color format; the hardware/API
has no fallback path for this, it is a hard construction-time error.

**sRGB blend semantics — CONSTRUCTED and decisively confirmed:** shader
outputs a linear color value; harness compares an `RGBA8Unorm_sRGB`
attachment against a plain `RGBA8Unorm` one, both for a pure store and a
real blend (`src=dst=Add`, `dst` preloaded via `clearColor=0.2`):

| case | format | src (linear) | dst (linear) | observed stored `u8` | predicted |
|---|---|---:|---:|---:|---:|
| pure store | sRGB | 0.5 | — | 188 | `sRGBenc(0.5)*255≈187.9` |
| pure store | UNorm | 0.5 | — | 128 | `0.5*255=127.5→128` |
| blend (Add) | sRGB | 0.5 | 0.2 | 218 | `sRGBenc(0.5+0.2)*255≈217.8` |
| blend (Add) | UNorm | 0.5 | 0.2 | 178 | `(0.5+0.2)*255=178.5` |

**HW-VALIDATED, exact to the nearest 8-bit quantization step, both runs.**
**Driver consequence:** for an sRGB-tagged attachment, the blend equation
executes in **linear space** — the destination is decoded from sRGB to
linear on load (or the clear value is already treated as linear), the
blend math (`tile_read`/ALU/`frag_color_store`) operates on linear values,
and the STORE re-encodes to sRGB. A driver's epilog generator targeting an
sRGB attachment must apply this same load/blend/store-encode discipline,
not blend the raw encoded byte values.

**Format spot checks:** `RGBA16Float` and `RGBA8Unorm` identity-blend
(`src=One,dst=Zero`) both `OK`, both runs — no format-specific rejection
for ordinary float/normalized formats.

### 1.8 Alpha-to-coverage / alpha-to-one — CONSTRUCTED, exact fractional relationship

`f_alpha_out` (buffer-driven color), N=4 MSAA, hardware box-filter resolve
(`storeAction=MultisampleResolve`), full geometric coverage (only alpha
value varies coverage via `alphaToCoverageEnabled`):

| requested alpha | resolved RGB | resolved alpha | interpretation |
|---:|---:|---:|---|
| 0.0 | 0.0 | 0.0 | 0 of 4 samples pass |
| 0.25 | 0.25 | **0.0625** (=0.25²) | 1 of 4 samples pass, EXACT |
| 0.5 | 0.5 | **0.25** (=0.5²) | 2 of 4 samples pass, EXACT |
| 0.75 | 0.75 | **0.5625** (=0.75²) | 3 of 4 samples pass, EXACT |
| 1.0 | 1.0 | 1.0 | 4 of 4 samples pass |

**HW-VALIDATED, exact (not dithered/approximated), both runs.**
**INTERPRETED:** the derived sample-coverage fraction equals the shader's
alpha value **exactly** for these quarter-fraction values (no ordered-
dither approximation observed at this granularity); the shader's own alpha
output is **still written** to whichever samples pass (not zeroed), so the
resolved alpha equals `coverageFraction × shaderAlpha` — the RGB channels
(alpha-independent) resolve to the coverage fraction alone. `alphaToOne`,
tested as a paired enabled/disabled control (N=1, non-MSAA): enabled forces
resolved alpha to exactly `1.0` regardless of the shader's `0.3` output;
disabled passes `0.3` through unchanged. **Driver consequence:**
`alphaToCoverageEnabled`/`alphaToOneEnabled` are both native, exact,
hardware-implemented — no software emulation needed; a driver computing
expected coverage from alpha for e.g. an EDGE-antialiasing or an
order-independent-transparency scheme can rely on this exact linear
relationship (at least at the quarter-sample granularities tested here).

### 1.9 NaN / Infinity propagation — CONSTRUCTED, bit-exact IEEE semantics

`src` channel 0 set to an exact bit pattern via buffer (not a compiled
constant), `Add` op, `RGBA32Float` (exact bit readback):

| input bit pattern | dst (linear) | observed result bits | interpretation |
|---|---:|---|---|
| qNaN `0x7FC00000` | 0.0 | `0x7FC00000` (bit-identical) | qNaN + 0 = same qNaN, unchanged payload |
| +Inf `0x7F800000` | 0.0 | `0x7F800000` | +Inf + 0 = +Inf |
| −Inf `0xFF800000` | 0.0 | `0xFF800000` | −Inf + 0 = −Inf |
| qNaN `0x7FC00000` | 2.0 | `0x7FC00000` (bit-identical) | qNaN + finite = same qNaN payload, not re-canonicalized |

**HW-VALIDATED, exact, both runs.** **INTERPRETED:** the blend ALU is
IEEE-754-compliant for NaN/Infinity propagation through `Add`, with **no
flush-to-zero, no clamping, and no payload canonicalization** — the exact
input NaN bit pattern reappears unchanged in the output even when added to
a nonzero finite value. **Driver consequence:** a driver need not special-
case NaN/Inf source colors reaching the blend unit; ordinary IEEE float
arithmetic semantics apply, matching what a Vulkan/GL driver on IEEE-
compliant hardware would already assume.

### 1.10 Programmable epilog for a NON-fixed-function-expressible mode: logic ops

Vulkan's `VK_LOGIC_OP_*` (bitwise AND/OR/XOR/INVERT/…) has **no**
equivalent in `MTLBlendFactor`/`MTLBlendOperation` — Metal's fixed-
function-shaped blend descriptor cannot express it at all. This is
precisely the class of capability DRV-ABI-01 asks the epilog generator to
cover. **Constructed and validated:** `f_logic_and/or/xor/inv/copy`, each
declaring `uint dst [[color(0)]]` as a genuine fragment **input** (forcing
`tile_read`) and computing the result with ordinary MSL bitwise ALU on an
`R32Uint` attachment, via a real two-pass render (pass 1 writes a known
`dst` pattern; pass 2, `loadAction=Load`, runs the logic-op shader):

| op | src | dst | predicted | observed | match |
|---|---:|---:|---:|---:|---|
| AND | `0xF0F0F0F0` | `0xFF00FF00` | `0xF000F000` | `0xF000F000` | yes |
| AND (identity boundary) | `0x00000000` | `0xFFFFFFFF` | `0x00000000` | `0x00000000` | yes |
| OR | `0x0F0F0F0F` | `0xF0F0F0F0` | `0xFFFFFFFF` | `0xFFFFFFFF` | yes |
| XOR | `0xAAAAAAAA` | `0x55555555` | `0xFFFFFFFF` | `0xFFFFFFFF` | yes |
| XOR (self-cancel boundary) | `0xFFFFFFFF` | `0xFFFFFFFF` | `0x00000000` | `0x00000000` | yes |
| INVERT (dst=0) | — | `0x00000000` | `0xFFFFFFFF` | `0xFFFFFFFF` | yes |
| INVERT (dst=all-1, boundary) | — | `0xFFFFFFFF` | `0x00000000` | `0x00000000` | yes |
| COPY (control, ignores dst) | `0x12345678` | `0xAAAAAAAA` | `0x12345678` | `0x12345678` | yes |

**8/8 HW-VALIDATED, exact, both runs.** **Driver consequence:** this is
the literal, constructed, working template for "what a future epilog
generator must emit" for any blend/logic mode the fixed-function-shaped
API surface cannot express: (1) declare the fragment output attachment
also as a `[[color(n)]]` **input** parameter (forces `tile_read`); (2)
compute the desired result with ordinary ALU against the read-back
destination value and the shader's own source computation; (3) return the
result as the ordinary `[[color(n)]]` output (`frag_color_store`). No
special hardware mode, descriptor field, or fixed-function unit is
required or exists for logic ops on Apple9 — they are, and must be,
entirely software (in-shader), exactly as they would be on any GPU lacking
native logic-op hardware.

### 1.11 Color-attachment count — the full 1..8 range CONSTRUCTED, API ceiling found

Real renders (`RGBA16Float`, independently-addressed, independently-
correct per-target values, extending EXP-0109 §3.1's already-validated 1/2/
4 pattern to the FULL range): **natt = 1,2,3,4,5,6,7,8 all render
correctly** (spot-checked at 1, 8: exact half-float match to the `c0×0.1`
… `c0×0.8` formula, both runs). **Pure API-index-ceiling probe**
(`mrtapiceil`, no shader/pipeline creation involved — just touching
`MTLRenderPipelineColorAttachmentDescriptorArray`'s indexer): index 0 and
index 7 (`natt=1,8`) succeed; index 8 and index 9 (`natt=9,10`) **both
raise a FATAL assertion the instant the array is indexed**
(`"attachmentIndex(8) must be < 8"` / `"attachmentIndex(9) must be < 8"`),
**not even catchable via `@try/@catch`** (a lower-level trap, not an
`NSException`) — reproduced identically both runs. **Driver consequence:**
the hard, unconditional ceiling is **exactly 8** color attachments, backed
by a fatal, uncatchable process abort the instant it is exceeded at the
API level — a driver must validate attachment count against this ceiling
itself before ever touching the array.

### 1.12 New capability lead, NOT exercised here (explicitly flagged)

Public-header research (`MTL4PipelineState.h`, macOS 26.5 SDK) surfaced
`MTL4BlendStateUnspecialized`, part of Metal 4's own new, native "deferred
pipeline specialization" mechanism — a DIFFERENT API surface (its own
`MTL4RenderPipelineDescriptor`/command-buffer classes) from the classic
`MTLRenderPipelineDescriptor` path this experiment exercises throughout.
Its doc comment ("Defers determining the blending stage... Behaves as
`MTL4BlendStateDisabled` until you specialize this pipeline value")
independently corroborates §1.1's structural finding — Apple's own
engineering solution to the "shader-variant explosion from baking blend
state into every pipeline" problem this project's `docs/` will need to
document is, itself, a request-for-later-compilation workflow, not a
genuine hardware dynamic-blend register. **Flagged as a high-value lead
for a dedicated follow-up experiment** (building an `MTL4Compiler`/
`MTL4PipelineDescriptor`-based harness is a materially larger, separate
engineering effort); not constructed or tested here beyond reading its
public documentation.

---

## §2 CS system values beyond dynamic shared memory — CLOSED BY CITATION

Not re-tested here. EXP-0092 (M4, `experiments/EXP-0092-m4-sysval-abi/
RESULTS.md`) already `HW-VALIDATED` `get_sr`-based sysvals (GLIO-A02),
vertex/instance/base-vertex/base-instance semantics (GLIO-A03),
`load_num_workgroups`/`threadgroups_per_grid` (GLIO-A05), and a finite-
resource table for this domain (GLIO-A06). Re-litigating it here would not
add evidence; DRV-ABI-01's CS-sysval sub-item is satisfied by that prior
experiment together with EXP-0109 §4 (dynamic threadgroup memory +
preamble presence).

---

## §3 FS output ordering constraints — CLOSED, HW-VALIDATED

### 3.1 Source-statement order is provably irrelevant

`f_order_ab` (color→depth→stencil assignment order) and `f_order_ba`
(stencil→depth→color, identical final values) — **structural**
(`struct_extract`, `RGBA8Unorm`+`Depth32Float`+`Stencil8` pipeline):
compiled fragment bytes are **byte-for-byte identical**. **Functional**
(`fsorder_render_cmp`, real render, two disjoint fragment functions, same
pipeline/state): the two result records (`color`, `depth`, `stencil`) are
**identical**. Both runs byte-identical. **HW-VALIDATED.** **Driver
consequence:** a compiler backend never needs to worry about the SOURCE
order in which a fragment shader computes/assigns its color/depth/stencil/
sample-mask struct fields — MSL's single-struct-return model means there
is no partial-write-order hazard to preserve; the compiler is free to
reorder computation for scheduling purposes.

### 3.2 Depth-test-failure suppression + stencil-op selection — paired, both directions

A real `MTLCompareFunctionLess` depth test, clear depth `0.5`, shader's OWN
explicit `[[depth(less)]]` output set (via a harness-supplied threshold
correctly scaled to the target width, see `PROGRESS.md`'s bug-fix note) to
`0.2` on the left half (PASSES) and `0.9` on the right half (FAILS).
Stencil test held at `Always` (op selection depends purely on the depth
outcome). Two cases swap WHICH op fires on pass vs fail, as a paired
control:

| case | depthFailOp | depthPassOp | side | color | depth | stencil |
|---|---|---|---|---|---:|---:|
| `keep_replace` | Keep | Replace(shader value 222) | left (PASS) | `(255,255,255,255)` (written) | `0.2` (shader value landed) | `222` (shader value, via EXP-0109 §3.4's Replace-uses-shader-value rule) |
| `keep_replace` | Keep | Replace | right (FAIL) | `(0,0,0,0)` (clear, **suppressed**) | `0.5` (clear, **suppressed**) | `77` (clear, Keep fired — **suppressed**) |
| `replace_keep` | Replace | Keep | left (PASS) | `(255,255,255,255)` | `0.2` | `77` (clear — Keep fired on PASS this time) |
| `replace_keep` | Replace | Keep | right (FAIL) | `(0,0,0,0)` (**suppressed**) | `0.5` (**suppressed**) | `222` (shader value — Replace fired on FAIL this time) |

**HW-VALIDATED, exact, both runs.** **INTERPRETED:** (1) a depth-test
failure driven by the shader's own computed depth value completely
suppresses color AND stencil writes, extending EXP-0109 §3.3/§3.4's
per-channel findings and EXP-0091's discard-suppression precedent to a
genuine fixed-function depth-test failure (not `discard_fragment()`); (2)
the stencil-op selection correctly uses the **post-shader** depth-test
outcome — reconfirmed in BOTH directions by swapping which op is
configured for pass vs fail and observing the correct one fire each time;
(3) EXP-0109 §3.4's "Replace uses the shader's `[[stencil]]` value, not
the encode-time reference" finding holds even in this more complex
combined pass/fail/op-selection scenario. **Driver consequence:** no
special ordering constraints exist between color/depth/stencil outputs
from one fragment invocation beyond the standard fixed-function
depth/stencil-test-then-write pipeline; a compiler can treat the whole
struct return as a single atomic candidate write, gated as a unit by the
depth/stencil tests, exactly as documented for a conventional
depth/stencil pipeline.

### 3.3 Explicitly deferred (not silently dropped)

Per-sample `[[sample_mask]]`-driven suppression of one SPECIFIC excluded
sample's depth/stencil write (as distinct from §6.2's uniform-mask width
sweep, which validates the mechanism for the COLOR channel only) was not
independently built — no budget for a per-sample depth/stencil MSAA
readback rig in this experiment. `PARTIAL`/`INFERRED`-by-analogy to the
uniformly-proven color case and to EXP-0111 FS-12's own precedent for the
same open question on discard-driven (rather than mask-driven) stencil
suppression.

---

## §4 Barycentric-coordinate VALUE correctness — PARTIAL, decisive mechanism proof + disclosed anomaly

### 4.1 What IS established, HW-VALIDATED

`bary_values` case: asymmetric, non-uniform-`w` triangle (`w=1,2,4`,
screen position independent of `w`), per-vertex tags `(10,20,30)`, fragment
shader reports raw `barycentric_coord` AND an in-shader manual
recombination `b.x*tag0+b.y*tag1+b.z*tag2`:

- **`sum(b) == 1.00000001`** (exact to float precision) — a genuine
  barycentric partition of unity, both runs.
- **The in-shader manual recombination is internally self-consistent**:
  `b.x*10+b.y*20+b.z*30` computed ON-DEVICE from the SAME `b` matches an
  independent OFF-device recomputation from the same observed `b` values
  to float precision (`23.782555` observed vs `23.782554` recomputed).

**HW-VALIDATED, both runs byte-identical.** This proves `barycentric_coord`
is a genuine, internally-consistent, usable set of per-fragment weights
over the primitive's 3 vertices — the basic ABI contract (three weights
summing to one, usable for manual attribute recombination exactly as a
compiler backend would use them) holds.

### 4.2 What is NOT established — a disclosed, reproduced anomaly

The exact **vertex-to-component correspondence** (which of `b.x/b.y/b.z`
belongs to which emitted vertex) and the **linear-vs-perspective-correct**
convention could **not** be reliably pinned down. Neither of this
experiment's two candidate host-oracle models (screen-space linear;
perspective-corrected, both independently computed in `analysis/decode.py`
from the known triangle geometry and the exact sample pixel, itself
confirmed via a supplementary probe to be `(32.5, 32.5)` as intended)
matches the OFFICIAL, two-run-gated observed `b`.

**Root-cause investigation** (supplementary, single-run, **non-frozen** ad
hoc probes, `work/supplementary/bary_diag*.{metal,m}` — mirroring
EXP-0109 §3.2's precedent for a post-hoc gap-closing single probe, full
detail in `PROGRESS.md`): a fragment function textually **identical** to
the official `f_bary` reproduces the official value exactly. Adding a
THIRD output that simply echoes the built-in `float4 pos [[position]]`
back out to a color attachment — otherwise unchanged — flips the compiled
`barycentric_coord` readback to a DIFFERENT value that DOES match this
experiment's perspective-corrected host model to 4 decimal places.
Presence/absence of unrelated functions in the same source file was
independently tested and ruled out as the cause.

**INTERPRETED.** This is reported as a genuine, 4×-reproduced anomaly, not
resolved here: an unrelated fragment OUTPUT addition changes the compiled
interpretation or delivered value of `barycentric_coord` in this specific
probe shape, on this exact toolchain — plausibly a compiler/register-
allocation interaction (e.g. the presence of a `[[position]]` echo output
changing which hardware register or interpolation-setup path feeds the
barycentric read), not necessarily a hardware fact about
`barycentric_coord` itself. The OFFICIAL, two-run-gated capture (§4.1's
shape, no position echo) is authoritative for this experiment's verdict.
**Verdict: `PARTIAL`.** **Driver consequence:** a compiler backend can
rely on `barycentric_coord` summing to 1 and being usable for manual
attribute recombination via a per-primitive vertex-data buffer (the
correct general mechanism), but must NOT yet assume a specific vertex-
order convention or linear-vs-perspective semantics without further,
dedicated investigation — flagged as an explicit open item, not silently
resolved either way.

---

## §5 `primitive_id` VALUE correctness — CLOSED, HW-VALIDATED

### 5.1 Assembly order, not raw vertex-index values

`pid_indexed_shuffled`: an indexed draw with index buffer
`{9,10,11, 0,1,2, 3,4,5, 6,7,8}` (first-submitted triangle uses vertex
indices 9,10,11, which — under NATURAL vid-to-column mapping — is
"column 3"'s geometry):

| screen column (fixed) | which primitive rendered there | observed `primid` |
|---|---|---:|
| 0 | 2nd submitted (indices 0,1,2) | **1** |
| 1 | 3rd submitted (indices 3,4,5) | **2** |
| 2 | 4th submitted (indices 6,7,8) | **3** |
| 3 | 1st submitted (indices 9,10,11) | **0** |

**HW-VALIDATED, exact, both runs.** Each screen region's `primid` equals
its ASSEMBLY-ORDER position in the index buffer, not any function of the
raw vertex-index values it uses. Positive control: `pid_nonindexed`
(natural order) gives `primid=0,1,2,3` in column order, exactly as
expected, with a genuine null-detector (unwritten regions read the poison
clear value `999`, proving the harness distinguishes "written" from
"not").

### 5.2 Resets per instance, does not accumulate

`pid_instanced`: 2 instances placed in geometrically DISJOINT screen
regions (via a per-instance NDC-Y offset added to `v_pidquad`, so both
instances are independently readable rather than the second overdrawing
the first):

| instance | region | observed `primid` per column |
|---|---|---|
| 0 | bottom half | `0,1,2,3` |
| 1 | top half | `0,1,2,3` (**NOT** `4,5,6,7`) |

**HW-VALIDATED, exact, both runs.** **Driver consequence:** `primitive_id`
is a per-DRAW-CALL assembly counter that resets for each instance and
tracks primitive submission order (post-index-resolution), never raw
index-buffer content — a compiler backend implementing NIR's `gl_PrimitiveID`
can rely on this directly, with no per-instance offset correction needed
and no dependency on the actual vertex-index values used.

**Confounder resolved during pilot:** `[[instance_id]]` is a vertex-stage-
only MSL builtin (rejected as a fragment-function input attribute at
compile time — own-compiler diagnostic captured verbatim, see
`PROGRESS.md`); the instancing test relays it via an ordinary `[[flat]]`
varying instead.

---

## §6 MSAA-dependent centroid vs. sample VALUE differentiation — CLOSED, HW-VALIDATED

### 6.1 Direct per-invocation differentiation

Reusing EXP-0111's proven partial-coverage geometry (`interp_centroid_extrap`:
N=4, single pixel, triangle edge at NDC x=−0.2, 2 of 4 samples covered,
pixel CENTER strictly outside coverage), a per-sample-forced fragment
shader atomic-appends every invocation's `(sample_id, sample-value,
centroid-value, center-value)` via pull-model calls on ONE `interpolant<>`
member:

| `sample_id` | `interpolate_at_sample` | `interpolate_at_centroid` | `interpolate_at_center` |
|---:|---:|---:|---:|
| 0 | **−0.24705887** | −0.24705887 | 0.0039215088 |
| 2 | **−0.74901962** | −0.24705887 | 0.0039215088 |

**HW-VALIDATED, exact, both runs.** `centroid` and `center` are IDENTICAL
across both live invocations of the pixel (as expected — both compute ONE
value for the whole pixel); `sample` is DIFFERENT between the two
invocations, each matching that invocation's own sub-pixel position — the
decisive differentiation EXP-0111 left open. **Driver consequence:**
`sample`-qualified interpolation genuinely re-evaluates per invocation at
each covered sample's true position (not a single pixel-wide value
computed once and broadcast), while `centroid` computes the SAME
coverage-weighted value for every invocation of that pixel — a compiler
backend can rely on this distinction exactly as documented, and must NOT
conflate `sample` with `centroid` even though both differ from
(unclamped) `center` under partial coverage.

### 6.2 `[[sample_mask]]` finite bit width — the coordinator's "sample mask width" row

Uniform (non-per-sample-forced) `[[sample_mask]]` output, hardware
box-filter resolve, sample counts N=1,2,4:

| N | mask values tested (hex) | formula | result |
|---:|---|---|---|
| 4 | `0x0,0x1,0x3,0x7,0xF,0x10,0xFFFFFFFF` | `popcount(mask & 0xF)/4` | **7/7 exact**; `0x10` and `0xFFFFFFFF` both resolve as if only bits 0-3 existed |
| 2 | `0x0,0x1,0x3,0x4,0xFFFFFFFF` | `popcount(mask & 0x3)/2` | **5/5 exact**; `0x4` (first bit beyond N=2) resolves as `0` |
| 1 | `0x0,0x1` | `popcount(mask & 0x1)/1` | **2/2 exact** |

**14/14 HW-VALIDATED, exact, both runs.** **Driver consequence:** the
LEGAL mask width equals EXACTLY the configured sample count (bits
`[0, N-1]`); any bit at position `≥N` is silently, completely inert — no
wraparound, no aliasing into a lower bit, no fault. A compiler backend can
freely emit a mask with high bits set (e.g. a naive `0xFFFFFFFF` "all
samples") for any legal N without needing to first mask it down to `N`
bits.

---

## §7 Full CALL-ABI byte decode — CLOSED, resolves EXP-0109's flagged discrepancy

### 7.1 The discrepancy and its resolution

EXP-0109's `cs_call_probe` (M4, two call sites to the same callee, no
nesting) found `byte+6==0x54` at both call sites, versus EXP-0035's A18
single-call-site captures (`direct_call.txt`, `dynamic_library.txt`)
showing `byte+6==0x56` — flagged as an unresolved discrepancy. This
experiment constructed **six** call topologies and extracted every direct
CALL instance (`0f 05 54 1a 8f 00 <byte6> <off40:5B> 00`, 14 bytes) via the
unmodified `tools/shdump`+`agxparse.py` pipeline:

| topology | call sites | nesting | `byte+6` values seen | `byte+5` values | `off40` range |
|---|---:|---|---|---|---:|
| `k_single` | 1 | none | `0x54` | `0x00` | −84 |
| `k_twosame` | 2 (same callee) | none | `0x54`, `0x54` | `0x00`, `0x00` | −90, −118 |
| `k_twodiff` | 2 (different callees) | none | `0x54`, `0x54` | `0x00`, `0x00` | −154, −118 |
| `k_threecalls` | 3 (same callee) | none | `0x54` ×3 | `0x00` ×3 | −88, −118, −148 |
| `k_far` (inflated callee body) | 1 | none | `0x54` | `0x00` | −84 (unchanged from `k_single` — see note) |
| `k_nested` (`mid_fn` sub-region, reproduces EXP-0035's "mid" byte-for-byte) | 2 (same callee) | **non-leaf, spilling** | `0x54`, `0x54` | **`0x10`, `0x00`** | −86, −132 |

**`byte+6` is `0x54` in EVERY constructed case — uniformly, with zero
exceptions — across single-call, multi-call-same-callee, multi-call-
different-callee, three-call, and nested-non-leaf-frame topologies, and
across an `off40` range spanning −84 to −154.**

**INTERPRETED.** This directly and decisively refutes the two most natural
hypotheses read from EXP-0035's own A18 data alone:

- **H-CALL-1 (call-site count determines `byte+6`)** — refuted by
  `k_single`: a lone call site, on this M4/toolchain, already shows
  `0x54`, not the `0x56` EXP-0035's single-call-site A18 examples showed.
- **H-CALL-2 (leaf-vs-nonleaf/nesting determines it)** — refuted by
  `k_twosame`/`k_twodiff`/`k_threecalls` (flat, non-nested, multiple
  calls) agreeing with `k_nested` (genuinely nested, spilling): all show
  `0x54`.
- **H-CALL-3 (`off40` magnitude/sign predicts it)** — not falsified but
  also not needed as an explanation: `byte+6` is invariant across the
  entire −84..−154 range observed, so magnitude alone does not appear to
  select between `0x54`/`0x56` either (though `k_far`'s attempt to force a
  materially different offset via an inflated callee body did NOT actually
  change the offset — see the disclosed limitation below).

The most defensible standing conclusion: **on THIS M4 target under the
CURRENT toolchain (macOS 26.6.2, Apple clang 21.0.0), `byte+6` is
invariantly `0x54`** — this is the operationally important, HW-VALIDATED
fact a driver targeting this exact environment needs. Whether the
`0x54`/`0x56` split instead reflects a **toolchain/compiler-version**
difference between EXP-0035's (older, unrecorded-exact-version) A18
capture and this session's current toolchain — rather than any call-site-
count or nesting property — is the leading candidate explanation but is
`INFERRED`, not provable without re-running the old toolchain (not
available). Notably, EXP-0035's OWN "mid" (nested) case ALSO showed
`byte+6==0x54` even under that older toolchain, meaning even IF a
toolchain-version story is right, it is not simply "old toolchain always
emitted `0x56`" — the nested case there already showed `0x54`. This is
disclosed, not smoothed over.

**Disclosed limitation:** `k_far`'s attempt to isolate `off40`-magnitude
as a variable (inflating the CALLEE's own body length while holding
call-site topology at 1) did not actually change the offset, because the
compiler places the callee immediately after an (unchanged) caller
prologue regardless of the callee's own body size — the callee's ENTRY
point offset from the call site is determined by the CALLER's code length
up to the call, not the callee's size. A genuinely different offset-
magnitude/sign probe (e.g. a backward call, or padding BEFORE the call
site) was not attempted; the −84..−154 range naturally spanned by the
other five topologies is the actual tested range for "does offset
magnitude/sign affect `byte+6`."

### 7.2 `byte+5`'s pattern (bonus finding, reported not chased)

`byte+5` is `0x00` in every FLAT (non-nested) topology's call sites,
regardless of call count (1, 2, or 3). In the ONE nested/spilling topology
(`k_nested`'s `mid_fn`), `byte+5` is `0x10` for the FIRST of its two
nested calls and `0x00` for the second — this **exactly reproduces**
EXP-0035's A18 "mid" raw bytes (`aa`/`0x10` then `7c`/`0x00`), now
independently confirmed on M4 with a byte-for-byte matching pattern.
**INFERRED** (not chased further, disclosed as an open item): `byte+5`
plausibly relates to link-register save-slot/frame-state specifically in
a non-leaf (self-spilling) caller's FIRST call vs subsequent calls; not
independently varied past 2 nested calls to confirm whether a 3rd nested
call would also show `0x00`.

### 7.3 Call-nesting depth — the coordinator's "call depth" finite-resource row

14 constructed depths (1,2,3,4,6,8,12,16,24,32,48,64,96,128), each a
distinct chain of `__attribute__((noinline))` MSL functions (generated by
the committed, deterministic `harness/gen_callchain.py`), each REAL
compute dispatch + readback against the exact host oracle
`out[gid]==gid+depth`:

**14/14 exact, zero faults, zero timeouts, zero wrong values, both runs
byte-identical**, across the full tested range 1..128 (a 128× dynamic
range). **No call-nesting-depth limit was found within this range.**
**Driver consequence:** ordinary function-call nesting up to at least 128
levels deep works correctly with no special handling; the safe, honest
statement for anything beyond depth 128 is `UNTESTED`, not "unlimited."

---

## §8 Stencil-value overflow — CLOSED, HW-VALIDATED

### 8.1 Truncation, not clamping — CONSTRUCTED across the full `uint32` range

| requested (`uint`) | observed | `value & 0xFF` | `min(value,255)` | matches |
|---:|---:|---:|---:|---|
| 0 | 0 | 0 | 0 | both (degenerate) |
| 1 | 1 | 1 | 1 | both (degenerate) |
| 127 | 127 | 127 | 127 | both (degenerate) |
| 254 | 254 | 254 | 254 | both (degenerate) |
| 255 | 255 | 255 | 255 | both (degenerate, in-range max) |
| **256** | **0** | 0 | 255 | **truncate ONLY** |
| **257** | **1** | 1 | 255 | **truncate ONLY** |
| **511** | **255** | 255 | 255 | both give 255 (ambiguous point) |
| **65535** | **255** | 255 | 255 | both give 255 (ambiguous point) |
| **4294967295** (`2^32-1`) | **255** | 255 | 255 | both give 255 (ambiguous point) |

The `256`/`257` cases are the DECISIVE disambiguators (chosen precisely
because their low byte is NOT 255, unlike the other overflow values) —
**truncation (`value & 0xFF`) matches exactly; clamp-to-255 is refuted.**
`ushort` source type: `300 → 44` (`300 & 0xFF = 44`, also disambiguating
and confirming truncation), `255 → 255` (in-range control).

**12/12 HW-VALIDATED, exact, both runs.** **Driver consequence:** a
shader-supplied `[[stencil]]` value is silently truncated to its low 8
bits when stored to an 8-bit `Stencil8` attachment — a compiler backend
does not need to insert an explicit clamp/saturate before writing
`[[stencil]]`; the hardware's own store path already truncates, matching
the natural "just take the low byte" behavior of writing a wider value
into a narrower fixed-function stencil buffer.

### 8.2 Legal MSL source types — CONSTRUCTED, one type REJECTED

`uint` and `ushort` both compile and work correctly (§8.1). `int` (signed)
is **rejected at compile time** ("type 'int' is not valid for attribute
'stencil'"), reproduced identically both runs, kept as an isolated
negative control in its own translation unit (Metal compiles one source
file as one compilation unit; the failure would otherwise poison the
working `uint`/`ushort` forms sharing a file). **Driver consequence:** a
compiler backend lowering a stencil-export value must materialize it as
an unsigned (`uint`/`ushort`) MSL type; a signed source value must be
bit-cast/reinterpreted to unsigned before assignment to `[[stencil]]`.

---

## §9 Split prolog/epilog register-crossing mechanics — DEFERRED

Per DRV-ABI-01's own scope ("Specify what a future epilog generator must
emit; do not implement that generator"), constructing and validating an
actual, genuinely-split prolog/epilog pair end-to-end (its own calling
convention discipline, live-range analysis across the split, register
save/restore choreography) is a substantial standalone engineering effort,
not a bounded probe — explicitly out of this experiment's scope, as
pre-registered. §7's CALL-ABI byte decode is the necessary precursor fact
such a split would build on (per EXP-0109 §5.1: the mechanism available is
the ordinary CALL/RETURN ABI, args in `r10,r11,r12,...`, return in `r10`,
non-leaf frames spilling to per-thread scratch) and is now fully closed;
the split-pair construction itself remains a downstream compiler-team
deliverable, not documented further here.

---

## Finite-resource rows (coordinator's mandate, applied to every finite thing touched)

| Namespace/resource | Scope | Encoding | Exact usable range/count (tested) | Holes/reserved | First invalid value | Observed failure mode | Correct driver fallback | Evidence |
|---|---|---|---|---|---|---|---|---|
| Color attachments | per render pipeline | `colorAttachments[0..7]` | **1..8 all HW-render correctly**, independently addressed/correct | none within 0-7 | index **8** (9th, 0-based) | **fatal, uncatchable process abort** the instant the array index is touched — no pipeline/shader involvement needed to trigger it | validate count ≤8 before ever indexing the array | `mrtceil_1..8`, `mrtapiceil_{1,8,9,10}` |
| `MTLBlendFactor` | per color-attachment blend state, src/dst role | `NSUInteger` enum 0-19 | **0..18 all HW-exact** (23/23 incl. dst-role), **19 (Unspecialized) HW-confirmed documented fallback** | none within 0-19 | **20** | **fatal process-aborting assertion** at pipeline creation | never construct outside `[0,19]` | `blendfac_src_*`, `blendfac_dst_*`, `blendfac_src_invalid20` |
| `MTLBlendOperation` | per color-attachment blend state, RGB/alpha independently | `NSUInteger` enum 0-5 | **0..4 all HW-exact** (5/5), **5 (Unspecialized) HW-confirmed documented fallback** | none within 0-5 | **6** | **fatal process-aborting assertion** | never construct outside `[0,5]` | `blendop_*`, `blendop_invalid6` |
| `MTLColorWriteMask` | per color attachment | 4-bit field + Unspecialized sentinel | **bits 0-3 (A,B,G,R) all HW-exact**, **0x10 (Unspecialized) HW-confirmed behaves as All** | bits 5-31 | 0x20 (first bit past documented range) | **silently inert, no crash** (unlike factor/op enums) | safe to leave unrecognized bits set; only bits 0-3 (+0x10 sentinel) are load-bearing | `writemask_*` |
| Blend constant | per encoder, all 4 channels | `float` via `setBlendColorRed:green:blue:alpha:` | **documented legal `[0,1]`; tested `[-0.5,1.5]` — NO clamping observed anywhere in that range** | n/a (continuous) | n/a (no rejection observed even past documented range) | **unclamped pass-through** of out-of-range IEEE floats into the blend math | driver must clamp itself if the target API contract requires `[0,1]` | `blendconst_*` |
| Integer pixel format + blending | per color attachment | boolean × format class | integer formats never blendable | n/a | `blendingEnabled=YES` on any integer format | **fatal process-aborting assertion** (paired with a same-format, blend-disabled POSITIVE control that succeeds) | never enable blending on an integer-valued color format | `fmtreject_r32uint_blend_{off,on}` |
| `[[sample_mask]]` bit width | per fragment invocation, per configured sample count N | 32-bit `uint`, only bits `[0,N-1]` load-bearing | **N=1,2,4 all exactly `popcount(mask & ((1<<N)-1))/N`**, 14/14 cases | bits ≥N | first bit at position N (e.g. `0x4` for N=2, `0x10` for N=4) | **silently inert** — no aliasing/wraparound into lower bits | driver may emit a naive `0xFFFFFFFF`/all-samples mask for any N without masking down | `samplemask_n{1,2,4}_*` |
| `[[stencil]]` value range | per fragment, 8-bit `Stencil8` storage | `uint`/`ushort` legal; `int` REJECTED at compile time | **0..255 exact identity**; **256..2^32-1 truncate to low 8 bits** (`value & 0xFF`), NOT clamp | n/a (continuous input, fixed 8-bit storage) | any value ≥256 (first genuinely-overflowing value tested: 256) | **silent truncation**, no fault, no clamp | driver need not clamp/saturate before `[[stencil]]` assignment — storage itself truncates; must materialize as `uint`/`ushort`, never `int` | `stencilover_*` |
| CALL nesting depth | per compiled function-call chain | ordinary CALL/RETURN, per-thread scratch spill for non-leaf frames | **1..128 all exact, zero faults** (128× range) | untested beyond 128 | not found in tested range | n/a — no failure observed | treat depth ≤128 as safe; depth >128 is `UNTESTED`, not assumed safe or unsafe | `calldepth_1..128` |
| CALL-ABI `byte+6` | per direct out-of-line CALL instruction | 1 byte, position `call_addr+6` | **`0x54` uniformly** across 6 constructed topologies (single/multi/nested call, `off40` range −84..−154) on this M4/toolchain | `0x56` seen only in OLDER (EXP-0035) A18 captures, not reproduced here under any constructed topology | n/a (not an enumerated field with a defined invalid range) | n/a | emit `0x54` for this exact target/toolchain; treat the `0x56` vs `0x54` split as a possible toolchain-version artifact, not call-topology-dependent | `callabi_*` |

---

## What P0.8 / DRV-ABI-01 still needs (explicit, not implied)

This experiment closes seven of EXP-0109's nine named remaining items (1,
3, 5, 6, 7, 8 fully `CLOSED`; 4 `PARTIAL`), closes item 2 by citation to
EXP-0092, and leaves item 9 deferred per DRV-ABI-01's own scope. The row
remains **OPEN**, not `CLOSED`, per `docs/P0-P1-CLOSURE.md`'s six closure
rules — explicitly still required:

1. **Barycentric vertex-order/perspective convention** (§4.2) — the
   reported anomaly (an unrelated shader-output addition changes the
   observed value) needs a dedicated follow-up: a structural byte-diff of
   the two fragment-function variants' compiled code (with vs. without a
   position-echo output) would be the natural next step to determine
   whether this is a genuine compiler/register-allocation quirk or an
   artifact of this experiment's specific probe construction.
2. **MSAA-vs-blend timing** (§1, deferred sub-item) — does the
   fixed-function-shaped blend equation apply pre- or post-resolve for a
   multisampled target? Not attempted; no budget for a dedicated
   per-sample-tile-content probe here.
3. **`MTL4BlendStateUnspecialized`/Metal 4's native dynamic-pipeline-state
   workflow** (§1.12) — a genuinely new, high-value lead surfaced via
   public-header research, corroborating this experiment's structural
   findings but not independently exercised; building an
   `MTL4Compiler`/`MTL4PipelineDescriptor`-based harness is a materially
   larger, separate engineering effort.
4. **Per-sample `[[sample_mask]]`-driven suppression of depth/stencil for
   a SPECIFIC excluded sample** (§3.3) — the uniform-mask-value mechanism
   is proven for color (§6.2); the same mechanism's effect on depth/
   stencil for a genuinely per-sample-divergent mask was not independently
   built.
5. **`byte+5`'s exact semantics beyond 2 nested calls** (§7.2) — plausibly
   link-register-save-slot state in a non-leaf caller, not confirmed past
   a 2-call nested frame.
6. **A18/G17P confirmation** of every M4 fact in this document — all
   `INFERRED`-by-family per `docs/m4-deltas.md`'s ISA-identity finding, not
   independently validated (A18 is hands-off per user directive).
7. **Split prolog/epilog end-to-end construction** (§9) — explicitly
   deferred per DRV-ABI-01's own "specify, do not implement" scope; the
   necessary CALL-ABI precursor (§7) is now closed.
8. The full blend/logic/format-conversion matrix DRV-ABI-01 asks for is
   now SUBSTANTIALLY covered (§1) but not EXHAUSTIVE: not every
   `(factor, factor, op)` triple was constructed (only isolating single-
   factor and single-op cases, plus a handful of combined cases like
   `on_both`); normalized/integer/float FORMAT conversion was spot-checked
   (RGBA16Float, RGBA8Unorm, sRGB) but not exhaustively swept across every
   advertised pixel format.

---

## Clean-room provenance

```text
Clean-room provenance: OWN-SHADER (kernels/*.metal, compiled through the
  public newLibraryWithSource:/newRenderPipelineStateWithDescriptor:/
  newBinaryArchiveWithDescriptor: runtime APIs; harness/*.m authored
  ObjC probes; the unmodified tools/shdump/shdump.m and
  tools/shdump/agxparse.py, invoked read-only) + HW-PROBE (real draws/
  dispatches on the real M4 device via harness/render.m and
  harness/compute_run.m, real readbacks, no splicing) + PUBLIC
  (MTLBlendFactor/MTLBlendOperation/MTLColorWriteMask/MTLPixelFormat enum
  values and MTL4BlendState/MTL4PipelineOptions documentation comments,
  read from the public Metal.framework SDK headers on this host --
  developer-facing C/ObjC header source text, not compiled binaries --
  matching EXP-0109's established precedent for this exact practice; the
  public Metal Shading Language compiler's own diagnostic text, returned
  for OUR OWN source via the public newLibraryWithSource: API; Alyssa
  Rosenzweig's public M1 GPU blog post, gpu_knowledge/blog_posts/
  alyssa_rosenzweig/dissecting-m1-gpu-part4.md).
Inputs inspected: kernels/blend.metal, kernels/fsorder.metal,
  kernels/barycentric.metal, kernels/msaa_diff.metal,
  kernels/samplemask.metal, kernels/stencil.metal,
  kernels/stencil_i32_negative.metal, kernels/callabi.metal,
  kernels/callchain.metal (all authored by us, callchain.metal generated
  by our own committed, deterministic harness/gen_callchain.py); public
  Metal SDK headers (MTLRenderPipeline.h, MTLPixelFormat.h,
  MTL4PipelineState.h, MTLRenderPass.h); NSError/compiler diagnostic
  strings the public compiler returns for our own source; the public
  Rosenzweig blog post cited above.
Apple binary introspection: NONE. No disassembler, decompiler, or binary-
  inspection tool was run on any Apple framework, dylib, kext, firmware,
  or compiler binary. tools/agx-isa/ and tools/agxtest/ were not touched;
  tools/shdump/{shdump.m,agxparse.py} were used unmodified (shdump.m
  rebuilt from its committed source into this experiment's own
  work/bin/<run_id>/; agxparse.py invoked as a subprocess, never edited).
  agxparse.py --extract-hex/--json return only the AGX code-region bytes
  and structural section names of OUR OWN compiled shaders -- no other
  region of any container was read.
Reproduction: python3 run.py --run <id> --out raw/<id> (x2); python3
  verify.py --crossrun raw/m4-20260828-run01 raw/m4-20260828-run02;
  python3 analysis/decode.py raw/m4-20260828-run01; python3 verify.py
  --selftest; python3 verify.py --seqtest; python3 verify.py --smoke
  (before any raw/ artifact exists).
Evidence: raw/m4-20260828-run01/, raw/m4-20260828-run02/
  (00_inputs.json, 01_cases.json, 04_results.jsonl, 05_run_manifest.json
  each); analysis/summary.json, analysis/decode.py;
  harness/fixtures/recorded_reality.json; CAPTURE_CONTRACT.json
  (authored sha256 set, verified unchanged from PRE_GPU through
  RUN02_PRESENT); PROGRESS.md (full pilot log, including two disclosed
  kernel/harness bug fixes, the fatal-process-abort operational hazard,
  and the barycentric anomaly's supplementary-probe root-cause trail).
```

## Files

- `PRE_REGISTRATION.md`, `CAPTURE_CONTRACT.json`, `PROGRESS.md` — frozen
  contract, milestone log, and full pilot/anomaly disclosure trail.
- `casematrix.py` — the 148-case frozen matrix (single source of truth for
  `run.py`/`verify.py`); its module docstring documents the
  fatal-abort-case-ordering mitigation.
- `kernels/blend.metal`, `kernels/fsorder.metal`, `kernels/barycentric.metal`,
  `kernels/msaa_diff.metal`, `kernels/samplemask.metal`,
  `kernels/stencil.metal`, `kernels/stencil_i32_negative.metal`,
  `kernels/callabi.metal`, `kernels/callchain.metal` — authored MSL.
- `harness/gen_callchain.py` — authored, deterministic generator for
  `kernels/callchain.metal` (run once, output committed).
- `harness/struct_extract.m` — generic structural (compile+serialize)
  probe with a fully CLI-configurable blend/format descriptor.
- `harness/render.m` — the main HW-PROBE binary (18 `--mode`s covering
  every family in this experiment).
- `harness/compute_run.m` — generic compute dispatch+readback (used for
  the call-depth sweep).
- `run.py`, `verify.py` — capture driver + standing-gate verifier
  (`verify.py --smoke` added beyond EXP-0109's pattern, wrapping
  `run.py --smoke-only`).
- `raw/m4-20260828-run01/`, `raw/m4-20260828-run02/` — the two official
  captures, 148 cases each, byte-identical.
- `analysis/decode.py`, `analysis/summary.json` — post-capture oracle
  computation (blend-factor/op formulas, barycentric linear/perspective
  models, stencil truncate/clamp models, sample-mask popcount formula),
  no new GPU calls.
- `work/supplementary/bary_diag*.{metal,m}` — the disclosed, non-frozen,
  single-run ad hoc diagnostic probes for the barycentric anomaly (§4.2);
  NOT part of the frozen evidence, kept for reviewer traceability.
- `manifest.json` — target/tool/revision metadata.

## STOPs

No `BLOCKED` state was entered; no host wedge, reboot, or `macvdmtool` use
occurred anywhere in this experiment. Five designed fatal-process-abort
cases (invalid blend factor/op enum values, blend-on-integer-format, and
the two out-of-range MRT-attachment-index probes) executed exactly as
pre-registered, each fully contained to its own subprocess with zero
collateral effect on any other case (mitigated by the case-list ordering
documented in `casematrix.py`'s module docstring and confirmed by the
148/148 byte-identical cross-run result). One genuinely unresolved anomaly
is disclosed, not silently smoothed over: the barycentric
vertex-order/perspective-convention question (§4.2) is left `PARTIAL`,
with the full root-cause investigation trail preserved in `PROGRESS.md`
and `work/supplementary/`.
