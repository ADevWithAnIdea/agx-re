# RESULTS — EXP-0134-m4-lossless-compression

**Target:** Apple M4 (G16G), 10 GPU cores, macOS 26.6.2 (25G82), Metal 4. **M4 only — no
A18 Pro claim anywhere in this document** (CLAUDE.md 2026-08-27 target discipline).
**Two official captures**, `m4_20260828_run01` / `m4_20260828_run02`, byte-identical on
every gated field (`harness/verify.py --captured`: `issues_total: 0`). 83 cases: 79 PASS,
2 FAIL (a genuine, reproduced formula-boundary finding — not a defect, see §2.4), 2 N/A
(memoryless resources reject the descriptor-capture bind step — a method limitation, not
a claim about memoryless compression). All five standing gates: PASS (§6).

Convention: OBSERVED = read directly off hardware/dumped bytes. INTERPRETED = our reading
of what the observation means. Evidence label per CODEX: `DATA-TRACE-VALIDATED` unless
otherwise marked (every claim below rests on the descriptor bits and/or aux bytes captured
from our own process's registered GPU buffer objects via the read-only `tools/iotrace`
interposer, cross-run reproduced).

---

## 1. Eligibility matrix (Group ELIG, 31 cases)

**OBSERVED** (`word1` bit27 = compression flag; every probe texture carries `ShaderRead`,
see PRE_REGISTRATION.md scope note):

| usage | 32×32 (eligible size) | 8×8 (sub-threshold) |
|---|---|---|
| `read` | **compressed** | not compressed |
| `read,rt` | **compressed** | not compressed |
| `read,write` | not compressed | not compressed |
| `read,rt,write` | not compressed | not compressed |
| `read,pfview` | **not compressed** | not compressed |
| `read,rt,pfview` | **not compressed** | not compressed |

**INTERPRETED.** `MTLTextureUsagePixelFormatView` **alone** (without `ShaderWrite`)
already disables compression. This resolves an ambiguity in `docs/descriptors/README.md`'s
existing wording ("ShaderWrite AND PixelFormatView disable lossless compression"), which
could be read either as a conjunction requirement or as two independently-disabling bits.
**It is the latter: `ShaderWrite` and `PixelFormatView` each independently disable
compression**, `RenderTarget`/`ShaderRead` never do. (H-E1 confirmed; falsifier not observed.)

**Storage mode** (`elig_storage`, 4 cases): `StorageModePrivate` shows identical
compression behavior to `StorageModeShared` at the same usage (`read` → compressed;
`read,write` → not compressed). `StorageModeMemoryless` creation succeeds
(`TEX_CREATE_OK=1`) but the compute-kernel bind step used to capture the descriptor
**fails** (`BIND_STATUS=5`, command-buffer error) for both `read` and `read,rt` usage —
a standalone compute kernel cannot read a memoryless resource outside the tile pipeline.
**Memoryless compression eligibility is UNKNOWN via this method** (recorded `N/A`, not
inferred either way — H-E2's storage-independence claim is confirmed for Private only).

**Texture type** (`elig_type`, 9 cases): array (2 layers), cube, 3D (depth 4), and MSAA
(2×/4×) all compress at a 32×32-per-plane (64×64 for MSAA) eligible size and do not at an
8×8/sub-threshold per-plane size — reconfirms the per-plane W≥16∧H≥16 rule already
established on M4 (EXP-M4-07). (Array's measured `aux_bytes`/`main_bytes` are unreliable —
its main image, 8192B across 2 layers, is below the ~16KiB dedicated-BO threshold, §2.2 —
only the boolean compression flag is trustworthy for that case.)

**Linear (buffer-backed)** (`elig_linear`, 2 cases): a 64×64 buffer-backed texture
**never compresses**, at `usage=read` or `usage=read,rt`, despite being well above the
size threshold. (H-E4 confirmed.)

**Size boundary** (`elig_boundary`, 4 cases, non-square reconfirmation): 16×16 compresses;
15×15, 16×15, 15×16 do not — the W≥16∧H≥16 rule is genuinely per-dimension, not
per-area. (H-E5 confirmed.)

---

## 2. Aux geometry (Group AUX, 27 cases)

### 2.1 `numTexels/32` formula — 13/15 exact matches

7 formats spanning bpp 1/2/4/8/16 (float/unorm/uint families), 2 tile-aligned sizes each
(chosen so the main image clears the empirically-discovered dedicated-BO threshold, §2.2)
all match `aux_bytes = W·H/32` **exactly**: r8unorm, r16float, rgba8unorm, rgba16float,
r32uint, rgba8uint at every tested size; rgba32float only at 64×64 and above (see §2.4 for
the 32×32 exception). MSAA (§2.3) extends the same formula with an extra `·N` factor.

### 2.2 Dedicated-BO vs. shared-heap suballocation (a driver-irrelevant Apple-allocator
artifact, discovered during pipeline validation — PROGRESS.md M2)

