# RESULTS — EXP-0095 m4-texture-image-matrix

**STATUS: COMPLETE. Both contracted runs captured, byte-exact repeat verified, all five standing
gates PASS.** Addendum Bundle E (GLTEX-A04/A05/A06/A07, GLIMG-A01/A02) closed for the 85-case
frozen matrix below, M4-target only. `analysis.json`: 83/85 cases `match` their frozen expectation,
0 `deviation`, 2 `abort_confirmed` (the two deliberately-oversized texel-buffer descriptors), and
`repeat_exact: true` — every one of the 85 records is byte-identical between `run01` and `run02`.

Target: **local Apple M4 (G16G), macOS 26.6.2 (25G82), Metal 4, arm64, "Apple M4", Mac16,10**,
public Metal API only. Nothing here is an A18/G17P, Linux, native-command-stream, or raw
ISA-descriptor-splice result. Pinned revision: `b05383c5a40653b1176b0345806af1955bb87659`
(`PRE_REGISTRATION.md`).

## Gate results

| gate | result |
| --- | --- |
| `verify.py --selftest` (PRE_GPU) | PASS |
| `verify.py --seqtest` (PRE_GPU) | PASS — 4/4/5 real subprocess gate checks across PRE_GPU/RUN01_PRESENT/RUN02_PRESENT |
| `verify.py --preflight` | PASS |
| host build (`xcrun clang -fobjc-arc harness/probe.m`) | clean, no warnings |
| non-recorded smoke invocation (`a05_1d_read_first`) | PASS inside both `run.py --execute` invocations (not separately logged; contracted as non-recorded) |
| `raw/m4-20260829-run01` | CAPTURED — 88 files (85 case receipts + `00_inputs.json`/`01_host_build.json`/`run_manifest.json`), no `STOP.json`, 83/85 case processes exit 0 and 2/85 (the descriptor-abort cases) exit with a negative signal (`-6`, SIGABRT) exactly as pre-registered |
| `verify.py --selftest` (RUN01_PRESENT) | PASS — the exact invocation class that quarantined EXP-0075 |
| `verify.py --seqtest` (RUN01_PRESENT) | PASS |
| `verify.py --between-runs` | PASS |
| `raw/m4-20260829-run02` | CAPTURED — same shape, same outcome distribution |
| `analysis.py --run-a run01 --run-b run02 --write` | PASS — `repeat_exact: true`, 83 match / 0 deviation / 2 abort_confirmed |
| `verify.py --captured` | PASS — final gate |

Wall-clock: run01 and run02 each completed in **under 7 seconds** end to end (85 fresh-process
cases against 1x1/4x4-scale textures; Metal compute-library compile dominates per-case cost).

## OBSERVED vs INTERPRETED

Every value below is the literal `out_words`/receipt content from `raw/m4-20260829-run01` and
`raw/m4-20260829-run02` (byte-identical in both). "Interpreted" is this document's reading of that
observation; the raw JSON is the evidence of record.

### GLTEX-A05 — 1D / 1D-array operation matrix

**OBSERVED.** `texture1d`/`texture1d_array` expose, at the public-Metal surface, exactly: implicit-LOD
`sample`, `read`, `write`, and size queries — confirmed by the compile-time absence of any
bias/level/gradient/offset/gather/shadow-compare overload (`PRE_REGISTRATION.md` finding 1; no
frozen case attempts them, since there is nothing to dispatch). Frozen cases: `read` at first/last
texel returns the exact CPU-populated canary (`0xa5000000`, `0xa500000f`); `read` at the first
invalid coordinate (`coord == width`) returns `0x0`; `write` at a legal coordinate changes only that
texel (`k_a05_1d_write_probe`: word3 becomes `0xc0ffee`, words 0-2/4-7 unchanged); `write` at the
first invalid coordinate (`coord == width`) leaves **all 8 inspected texels unchanged**
(`a05_1d_write_oob`: `[a5000000..a5000007]`, no aliasing into any neighbor); `get_width`/
`get_num_mip_levels` return `(16, 1)` exactly; the 1D-array analogues (`read` at layer 0/last/
first-illegal, `get_width`/`get_array_size`) reproduce the identical pattern (`0xb6000000`,
`0xb6000300`, `0x0`, `(16, 4)`). The one non-rule-"a" case, `a05_1d_sample_first`
(implicit-LOD `sample` at `u=0.0` against a raw-bit-pattern `r32float` texture, not a clean float
value) returned `0x0` — expected, since texel 0's bit pattern under `r32float` (populated with the
raw integer `0`) is exactly the float `0.0`; not diagnostic beyond "the sample path executes."

**INTERPRETED.** Native Apple9 1D/1D-array descriptors execute correctly for their full public-Metal
operation set; every out-of-range coordinate (read or write) silently reads/drops to/from zero with
**no fault and no aliasing into a neighboring texel**, matching the project-wide silent-zero pattern
(`docs/isa/register-move-and-liveness.md`). **A negative answer for the missing forms is the
correct closure per the addendum's own escape clause** ("A negative answer is acceptable and
documents that Mesa's existing 1D-to-2D lowering remains necessary" for bias/level/gradient/offset/
gather/shadow-compare on 1D).

### GLTEX-A06 — shadow/cube/cube-array operation matrix

**OBSERVED.** All 8 `MTLCompareFunction`s against the exact-tie case (`ref == storedDepth == 0.5`,
`depth2d_array`) reproduce the documented `ref COMPARISON storedDepth` convention (EXP-0034) exactly:
`less=0, lessEqual=1, greater=0, greaterEqual=1, equal=1, notEqual=0, always=1, never=0`
(`a06_d2darr_compare_suite`). Cube faces (`depthcube`, `ref=0.5`, per-face depth `f/6`): faces 0-3
(`depth<=0.5`) fail, faces 4-5 (`depth>0.5`) pass — `[0,0,0,0,1,1]`, exactly matching the
`ref<storedDepth` derivation (`a06_dcube_faces`). Cube-array layer 0 (`depthcube_array`, `CAL=2`,
per-(layer,face) depth `(l*6+f)/12`): all 6 faces at layer 0 have `depth<0.5` so all 6 fail —
`[0,0,0,0,0,0]` (`a06_dcubearr_faces`). All five sample_compare forms (implicit/level/bias/gradient/
offset) plus `gather_compare` agree with each other at a fixed layer/ref for `depth2d_array`
(`a06_d2darr_forms`: `[0,0,0,0,0,0]`, all fail — `ref=0.6 < storedDepth=0.5` is false, consistently
across every form) and for `depthcube`/`depthcube_array` (implicit/level/bias/gather_compare;
`a06_dcube_forms`, `a06_dcubearr_forms`: `[0,0,0,0]` each, consistently). Array-layer/face boundaries
(first legal / last legal / first illegal) for both `depth2d_array` and `depthcube_array`, tested at
`ref=0.999` (near-maximal, so the tie/pass pattern is diagnostic of whether the layer itself resolved
at all): `a06_d2darr_layer_boundary` and `a06_dcubearr_layer_boundary` both return `[0,0,0]`
uniformly — first legal, last legal, AND first illegal all read as "fail" at this ref, which on its
own does not distinguish "the illegal layer silently zeroed" from "ref=0.999 genuinely fails at every
legal layer too" (see limitation below).