**OBSERVED.** A compression-eligible texture whose padded main image is **≥ ~0x4000
(16KiB)** bytes gets its own dedicated GPU buffer object: the descriptor's base VA equals
the BO's own GPU VA exactly, and `BO_size = main_bytes + aux_bytes` to the byte (confirmed
at every §2.1 size). Below that, the texture is **suballocated from a shared heap BO**
alongside other small objects, so "whole-BO-size minus offset" no longer measures the aux
region alone.

**INTERPRETED.** This is a property of Apple's own private CPU-visible small-object
allocator, observed as a side effect of our DATA-TRACE method — **not** a hardware fact or
a UAPI requirement a third-party driver must replicate; the driver owns its own allocator
and only needs the *logical* aux-size formula (§2.1), which holds regardless.

### 2.3 MSAA auxiliary ratio — `aux_bytes = W·H·N/32` (the row's specifically-requested,
previously-unpinned fact)

| format | N | main bytes | aux bytes | `W·H·N/32` |
|---|---|---|---|---|
| rgba8unorm 64×64 | 1 | 16384 | 128 | 128 |
| rgba8unorm 64×64 | 2 | 32768 | 256 | 256 |
| rgba8unorm 64×64 | 4 | 65536 | 512 | 512 |
| r16float 128×128 | 1 | 32768 | 512 | 512 |
| r16float 128×128 | 2 | 65536 | 1024 | 1024 |
| r16float 128×128 | 4 | 131072 | 2048 | 2048 |

**OBSERVED**, exact match at every point, both formats. **INTERPRETED**: aux scales
**linearly with sample count** — one state byte per 8×4-**per-sample** block, i.e. the
same divisor-32 rule as the non-MSAA case extended to `numTexels·N`, not a fixed
per-pixel-regardless-of-samples allocation. This resolves `docs/tiling/README.md` §4.5's
open item ("the exact per-sample MSAA aux ratio is not fully pinned").

### 2.4 Minimum aux-allocation floor at bpp16 (finite-resource mandate; a genuine,
reproduced formula boundary — not a harness defect)

| case | w×h | bpp | formula predicts | measured | 
|---|---|---|---|---|
| `a_bpp_rgba32float_32` | 32×32 | 16 | 32B | **128B** |
| `a_bpp_rgba32float_32x64` | 32×64 | 16 | 64B | **128B** |

Both cases are dedicated-BO (main image exactly 16384/32768B, at or above the §2.2
threshold — this is not the shared-heap artifact). Both clamp to the **same** 128-byte
value despite different formula predictions (32B and 64B) — this rules out "always ×4 the
formula" and supports a **hard ~128-byte minimum aux-allocation floor** that only bites at
bpp16 among the formats tested (bpp≤8 dedicated-BO sizes in this matrix always predict
≥128B already, so the floor is invisible there). **INTERPRETED, `PARTIAL`**: a driver
computing aux allocation size should take `max(numTexels/32, 128)` bytes, not the raw
formula, at minimum for bpp16; whether the floor is a fixed 128B constant or itself scales
with bpp/tile size is not established beyond these two points (both bpp16) — flagged as a
narrow, reproducible, but not fully generalized finding. Both cases are gated `FAIL` in
`raw/*/02_gated.jsonl` **by design** (`run.py`'s verdict logic is strictly formula-based;
the mismatch itself is the finding — see `CAPTURE_CONTRACT.json`'s
`known_expected_anomalies`).