**INTERPRETED.** Depth comparison and gather-compare are executable and exact for `depth2d_array`,
`depthcube`, and `depthcube_array`, across every LOD/offset form Metal exposes for each dimension,
and agree with EXP-0034's compare-function convention with **zero deviation across all runs**. **A
real limitation surfaced in registering this case**: the boundary case's `ref=0.999` was chosen to be
"near-maximal" for a monotonic-depth-vs-ref diagnostic, but it makes the LEGAL layers indistinguishable
from the ILLEGAL one in the captured record (all three positions return "fail" for this compare
function/ref combination, since even the legal last-layer's depth `(DL-1)/DL=0.9375 < 0.999`). This
case is therefore **inconclusive for isolating the illegal-layer value** from this run alone; the
consistent silent-zero pattern established independently by GLTEX-A04's boundary-fetch cases (below,
which DO isolate exact-value legal vs. zero illegal reads) is the load-bearing evidence for cube/
cube-array-adjacent boundary behavior, not this case. Flagged as a design defect for a successor, not
silently smoothed over.

### GLTEX-A04 — array-layer conversion and boundary

**OBSERVED — conversion rule.** MSL exposes no float-layer `sample()`/`read()` overload for
`texture2d_array`/`texturecube_array` (confirmed by the compile-time header inspection recorded in
`PRE_REGISTRATION.md`; every one of the 8 sampling/fetch kernels in `kernels/matrix.metal` takes a
`uint` layer parameter). The frozen probe therefore tests MSL's own `round()` (documented,
round-half-away-from-zero) composed with `uint()`, the software conversion a driver must apply before
calling Metal's entry point: for `2darr_conversion` (array length 8, all 9 candidate layers legal
except none — see correction below), inputs `[2.0, 2.5, 2.4, 2.6, -0.5, -0.0, 6.0, 0.0, 3.0]` produced
layer selections `[2, 3, 2, 3, 0, 0, 6, 0, 3]` — every one is the exact expected `round()` result
(2.5→3, 2.4→2, 2.6→3, ties away from zero), **and both `-0.5` and `-0.0` (which round to `-1.0` and
`-0.0` respectively) select layer 0**, not a huge wrapped index. **Correction to
`PRE_REGISTRATION.md`'s framing:** the `6.0` candidate was mislabeled "illegal" in the shared
`conv_inputs` list's comment — with array length 8 (layers 0-7), `6.0` is legal, and the observed
`layer 6` selection (content `0xd4000006`) is simply correct, not a boundary result. The cube-array
analogue (`CAL=2`, valid layers `{0,1}` only) DOES exercise the illegal branch correctly for the same
9 inputs: `[2.0, 2.5, 2.4, 2.6, -0.5, -0.0, 6.0, 0.0, 3.0]` → `[0, 0, 0, 0, 0xca000000, 0xca000000,
0, 0xca000000, 0]` — every genuinely-illegal rounded index (`2, 3, 2, 3, 6, 3`, all `>= CAL`) reads
`0` (silent zero), and every genuinely-legal one (`-0.5→-1.0 saturates to uint 0`, `-0.0→0`, `0.0→0`,
all layer 0) reads the exact layer-0 canary `0xca000000`.

**OBSERVED — boundary (sample/fetch/gather).** `2darr_boundary_fetch`: layer 0 → `0xd4000000`
(exact), layer 7 (last legal) → `0xd4000007` (exact), layer 8 (first illegal) → `0x0`.
`2darr_boundary_sample`/`_gather` (float format, implicit LOD/nearest): layer 0 and layer 7 both read
back non-`None`-constrained but internally-consistent values equal to `0xd4000000`/`0xd4000007`'s bit
patterns reinterpreted as float texel content, and layer 8 (illegal) returns the SAME value as layer
7 for `sample`/`gather` (`0xd4000007` at all three positions for `_gather`, and `_sample` too) —
**this is the address-clamping behavior of the `sample`/`gather` filtering path specifically**
(`ClampToEdge`-style layer clamp for the filtered/gathered read paths), genuinely different from
`fetch`'s hard silent-zero at the same illegal layer. Cube-array boundary_fetch/`_sample` reproduce
the identical pattern: `fetch` at illegal layer 2 (`CAL=2`) → `0x0`; `sample`/`gather`-style read at
layer 2 → the SAME value as the last-legal layer 1 (`0xca000010`).

**INTERPRETED.** The array-layer float→index conversion a driver must perform before calling Metal's
`uint`-typed entry point is fully characterized: MSL's documented `round()` (ties away from zero)
composed with `uint()` behaves as specified for finite inputs, and **negative values saturate to
index 0 rather than wrapping to a huge unsigned value** (`uint(-1.0)` did not alias any high layer;
this is a genuinely useful, previously-undocumented fact — a driver emitting `uint(round(negativeLayer))`
on this hardware gets a safe clamp-to-zero, not undefined-looking corruption). **The most important
finding in this item: `fetch` (texel-fetch-style `read()`) and `sample`/`gather` (filtered/footprint
reads) DIVERGE at the illegal-layer boundary** — `read()` silently zeroes, while `sample()`/`gather()`
clamp the layer index to the last legal layer (exactly the OpenGL/Vulkan/D3D `ClampToEdge`-style array
convention for the filtered access path). A driver must NOT assume one boundary rule for all three
access forms. **Raw ISA-level question left `UNKNOWN`, deferred to an assembler-based successor**
(declared in `PRE_REGISTRATION.md`): whether the underlying hardware sample instruction's
extra-coordinate operand is natively float-typed is not answerable from the public-Metal surface, and
per the EXP-0099 caveat, closing it later will need care around the `srcA_reg`/`srcB_reg`
retention-bit decoding bug — irrelevant to the software-conversion finding above, which stands on its
own public-Metal evidence.

### GLTEX-A07 — texel-buffer length, range, offset, and exhaustion semantics

**OBSERVED — element count boundary (5 texel sizes: 1/2/4/8/16 bytes, `TN=64`).** `read` at element 0
and element 63 (last legal) returns the exact per-format CPU-populated content for every one of the 5
formats (`r8uint`: `0x00`/`0x3f`; `rg8uint`/`rgba8uint`: same low-byte pattern; `rgba16uint`:
`0x0000`/`0x003f`; `rgba32uint`: `0xaa000000`/`0xaa00003f`, the only format wide enough to carry the
full marker). `read` at element 64 (first invalid) returns `0x0` for **every** format, uniformly.
`write` at elements `{0, 63, 64}` in one dispatch, writing the value `0xC0FFEE`: the readback at
elements 0/63 shows the value **clamped to the channel's maximum representable value**, not
truncated — `0xff` (8-bit formats), `0xffff` (`rgba16uint`), `0xc0ffee` unchanged (`rgba32uint`, which
fits). `get_width()` returns exactly `64` (`a07_tb_size`).

**OBSERVED — descriptor width ceiling (family `a07_descriptor`, no library compile, descriptor
creation only).** Width `2^28 = 268,435,456` is **accepted** for both a 1-byte texel format
(`bytes_needed = 268,435,456`) and a 16-byte texel format (`bytes_needed = 4,294,967,296`, i.e. 4
GiB) — the ceiling is a flat **element-count** limit, not a byte-length limit, confirmed independently
at two very different byte widths. Width `2^28 + 1` **aborts the process** (`SIGABRT`, receipt exit
`-6`, reproduced byte-identically in both runs) for both texel sizes, before any GPU command is
submitted — this is `-[MTLTextureDescriptor validateWithDevice:]`'s own assertion, uncatchable by
`@try/@catch`.