### 2.5 Finite-resource: smallest-eligible allocation footprint (`aux_alloc_floor`, replicate method)

8 identical textures per case; base-VA spacing is perfectly uniform in every case
(`deltas_equal: true`), giving a direct HW measurement of total per-object footprint:

| format | w×h | main | formula aux | main+aux | **measured footprint** | `round_up(main+aux, 256)` |
|---|---|---|---|---|---|---|
| rgba8unorm | 16×16 | 1024 | 8 | 1032 | **1280** | 1280 ✓ |
| rgba8unorm | 20×20 (padded 32×32) | 4096 | 32 | 4128 | **4352** | 4352 ✓ |
| r8unorm | 16×16 | 256 | 8 | 264 | **512** | 512 ✓ |
| rgba32float | 16×16 | 4096 | 8 | 4104 | **4352** | 4352 ✓ |

**INTERPRETED**: the shared small-object heap (§2.2) rounds each compressed texture's
`main+aux` footprint up to a **256-byte allocation granule** — consistent across all 4
independent (format, size) configurations. Same caveat as §2.2: an Apple-allocator
artifact, not a portable requirement; the *logical* aux size (`numTexels/32`, floored per
§2.4) is what a driver needs.

### 2.6 Compression × mipmaps (`aux_mip`, 2 cases)

64×64 rgba8unorm, 1 level vs. 4 levels (64/32/16/8): aux grows from **128B → 384B**
between the two chains — directly confirms aux is **not** limited to the base level and
grows with chain length, consistent with EXP-O2G's A18 finding of one contiguous aux
covering the whole mip chain (not redone in full here; this reconfirms the qualitative
claim on M4). **PARTIAL / UNKNOWN**: the exact 384B figure matches neither a naive
per-level-slot-sum-then-`/32` (predicts 170B) nor the single-level formula applied to the
`main_bytes` window measured between base VA and secondary VA (21760B main → predicts
680B) — the precise mip-chain aux-total arithmetic is **not** re-derived by this
experiment (out of scope; `docs/tiling/README.md` §3/§5 owns the detailed mip-packing
formula) and is flagged `UNKNOWN` pending a dedicated follow-up, rather than asserting an
unverified number.

---

## 3. State ↔ pattern correlation (Group STATE, 16 cases)

**OBSERVED** aux state byte(s) per pattern (rgba8unorm 64×64 unless noted; "head" = first
bytes of the 128-byte aux array, Morton-of-blocks order per EXP-0017):

| pattern | aux state |
|---|---|
| uniform clear, black (0,0,0,0) | **all `0x03`** |
| uniform clear, white (1,1,1,1) | **all `0x03`** |
| uniform clear, mid-gray (0.5,0.5,0.5,1) | **all `0x03`** |
| uniform clear, arbitrary (0.2,0.7,0.4,1) | **all `0x03`** |
| smooth gradient | **all `0x15`** |
| high-entropy noise | **all `0x7f`** |
| split (left constant / right noise) | clean block-aligned runs of `0x03` / `0x7f`, transition exactly at the block-Morton boundary (full 128-byte dump verified, not just the head) |
| single-outlier, small color delta (ΔR≈0.05) at (4,2) in a gray block | that block → **`0x10`**, rest `0x03` |
| single-outlier, large color delta (ΔR≈0.5, ΔG/ΔB≈−0.5) at (4,2) | that block → **`0x21`**, rest `0x03` |
| single-outlier, same large delta, at corner (0,0) | that block → **`0x22`**, rest `0x03` |

**INTERPRETED.**
- **A uniform block and a noise block land in unambiguously different states** (`0x03` vs.
  `0x7f`), and a smooth gradient is a **third**, separate state (`0x15`) — reconfirms
  EXP-0017 with a fresh, independently-reproduced (cross-run byte-identical) capture.