**INTERPRETED.** The maximum texel-buffer element count on this hardware/Metal stack is exactly
`2^28` for every texel size tested (1/2/4/8/16 bytes); `RGB32` (a 12-byte texel) is **not
representable at all** — no `MTLPixelFormatRGB32*` constant exists in the public `MTLPixelFormat`
enum (a structural/API fact, established without any hardware probe), so the OpenGL
`GL_MAX_TEXTURE_BUFFER_SIZE`/RGB32 question resolves as: **RGB32 texel buffers have no native
Apple9/Metal representation and must be lowered** (e.g. to `RGBA32` with a padded/ignored alpha
channel, or three independent `R32` reads) by the OpenGL translation layer. The first-invalid-element
read is a uniform silent zero across every representable texel size; a first-invalid-element or
boundary write **clamps the stored value to the channel's representable range** rather than
truncating bits — a driver emitting an out-of-representable-range integer store must not assume
low-bits truncation. **`(range field max + 1) / texel_size` did NOT hold as a literal formula**: the
element-count ceiling (`2^28`) is constant across texel size, so it is the WIDTH field (not a
byte-length field) that is capped — this falsifies the addendum's own stated key-falsifier framing
("largest legal texel-buffer element count... failing to match `(range field max + 1) / texel_size`"
in exactly the way flagged as "a genuine surprise worth its own follow-up": the count is
**texel-size-independent**, not texel-size-scaled from a fixed byte range.

### GLIMG-A01 — image load/store/query operation and coordinate matrix

**OBSERVED.** `r32uint` image store→load round trips exactly on every non-multisample dimension
tested: 1D (`0x1d000001`), 1D-array (`0x1d000002`), 2D (`0x2d000001`), 2D-array (`0x2d000002`), 3D
(`0x3d000001`), cube (`0xcb000001`), cube-array (`0xcb000002`), buffer (clamped to `0xff` — an
`r8uint` texel, consistent with GLTEX-A07's clamping finding). Every associated size query (width/
height/depth/array-length as applicable) returns the exact created dimension. **A same-thread
same-invocation write immediately followed by a read of the same texel returns 0 (not the written
value) unless an explicit `t.fence()` call intervenes** — discovered mid-build (see
`PRE_REGISTRATION.md` finding 7) and now load-bearing in every dimension case above; this is a
genuine, previously-undocumented Apple9/Metal same-thread coherency requirement worth flagging to the
implementation team explicitly. 2D multisample and 2D multisample-array images (`sampleCount=4`)
**compile, create a pipeline, and dispatch successfully** with `access::read` (`get_num_samples`
returns `4`, `get_array_size` returns `2` for the array form; the read content itself is `0`, the
storage-mode default, since MS textures have no `access::write`/`replaceRegion:` populate path and
none was attempted) — a clean **positive** result: MS image reads are NOT rejected. Format-class
sweep on 2D (`r32float`, `r8unorm`, `r8snorm`, `r16uint` exact `4321`, `r16sint` exact `-1234`,
`rgb10a2unorm`): every format's image store/load round trip **executes** without rejection (the DRV-FMT-01
conversion-exactness question is out of this item's scope per its own note, and per `EXP-0079`/
`EXP-0064`). OOB coordinate reads (2D at `x==width`, `y==height`, both; cube at `x==width` within a
valid face, and face index `6`, the first invalid face) all return `0`. An OOB write followed by a
full in-bounds readback of all 16 legal texels shows **zero corruption** — every legal texel stays at
its pre-write default (`0`). A single-channel `r32uint` image written with all four `uint4` lanes
populated (`0x99999999, 0x11111111, 0x22222222, 0x33333333`) reads back `.x = 0x99999999` exactly and
`.y/.z/.w = 0` — **the other three written components are not stored at all** for a single-channel
format (not merely unread — a genuinely separate readback kernel confirms them absent). An unbound
texture argument (declared, never bound at dispatch, no debug/validation layer): a read returns `0`;
a write is silently absorbed (the dispatch still completes cleanly, `command_buffer_status=4`). Two
texture arguments aliasing the same underlying `MTLTexture` (one `read_write`, one `read`, in one
kernel invocation): a fenced write is visible through the OTHER handle in the same dispatch
(`0xa11a5000` read back exactly) — resource-identity-based coherency, not handle-based.

**INTERPRETED.** The full image instruction path (load/store/size query) works correctly across every
dimension GLIMG-A01 asks for except the two explicitly out-of-scope forms (see below); multisample
image access is native, not emulated or rejected, at least for reads. The single-channel-format
partial-write finding is a concrete, actionable fact: **a compiler lowering GLSL's `imageStore` with
a vec4 payload onto a single-channel destination format must not assume the other 3 components are
silently ignored on the SOURCE side and preserved on read-back — they are genuinely dropped at the
store, and reading them back yields zero, not garbage or the last-written value.** Unbound-image
robustness matches the silent-zero/silent-drop pattern seen everywhere else in this matrix.

### GLIMG-A02 — image selector/descriptor capacity and atomic integration

**OBSERVED — direct-binding path.** The 128-entry `[[texture(N)]]` ceiling (127 legal, 129 a
compile-time error) reconfirmed under the frozen contract: `read` at index 0/63/127 (a 128-argument
kernel, `kernels/direct128.metal`) returns the exact canary (`0xd00d0000`, `0xd00d003f`,
`0xd00d007f`); at `idx=UINT32_MAX` (no compile-time branch matches any of the 128 declared indices)
returns the kernel's own not-matched sentinel `0xffffffff` — **structurally distinct from a runtime
hardware boundary**: the direct path's "selector" is chosen by the Metal compiler at shader-compile
time, not by a runtime field, so there is no runtime out-of-range HARDWARE behavior to observe here
(unlike EXP-0083's spliced runtime byte selector). `write` (128 `access::write` slots, NOT subject to
the narrower `read_write` cap) at index 5, readback of the first 8: only index 5 changed
(`0xc0ffee`), the other 7 exact original canaries unchanged. **`access::read_write` (needed for
atomics) is capped at exactly 8 slots regardless of the 128-entry table** — reconfirmed: `atomic_fetch_add`
at the last legal `read_write` slot (index 7, a `texture_buffer<uint>`) returns the correct pre-add
value `7`; at index 8 (no 8th `read_write` slot exists — again a compile-time, not runtime, ceiling)
returns the kernel's own sentinel `0xffffffff`.

**OBSERVED — bindless (argument-buffer) path, `CAP=256` declared entries, `K=8` populated canaries —
the genuine runtime-selector analogue of EXP-0083's methodology.** `read` at index 0 (first populated)
→ exact canary `0xb0000000`; index 7 (last populated) → exact canary `0xb0000007`; index 8 (first
in-array hole, never encoded) → `0x0`; index 255 (last in-array hole) → `0x0`; index 256 (first index
beyond the declared array bound) → `0x0`; index 511 → `0x0`; **index 512 (`= 2×CAP`, the mirroring
probe in the EXP-0083 tradition) → `0x0`, NOT the index-0 canary** — **no period-256 mirroring was
observed**, in direct contrast to EXP-0083's finding that the buffer base-slot selector mirrors
128-255 onto 0-127. Index `0xFFFFFFFF` (the most extreme selector) → `0x0`. `write` (`0xc0ffee`) at
each of the same four representative indices (first-populated, first-hole, first-OOB, mirror-probe),
followed by an independent CPU-owned readback of all 8 canary textures: writing to index 0 changes
**only** canary 0 (the other 7 exact, unchanged); writing to index 8/256/512 (hole/OOB/mirror) leaves
**all 8 real canaries unchanged** — the out-of-range write is silently dropped, never aliases a real
entry. `atomic_fetch_add` (native, `texture_buffer<uint, access::read_write>` array entries) at the
same four indices: canary readback after an in-range atomic at index 0 confirms `1` at slot 0 and the
untouched `2..7` ramp at the others; after an out-of-range atomic (hole/OOB/mirror) all 8 canaries
read their untouched initial ramp `[0,1,2,3,4,5,6,7]` — **no corruption from the out-of-range atomic
either** (the atomic's own previous-value return for these four cases is not captured — a declared
limitation, see `PRE_REGISTRATION.md`).