- **The uniform/"constant" code is content-independent**: true black, true white,
  mid-gray, and an arbitrary color all read the identical `0x03` — there is **no distinct
  "fast-clear-to-zero" code** among the values tested (H-S2 confirmed as stated: no split
  by specific color, at least among these four).
- **A single-texel outlier in an otherwise-uniform block gets its own, non-`{0x03,0x15,
  0x7f}` code — confirming a real fourth (or more) state exists beyond simple
  uniform/gradient/raw** (H-S3 confirmed: the codec has at least one more discrete mode
  for "mostly-constant-with-a-defect" content, which is exactly the kind of "does the HW
  support a limited-palette/partial mode" question the row asks). **However the outlier
  code is NOT one fixed value** — it changed with delta magnitude (`0x10` small delta →
  `0x21` large delta) **and** with position (`0x21` at (4,2) → `0x22` at (0,0), same
  delta). This means the aux byte is carrying more than a coarse mode selector for this
  content class; we do **not** attempt to decode what the extra bits mean (that would
  cross into the forbidden bitstream-recovery territory per PRE_REGISTRATION's clean-room
  boundary) — the driver-relevant fact is: **a single differing texel is enough to move
  a block out of the fully-compressed-uniform state**, and the exact resulting byte value
  is content-and-position-sensitive and must be treated as opaque.

### 3.1 Format independence — **refuted** (`state_format_repeat`, 6 cases)

| format | clear (uniform) | gradient | noise |
|---|---|---|---|
| rgba8unorm (bpp4) | `0x03` | `0x15` | `0x7f` |
| r32uint (bpp4) | `0x03` | `0x0d` | `0x25` |
| rgba16float (bpp8) | `0x07` | mixed, format-specific (non-uniform run) | mixed, format-specific (non-uniform run) |

**INTERPRETED, H-S4 refuted.** The **fully-uniform** code is stable across rgba8unorm and
r32uint (`0x03`, same bpp class) but **differs** for rgba16float (`0x07`, a different bpp
class) — so even the "constant" code is not universally format-invariant, only
same-bpp-class-invariant among the formats tested. The **gradient/noise** codes differ
between rgba8unorm and r32uint despite identical bpp and identical block geometry —
**the state-byte alphabet is not a small universal enum with fixed cross-format meaning.**
This is a materially different (and more cautious) conclusion than a naive reading of
EXP-0017's single-format result would suggest, and is the reason `docs/tiling/README.md`
should describe the codec's discrete-state existence and per-run reproducibility, but
**not** publish a fixed "0x03/0x15/0x7f means X" table as format-general.

---

## 4. CPU access and PBE (render-target) interaction (Group CPU, 9 cases)

**`replaceRegion:` (public Metal CPU-write API), OBSERVED, two-dump before/after
(`cpu_replace`, 3 cases):**

- **Before any GPU render** (`c_replace_before_write`): `replaceRegion:` succeeds
  (`CPU_OP_OK=1`) on a never-rendered compression-eligible texture; its aux reads all
  `0x7f` (raw) both before and after — an untouched/uninitialized resource is not
  presented as falsely "compressed."
- **After a gradient render, 8×8 sub-region replaced** (`c_replace_after_gradient`):
  before = aux all `0x15` (gradient, matching §3); **after = the first 8 aux bytes flip to
  `0x7f`, the rest stay `0x15`** — replacing raw content in an 8×8-texel corner (which
  spans only 2 of the 8×4-texel blocks physically) invalidated **8** aux-block entries, a
  wider neighborhood than the minimally-touched region. `replaceRegion:` succeeded
  (`CPU_OP_OK=1`).
- **Full-texture replace** (`c_replace_full`): before = all `0x15`; after = **all `0x7f`**
  (the whole image becomes "raw," consistent with overwriting every block with
  non-gradient-shaped bytes).

**INTERPRETED (H-C1, H-C2).** `replaceRegion:` **works** on a compression-eligible
resource in every tested state (untouched, mid-compressed, before or after GPU use), and —
critically for correctness — **the aux state is kept synchronized with the new content**:
CPU-written bytes that do not fit the gradient codec are correctly marked raw (`0x7f`),
not left stale. **A driver does not need to manually manage aux invalidation when using
`replaceRegion:`** on a compression-eligible texture; Metal's public CPU-write path
re-derives compression state itself. The touched-region aux invalidation is **conservative
(wider than the minimal touched blocks)** — a driver should not assume `replaceRegion:`
invalidates only the exact blocks a byte-level accounting of the region would predict.

**`getBytes:` (public Metal CPU-read API), OBSERVED (`cpu_getbytes`, 2 cases):**
on a gradient-rendered (compressed) texture, `getBytes:` for an 8×8 region returns the
first texel as `(0, 0, 170, 205)` — **exactly the known gradient formula's decoded
value**, not raw codec bytes. On a noise-rendered (also compressed) texture, `getBytes:`
succeeds (`CPU_OP_OK=1`; no closed-form check available for noise content).
**INTERPRETED (H-C3 confirmed):** Metal **transparently decompresses** for CPU-visible
reads; a driver's CPU readback path never needs to understand the compressed codec.

**Blit copy (`cpu_blit`, 2 cases):** `copyFromTexture:toTexture:` between two identically
eligible 64×64 gradient textures succeeds and the **destination is itself compressed**
(`compressed=1`, matching the source); between two sub-threshold 8×8 textures, the blit
also succeeds and the destination is (correctly) **not** compressed. **INTERPRETED (H-C4
confirmed):** blit copies preserve eligibility; a driver can rely on the same
usage/size-driven eligibility rule for blit destinations as for any other creation path.

**Store-action interaction (`cpu_storeaction`, 2 cases):** `MTLStoreActionDontCare` on a
compression-eligible render target completes without error (`status=OK`) and the
descriptor's compression flag is set exactly as with `MTLStoreActionStore` — eligibility
is a creation-time property, unaffected by whether the render pass actually stores.
**INTERPRETED (H-C5 confirmed):** no crash/corruption path found; DontCare content is
correctly undefined-but-safe, not gated further (per PRE_REGISTRATION's confounder note).

---

## 5. Can compression be left disabled with every correctness path intact? — **YES**

This experiment's own eligibility matrix (§1) already answers the row's escape clause
directly, with **three independent, trivial levers**, any one of which fully and
unconditionally disables compression for a resource, with no special-casing required
elsewhere in the driver:

1. **Include `MTLTextureUsageShaderWrite`** in the resource's usage (already the norm for
   any read-write/storage-image resource) — `read,write` and `read,rt,write` both showed
   `compressed=0` at every size tested.
2. **Include `MTLTextureUsagePixelFormatView`** — independently sufficient, confirmed new
   in this experiment (§1); useful for a resource that needs format reinterpretation but
   would otherwise be compression-eligible.
3. **Use a buffer-backed (linear) texture** instead of the optimal/twiddled layout —
   compression **never** engages for a linear texture regardless of usage or size (§1,
   `elig_linear`).

None of these require touching a compression-specific flag, aux buffer, or any codec
knowledge — they are ordinary resource-creation decisions a first driver already makes.
**A first-pass Mesa/Asahi driver can ship correctly with compression fully disabled by
simply never creating a private/optimal-layout ShaderRead-only-or-RenderTarget-only
texture** (i.e. by always including ShaderWrite where a resource needs CPU/compute
mutation, and by using linear layouts wherever the optimal layout isn't strictly required)
— **at the cost of leaving the bandwidth/footprint benefit of compression unused**, not at
the cost of any correctness gap. Every remaining open question in this document (the exact
codec bitstream, the full state-byte alphabet) only matters once a driver chooses to
**enable** compression as a later optimization; nothing here blocks a correct first
implementation.

---

## 6. Gate results

| gate | result |
|---|---|
| (a) `verify.py --selftest` | **PASS** (0 issues) |
| (b) `verify.py --seqtest` | **PASS** (7/7 checks) |
| (c) NON-RECORDED smoke, before any `raw/` write | **PASS** both runs (`work/m4_20260828_run0{1,2}_smoke.json`) |
| (d) nondeterminism exclusion | **PASS** — every case in this experiment is deterministic (`casematrix.nondeterministic_observed_keys()` always empty); cross-run gate requires byte-identical `observed` with zero exclusions |
| (e) fixtures from RECORDED REALITY | **PASS** — `fixtures/recorded_reality.json`, 5 real captures generated via `run_case()` itself |
| cross-run `--captured` | **PASS**, `issues_total: 0`, verdict counts identical both runs (79 PASS / 2 FAIL / 2 N/A) |

Additional process gates: append+fflush per record (`run.py`'s `gated_f.write(...); 
gated_f.flush()`), `PROGRESS.md` milestone log, hard 30s per-case / 20s smoke timeouts, no
run id reused, no post-capture repair (the two known-anomaly cases were **added to the
frozen matrix**, not patched away, once discovered during pipeline validation — see
PROGRESS.md M3), revision pinned in `CAPTURE_CONTRACT.json` by authored-file hash (not
live `HEAD`), fixtures generated from real hardware (not hand-typed).

---

## Limitations / what remains UNKNOWN

- The compressed-block **bitstream** itself: deliberately out of scope (clean-room
  boundary, PRE_REGISTRATION.md). A driver must treat block contents as opaque (already
  the standing guidance in `docs/tiling/README.md` §4.5) or disable compression (§5).
- **Memoryless storage** eligibility: untestable via this experiment's bind-based method
  (`N/A`, not a negative finding).
- The **exact mip-chain aux total formula** (§2.6): qualitatively confirmed to grow with
  chain length; the precise arithmetic is `UNKNOWN` pending a dedicated follow-up.
- The **minimum aux floor** (§2.4) is established at exactly two bpp16 data points; whether
  it is a fixed 128B constant in general (vs. bpp/tile-dependent) is `PARTIAL`.
- The **outlier state byte's** exact bit-level meaning (§3) is deliberately left opaque
  (clean-room boundary) — only its *existence* and *sensitivity to delta/position* are
  documented.
- Every finding is **M4-only**; no A18 Pro replication was performed (target discipline).

---

## Clean-room provenance

```
Clean-room provenance: HW-PROBE + OWN-SHADER + DATA-TRACE
Inputs inspected: our own MSL sources (inline in harness/cprobe.m), our own process's
  registered GPU buffer objects (captured by the READ-ONLY, unmodified
  tools/iotrace/iotrace.c interposer, built into work/iotrace.dylib), public Metal API
  calls (newLibraryWithSource:, replaceRegion:, getBytes:, blit encoder) and their
  documented (not disassembled) behavior.
Apple binary introspection: NONE.
Reproduction: harness/run.py --run <id> --out raw/<id>; harness/verify.py --selftest
  / --seqtest / --captured RUN_A RUN_B.
Evidence: raw/m4_20260828_run01/, raw/m4_20260828_run02/ (02_gated.jsonl / 03_nongated.jsonl
  / 04_manifest.json / 00_inputs.json each), raw/state_and_cpu_aux_excerpts.txt (full aux
  byte arrays behind the state-correlation and CPU-op-sync claims), raw/DUMPS_MANIFEST.md
  (retention/reproduction note for the ~2.3GiB of full per-case iotrace BO dumps, kept only
  on-host under work/dumps/ per CODEX's oversized-raw-artifact rule), fixtures/
  recorded_reality.json, CAPTURE_CONTRACT.json (authored-file SHA-256 hashes).
```

No step in this experiment required reading Apple's implementation; every fact above was
read off our own process's captured data or hardware-visible behavior. Nothing here
reverses the compression *algorithm* — only its externally observable state encoding,
geometry, and driver-visible correctness behavior, per the row's own instruction.