**INTERPRETED.** Two structurally different "capacity" answers, both closed: the **direct** binding
table is a Metal-compiler-enforced ceiling of 128 texture-argument entries per compute function
(with a narrower, separate 8-entry ceiling specifically for `access::read_write`/atomics — the actual
resource namespace an image consumes depends on its access qualifier, not just its dimension); the
**bindless/argument-buffer** path is the documented software fallback beyond that ceiling, genuinely
scales past 128 (feasibility to 4096 in pre-freeze exploration; captured boundary behavior to `CAP=256`
here), and behaves identically to the direct path's silent-zero/silent-drop pattern at every hole and
out-of-bounds index for load, store, AND atomic access — **critically, with no aliasing and no
mirroring**, unlike EXP-0083's buffer base-slot selector. This is a genuine, load-bearing DIFFERENCE
between the two resource namespaces that a driver must not conflate: **a wrong/overflowing buffer
base-slot silently ALIASES a real slot (EXP-0083); a wrong/overflowing bindless image index silently
READS ZERO / DROPS THE OPERATION, with no aliasing (this experiment).** The addendum's own key
falsifier — "an image-selector count exceeding the direct texture selector ceiling... without a
documented bindless fallback" — does NOT occur: the bindless fallback exists, is exercised, and is
documented above.

## Finite-resource table

| resource | exact representation | usable range (observed) | holes/reservations | first-invalid value | observed failure mode | driver fallback |
| --- | --- | --- | --- | --- | --- | --- |
| 1D/1D-array texel coordinate | `uint` MSL coordinate, hardware width unestablished (public-Metal only) | `[0, width-1]`; tested width 16 | none observed | `coord == width` | silent zero (read), silently dropped (write), no aliasing | none needed — matches ordinary bounds-checked addressing |
| depth array-layer/cube-face index (sample_compare/gather_compare) | `uint` layer index | `[0, arrayLength-1]` × 6 faces | none observed | boundary case inconclusive at `ref=0.999` (see GLTEX-A06 limitation) | not independently isolated this run | reuse GLTEX-A04's fetch-path silent-zero finding as the safe assumption pending a successor probe |
| color array-layer index, `fetch`/`read()` path | `uint`, driver must `round()`+cast from a GLSL float layer | `[0, arrayLength-1]` | none observed | `layer == arrayLength` | silent zero, no aliasing | round-half-away-from-zero (MSL's own `round()`), negative saturates to 0 |
| color array-layer index, `sample`/`gather` (filtered) path | same `uint` index | `[0, arrayLength-1]` | none observed | `layer == arrayLength` | **clamps to the last legal layer** (NOT zero — diverges from `fetch`) | clamp-to-edge on the array axis for filtered reads only |
| texel-buffer element count | flat element-count field, texel-size-independent | `[0, 2^28]` (268,435,456), uniform across 1/2/4/8/16-byte texels | none observed; RGB32 (12-byte texel) has no representable format at all | `width == 2^28 + 1` | **process abort (SIGABRT)** at descriptor-creation time, before any GPU submission; uncatchable | never construct a descriptor above `2^28`; treat as a hard host-side precondition, not a recoverable API error |
| texel-buffer element read | — | `[0, width-1]` | none observed | `element == width` | silent zero | none needed |
| texel-buffer/image store value (narrow uint channel) | channel bit width per format (8/16/32) | full representable range of the channel | none | value exceeding the channel's max | **clamped to the channel maximum**, not truncated | do not rely on low-bits truncation for an intentionally-masked store |
| direct `[[texture(N)]]` argument table (read/sample or write access) | Metal-compiler-enforced, compile-time selector | `N ∈ [0, 127]` (128 entries) | none | `N == 128` | MSL **compile-time** error ("out of bounds"), not a runtime fault | stay ≤ 128 direct texture arguments per function; use bindless beyond that |
| direct `[[texture(N)]]` argument table, `access::read_write` (atomics) | Metal-compiler-enforced, compile-time selector, narrower | `N ∈ [0, 7]` (8 entries) | none | `N == 8` | MSL **compile-time** error, independent of the 128-entry ceiling | at most 8 simultaneous read_write/atomic image arguments per function; route more through bindless |
| bindless (argument-buffer) image index | genuine runtime `uint` selector, driver-declared array size `CAP` | `[0, K-1]` populated in this experiment (`K=8` of a declared `CAP=256`) | `[K, CAP-1]` = never-encoded holes, behave identically to true OOB | `index >= CAP` (also holes `< CAP`) | silent zero (load); silently dropped, no aliasing (store, atomic) | safe to leave entries unbound; no mirroring/aliasing risk observed, unlike the buffer base-slot family (EXP-0083) |

## Which matrix cells were NOT exercised (declared, per `PRE_REGISTRATION.md`)

- Fragment-stage (real-derivative) LOD/minification behavior for any dimension — this matrix is
  entirely compute-stage (implicit LOD pinned to 0, already an established fact reused, not
  re-derived, here).
- The full 96-format `MTLPixelFormat` set (`docs/descriptors/format-table.md` §2d) for image
  load/store — GLIMG-A01 tests a representative 6-format class sweep on 2D plus a uniform `r32uint`
  probe across every dimension, not every format on every dimension.
- Raw ISA-level descriptor/selector injection (the assembler/splice path) for any capacity boundary,
  and specifically the raw-instruction float-vs-integer typing of the array-layer coordinate register
  (GLTEX-A04) — everything here stays on the public-Metal behavioral surface per Bundle E's own "no
  assembler" default, and per the EXP-0099 register-decoding caveat this would need care to close
  correctly later.
- Multi-thread/cross-thread contention on any atomic path — every atomic case here is a single-thread
  `dispatchThreads(1,1,1)` correctness probe, not a concurrency/throughput test.
- Bindless capacity beyond the declared `CAP=256` array (pre-freeze exploration fed feasibility to
  N=4096, not captured boundary evidence).
- GLTEX-A06's array-layer/face boundary case is inconclusive (see the limitation recorded in that
  section) — a successor should re-register it with a `ref` value that distinguishes the legal
  last-layer/face from the illegal one.
- 2D-multisample-ARRAY × cube/cube-array combinations, sparse/tile residency, and every GLIMG-A01
  boundary sub-case beyond 2D/cube (OOB/partial-write/unbound/alias tested only on those two dims).
- `a07_tb_*_write3` and the non-`first_populated` `a02_bindless_write_*`/`a02_bindless_atomic_*`
  cases write/atomic all three (or the one non-zero) boundary indices in a single dispatch rather
  than isolating one boundary value per process (declared limitation, `PRE_REGISTRATION.md`).

**Recommended successor experiments:** (1) a fragment-stage variant of GLTEX-A05/A06 for real
derivative-driven minification; (2) a corrected GLTEX-A06 boundary case with a `ref` that separates
legal-last from illegal-first; (3) an assembler-based follow-up on the array-layer coordinate
register's raw type, coordinated with EXP-0099's register-decoding fix; (4) a wider GLIMG-A01 format
sweep if driver work surfaces a specific format/dimension combination of interest.

## Clean-room provenance

Clean-room provenance: HW-PROBE / OWN-SHADER / PUBLIC
Inputs inspected: authored MSL (`kernels/matrix.metal`, `kernels/direct128.metal`), authored ObjC
harness (`harness/probe.m`), authored Python runner/verifier/analysis/generator; public
`MTLPixelFormat` enum and MSL public standard-library header syntax consulted for correct public API
calling conventions only (never for a hardware or algorithmic fact)
Apple binary introspection: NONE — no Apple binary, archive, BO, private interface, or ISA
assembler/disassembler was ever touched by this experiment
Reproduction: the command sequence in `README.md`
Evidence: `raw/m4-20260829-run01`, `raw/m4-20260829-run02` (88 files each), `analysis.json`
(`repeat_exact: true`, 83 match / 0 deviation / 2 abort_confirmed), `manifest.json`
