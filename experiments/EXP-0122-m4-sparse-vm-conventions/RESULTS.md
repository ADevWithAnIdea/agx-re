# EXP-0122 RESULTS — M4 sparse/VM conventions (DRV-ROBUST-01, P1.5 second half)

**Target:** local Apple M4 (G16G), macOS 26.6.2 build 25G82, Metal 4, public API only.
**Runs:** `raw/m4-20260828-run01`, `raw/m4-20260828-run02`. Both closed cleanly (no `STOP.json`,
87/87 process launches completed, 0 watchdog/timeout results in either run). Cross-run `gated`
comparison (`verify.py --captured`, `analysis.py`): **0 mismatches across every one of the 87
cases** whose `exec_status` was `ok` in both runs (11 domains). `manifest.json`: 9 authored
files + 28 raw artifacts hashed.

Every claim below cites `raw/m4-20260828-run01/<domain>.jsonl` (byte-identical in run02 per the
cross-run gate) or `analysis/summary.json`. **OBSERVED** = what the record directly shows.
**INTERPRETED** = the reading this experiment draws from it, with alternatives named.

---

## 1. VM conventions

### 1.1 BO alignment and size (finite, exhaustively tested)

OBSERVED: `[MTLDevice heapBufferSizeAndAlignWithLength:options:]`, swept over 31 lengths
(`{1,2,3,4,7,8,15,16,17,31,32,63,64,127,128,255,256,257,511,512,1023,1024,4095,4096,4097,
16383,16384,16385,65535,65536,65537}`) × 2 storage modes (shared, private) = 62 rows
(`raw/.../align.jsonl`), returns **`heap_align = 256` for every single one of the 62 rows**
(`analysis/summary.json: align.distinct_heap_align_values == [256]`), and a real
`newBufferWithLength:options:` allocation succeeds for all 62 (`all_alloc_ok: true`).
`heap_size` echoes the requested length exactly (no rounding observed in this range).

INTERPRETED: for this device/OS, the minimum buffer-placement alignment a driver must respect
when placing an arbitrary-length buffer (private or shared) is **256 bytes**, uniformly, at
least across `1..65537` bytes — not the 16 KiB sparse-tile/page granularity one might guess.
Alternative not excluded: alignment could still grow for lengths far outside the tested range
(untested above 65537 and below `maxBufferLength`).

### 1.2 `maxBufferLength` is an exact, symmetric boundary

OBSERVED (`raw/.../maxlen_boundary.jsonl`, `analysis/summary.json: maxlen_boundary`):
`device.maxBufferLength = 9534832640` bytes (≈8.882 GiB — matches the M4-delta figure already
on record in `CLAUDE.md`). For **both** shared and private storage modes:

| label | requested length | alloc_ok |
|---|---|---|
| `max_minus_1` | 9534832639 | **true** |
| `max` (exactly `maxBufferLength`) | 9534832640 | **true** |
| `max_plus_1` | 9534832641 | **false** |
| `max_plus_align` (`max`+256) | 9534832896 | **false** |
| `huge_1<<40` | 1099511627776 | **false** |

INTERPRETED: `maxBufferLength` is an exact, off-by-one-tested ceiling, identical for shared and
private storage, not merely a documented/rounded figure — a driver can allocate exactly up to
and including this value and must reject (or must expect Metal to reject) anything larger, with
no slack. Alternative not excluded: A18/G17P value is unqueried (hands-off); `EXP-M4-*` already
establishes `maxBufferLength` differs by device capacity class, so this exact number is
M4-specific and must be queried, not hard-coded, on other Apple9 devices — consistent with the
existing project guidance.

### 1.3 Device-address assignment (bump/free-list allocator, deterministic within a process)

OBSERVED (`raw/.../addrsurvey.jsonl`): allocating the ordered sequence
`[64B-shared, 64B-shared, 4096B-private, 4096B-private, 1MiB-shared, 1MiB-private]`, releasing
all six, and repeating twice more **within the same process** returns byte-identical GPU
addresses on all 3 passes (`analysis/summary.json: addrsurvey.addresses_identical_across_passes_within_run
== true`). Pass-1 addresses: `0x10000018000, 0x10000018100, 0x10000040000, 0x10000041000,
0x10000068000, 0x10000170000`. The two 64 B shared buffers are 0x100 (256 B) apart; the two
4096 B private buffers are 0x1000 (4096 B) apart — i.e. consecutive same-size allocations are
packed back-to-back with no slack beyond the 256 B alignment already established in §1.1.
Shared- and private-mode addresses in this run occupy disjoint sub-ranges in the observed
window (`0x10000018xxx`/`0x10000170000` shared vs. `0x10000040xxx`/`0x10000068000` private, in
this particular interleaving) — not independently re-tested at larger scale here.

INTERPRETED: within one process, the allocator is a deterministic bump allocator with immediate
address reuse on free (releasing and reallocating the identical sequence gives back the exact
same addresses every time) — this is an **observed allocator behaviour**, not a documented
architectural guarantee, and is not tested across process boundaries or under concurrent
allocation pressure. `vm_start`/kernel-reserved-region boundaries themselves remain **UNKNOWN**:
the lowest address observed in this experiment across all domains was `0x10000018000`
(`2^40 + 0x18000`), which is suggestively close to a round `2^40` base, but this experiment
never drove allocation volume high enough, nor probed low enough, to bound where the
userspace-visible window actually starts or ends as an allocator property (as opposed to the
*addressing-instruction* wraparound at `2^43` established in §2.3, which is a different,
better-evidenced boundary). This is named explicitly as unresolved in §5.

---

## 2. Guard/zero-page behaviour (extends EXP-0076)

74 cases (37 offsets × {load, store}, fixed 32-bit width, `base_len=64`, `mode=shared`), each
its own process, hard-timed. **0 hangs, 0 faults, 0 command-buffer errors** across both runs
(`cb_status=4`/completed on all 74×2=148 executions; guard allocations `g1_ok`/`g2_ok` remained
`true` in every case, including every store case — no OOB store corrupted an adjacent
allocation in the tested offset set).

### 2.1 Near-boundary replication of EXP-0076 (H-GUARD1: confirmed)

OBSERVED: offset 32 (in-bounds) → `05203b56` (matches `F(i)=(0xA5+0x1B*i) mod 256` at i=32..35);
offset 60 (last full in-bounds word) → `f9142f4a`; offset 64 (first fully-OOB word) → `00000000`;
offset 1088 (+1 KiB, EXP-0076's "far" case) → `00000000`. All four exactly reproduce EXP-0076's
established model under an independently authored harness.

### 2.2 The "zero" region is narrow, not a page-wide guard (H-GUARD2: confirmed)

OBSERVED, ascending offset past the 64-byte allocation:

| offset (bytes past base) | obs (32-bit LE) | zero? |
|---|---|---|
| 4096 | `00000000` | yes |
| 16384−256 | `d166d8b1` | **no** |
| 16384−4 | `09000000` | **no** |
| **16384 (one sparse tile / plausible page quantum)** | `0cda71aa` | **no** |
| 16384+4 | `09000000` | **no** |
| 16384+256 | `39ada2a3` | **no** |
| 32768 | `00000000` | yes |
| 1 MiB, 16 MiB, 256 MiB, 4 GiB, 64 GiB, 1 TiB, 2 TiB, 4 TiB | `00000000` (all) | yes |

INTERPRETED: the "OOB reads return zero" finding from EXP-0076 does **not** generalize to "every
address past the allocation reads zero." At exactly one platform quantum (16384 B, which is also
this device's default sparse tile size — see §3) and its immediate ±256 B neighbourhood, reads
return **live, non-zero, non-guard-pattern data** (not `0x5A`/`0xC3`, our own guard-buffer fill
bytes, so not attributable to `guard1`/`guard2`), while both closer (4096 B) and much farther
(32 KiB and up) offsets read zero. This falsifies a "guard page immediately around the
allocation" model and a "everything unmapped reads zero" model in favour of a narrower reading:
most of the address space near a small, lightly-loaded process's live allocations happens to be
unmapped (soft-fault-to-zero, consistent with EXP-0076), but this is **not guaranteed** — some
specific nearby addresses are genuinely backed by other live, driver-owned data whose owner this
experiment cannot identify (a `MTLBuffer`/`MTLLibrary`/queue-internal object, most plausibly).
**Driver implication:** an implementation must never assume that address space adjacent to (but
outside) an owned allocation is safe/zero without an explicit bounds check; the zero-fill
behaviour is real and reproducible at the *tested* small and very-large distances, but is not a
property of "outside the allocation" in general.

### 2.3 Address-space wraparound at exactly `2^43` bytes (H-GUARD3: confirmed, both directions)

OBSERVED — the boundary bisection and masking predictions, all reproduced identically in both
runs:

| case | offset (decimal) | obs | predicted under `(base+off) mod 2^43`, align-down-4 |
|---|---|---|---|
| `p42` | 2^42 | `00000000` (far, unmapped) | far |
| `p43_minus_4096` | 2^43−4096 | `00000000` (far) | far |
| `p43_minus_4` | 2^43−4 | `5a5a5a5a` | `base−4` → inside `guard1` (all `0x5A`) ✓ |
| `p43_exact` | **2^43** | `a5c0dbf6` | `base+0` → `main[0..3]` ✓ |
| `p43_plus_4` | 2^43+4 | `112c4762` | `base+4` → `main[4..7]` ✓ |
| `p43_plus_60` | 2^43+60 | `f9142f4a` | `base+60` → matches §2.1's `last60` exactly ✓ |
| `p43_plus_64` | 2^43+64 | `00000000` | `base+64` → matches §2.1's `oob64` exactly ✓ |
| `p43x1p5` (3×2^42) | 1.5×2^43 | `00000000` (far) | far — rules out period `2^42` |
| `p43x5_plus_4` | 5×2^43+4 | `112c4762` | same as `+4` → confirms period is exactly `2^43`, not larger |
| `p44` | 2^44 (=2×2^43) | `a5c0dbf6` | same as `+0` (consistent either way) |
| `p45_plus_32` | 2^45+32 | `05203b56` | `base+32` → matches §2.1's `ctrl32` ✓ |
| `neg32` (2^64−32) | | `5a5a5a5a` | `base−32` → inside `guard1` ✓ |
| `neg256` (2^64−256) | | `5a5a5a5a` | `base−256` → `guard1`'s first byte ✓ |
| `neg257` (2^64−257) | | `00000000` | 1 B before `guard1`'s start → unmapped ✓ |
| `neg1mb`, `neg1gb` | | `00000000` (both) | far, unmapped |
| `neg2p43` (2^64−2^43) | | `a5c0dbf6` | `base+0` (since `2^64 − 2^43 ≡ −2^43 ≡ 0 (mod 2^43)` and `base<2^43`) ✓ |

Every one of these 12 discriminating cases matches the model exactly, including the two cases
specifically designed to rule out competing periods (`p43x1p5` rules out `2^42`; `p43x5_plus_4`
rules out anything larger than `2^43`), and the model correctly predicts landing inside `guard1`
(a real, independently-verifiable allocation) three separate times from three different large
offsets.

INTERPRETED: the effective address computed by `(device uchar*)base + (uint64_t)off` for this
specific idiom (a `device`-address-space pointer plus a runtime-uniform byte offset, compiled
from our own MSL) **wraps with period exactly `2^43` bytes (8192 GiB)**, then the 32-bit access
is aligned down to the nearest 4-byte boundary before the load executes (consistent with the
per-unit align-down access model EXP-0076 already established). **Alternatives not excluded**
(named explicitly, per `PRE_REGISTRATION.md`'s pre-registered confounder): this could reflect
(a) the GPU's actual hardware VA bus width, (b) a 43-bit-wide ALU/addressing-instruction
operand specific to this load encoding, independent of any true VA bus width, or (c) a
firmware/driver-level address-space window unrelated to raw silicon width. This experiment
cannot distinguish these three; it only establishes the *observed effective behaviour* of this
addressing idiom precisely and reproducibly. It is also **not tested** whether other access
widths (8/16/64/128-bit, already the axis EXP-0076 varied) or other idioms (e.g. texture
addressing, argument-buffer-indirect pointers) share the same `2^43` period.

---

## 3. Sparse residency — geometry established by construction

Per the task's explicit framing, "a sparse descriptor flag and a 16 KiB tile" is **not**
sufficient, and this experiment establishes the actual finite geometry rather than assuming it.

### 3.1 Device capability

OBSERVED (`raw/.../caps.jsonl`): `device.sparseTileSizeInBytes = 16384` (the "default"/legacy
value), and (macOS 13+ API, present) `sparseTileSizeInBytesForSparsePageSize:` returns
**16384 / 65536 / 262144** for `MTLSparsePageSize{16,64,256}` respectively — i.e. there are (at
least) **three page-size classes**, not one fixed tile size. `device.supportsFamily:` reports
Apple1 through **Apple9 = true, Apple10 = false**, consistent with the project's own
Apple9-generation classification of this hardware (an independent internal-consistency check,
not itself a new finding).

### 3.2 Per-format, per-page-size tile geometry (finite table, 12 combinations tested)

OBSERVED (`raw/.../sparse_caps.jsonl`, full table in `analysis/summary.json:sparse_caps.table`):

| type | format | samples | tile (page16) | tile (page64) | tile (page256) |
|---|---|---|---|---|---|
| 2d | r8unorm (1 Bpp) | 1 | 128×128×1 | 256×256×1 | 512×512×1 |
| 2d | rg8unorm (2 Bpp) | 1 | 128×64×1 | 256×128×1 | 512×256×1 |
| 2d | rgba8unorm (4 Bpp) | 1 | 64×64×1 | 128×128×1 | 256×256×1 |
| 2d | bgra8unorm (4 Bpp) | 1 | 64×64×1 | 128×128×1 | 256×256×1 |
| 2d | r32float (4 Bpp) | 1 | 64×64×1 | 128×128×1 | 256×256×1 |
| 2d | rgba16float (8 Bpp) | 1 | 64×32×1 | 128×64×1 | 256×128×1 |
| 2d | rgba32float (16 Bpp) | 1 | 32×32×1 | 64×64×1 | 128×128×1 |
| 2d | rgba8unorm, 2× MSAA | 1 | 64×32×1 | 128×64×1 | 256×128×1 |
| 2d | rgba8unorm, 4× MSAA | 1 | 32×32×1 | 64×64×1 | 128×128×1 |
| 3d | rgba8unorm | 1 | 64×64×**1** | 128×128×**1** | 256×256×**1** |
| 2darray | rgba8unorm | 1 | 64×64×1 | 128×128×1 | 256×256×1 |
| cube | rgba8unorm | 1 | 64×64×1 | 128×128×1 | 256×256×1 |

INTERPRETED: for every tested combination, `tile_w × tile_h × tile_d × bytesPerTexel × samples`
equals **exactly** the page-size class's byte count (16384/65536/262144) — the tile is always
one full page, and the texel-space *shape* of that page scales inversely with bytes-per-texel
(and with sample count for MSAA), never the byte footprint. This is the exact, constructed
answer to "the geometry, not a flat 16 KiB constant." One specific, notable observation: the
reported tile depth for **3D textures is 1** (not partitioned across Z at page16) — i.e. on this
device, 3D sparse tiling is (at minimum, at this page-size class) sliced per-Z-layer exactly like
2D-array, not genuinely volumetric; this experiment did not probe whether page64/page256 (both
of which also reported depth=1 for 3D above) or other page-size/format combinations ever produce
`tile_d > 1`, so "3D sparse tiles are never volumetric on this device" is not asserted as a
universal, only as observed for every combination actually tested.

### 3.3 Packed mip-tail geometry (chain-based, not per-level — H-SPARSE2 confirmed)

OBSERVED (`raw/.../sparse_miptail.jsonl`, 9 cases, all `tex_alloc_ok=true`/`heap_alloc_ok=true`):

| width×height | mips | page | tile edge | first_mipmap_in_tail | tail bytes |
|---|---|---|---|---|---|
| 256×256 | 9 | 16 | 64 | 3 | 16384 |
| 1024×1024 | 11 | 16 | 64 | 5 | 16384 |
| 64×64 | 7 | 16 | 64 | 1 | 16384 |
| **63×63** | 6 | 16 | 64 | **1** | 16384 |
| 4096×4096 | 13 | 16 | 64 | 7 | 16384 |
| 128×128 | 8 | 64 | 128 | 1 | 65536 |
| 128×128 | 8 | 256 | 256 | **0** | 262144 |
| **32×32** | 6 | 256 | 256 | **0** | 262144 |
| 200×150 (NPOT) | 8 | 16 | 64 | 3 | 16384 |

INTERPRETED: `tail_size_in_bytes` always equals exactly one page-size-class tile (16384/65536/
262144 — never larger), confirming the tail is a single page regardless of how many trailing mip
levels it packs. `first_mipmap_in_tail` is **not** simply "the first level whose own max
dimension is below the tile edge": the 63×63/64-tile-edge case has a base level (63) already
smaller than the tile, yet `firstMipmapInTail = 1`, not 0 (the base level is excluded from the
tail); by contrast the 32×32/256-tile-edge case (base level far smaller than its 256 tile) does
report `firstMipmapInTail = 0`. The 200×150 case's mip chain (200,100,50,25,...) has level 2's
max dimension (50) already below the 64 tile edge, yet `firstMipmapInTail = 3`, not 2 — a naive
per-level "max(w,h) < tile edge" rule under-predicts this case by one level. **This experiment
establishes the exact, reproducible per-case values (the load-bearing, implementable fact) but
does not derive a single general closed-form rule from only 9 cases** — that remains explicitly
open work (§5), and any driver implementation should query `firstMipmapInTail`/`tailSizeInBytes`
directly per-texture rather than compute it from a guessed formula.

### 3.4 Residency-return on unmapped access: quiet zero, fault-free (H-SPARSE3 confirmed)

OBSERVED (`raw/.../sparse_unmapped_read.jsonl`, 4 configurations × 3–5 coordinates each,
covering single-tile page16, multi-tile (4×4 tiles) page16, single-tile page64, and a
tile-larger-than-texture page256 case): **every** coordinate in **every** configuration, with
**zero** tiles mapped, reads back all-zero component bytes (`analysis/summary.json:
sparse_unmapped_read.every_case_all_zero == true`), with `cb_status=4` (completed) and no error
in all 4×2=8 executions.

INTERPRETED: unmapped sparse-texture access is fault-free and reads as zero, the same "quiet
zero" model already established for buffer OOB access (§2, EXP-0076) — this holds uniformly
across the four tested tile-size/texture-size relationships, including the degenerate case where
the whole texture is smaller than one tile.

### 3.5 Tile mapping has a real, measurable effect; write persistence is a confirmed NEGATIVE (H-SPARSE4)

OBSERVED (`raw/.../sparse_partial_map.jsonl`, `sparse_remap.jsonl`): mapping one tile via
`MTLResourceStateCommandEncoder updateTextureMapping:mode:region:mipLevel:slice:` (pixel-unit
region, `MTLSparseTextureMappingModeMap`) increases `heap.usedSize` by **exactly** one tile's
byte footprint (16384 for the tested single-tile case, 65536 for the 4-tile "map one of four"
case — i.e. one 16384 B tile), confirming the map call has a real, measurable, correctly-sized
effect and is not a no-op. In the exact same configuration, a compute-kernel write
(`tex.write(pattern, coord)`) to a coordinate inside that freshly-mapped tile, followed by a
compute-kernel read of the same coordinate on a separate, `waitUntilCompleted`-serialized command
buffer, reads back **all-zero**, not the written pattern
(`analysis/summary.json: sparse_partial_map_and_remap.partial_map[*].write_appears_to_persist ==
[false, false]`; `sparse_remap`'s three-stage probe — read-after-write, read-after-unmap,
read-after-remap — reads **all-zero at every stage**, including immediately after the write).

INTERPRETED (a confirmed, reproducible negative — see `PRE_REGISTRATION.md` H-SPARSE4, which
explicitly pre-registered a negative as the expected outcome): on this exact
machine/OS/API-path — `MTLHeapTypeSparse` heap + `MTLResourceStateCommandEncoder`-based tile
mapping — a compute-kernel write into a demonstrably-mapped sparse-texture tile does not become
visible to a later read, **through either verification method tried** (a compute `access::read`
kernel, and — in the disclosed exploratory phase, not repeated under the frozen gates since it
requires no new hypothesis — an independent blit-copy readback that agrees with the kernel
read). The exploratory phase (fully disclosed in `PRE_REGISTRATION.md`) tried and ruled out, as
the explanation, every synchronization mechanism this experiment could construct from the public
API: explicit `hazardTrackingMode = .tracked` on the heap, an explicit `MTLFence` between write
and read encoders, `useResource:`/`useHeap:` calls, an added 500 ms delay, reducing to a single
tile in a single-tile texture, and `setPurgeableState: .nonVolatile`. None changed the outcome.
A **non-sparse** heap-allocated private texture, using the identical kernels and dispatch
pattern, writes and reads back correctly (`0.25,0.50,0.75,1.0` unorm8-quantized, confirmed via
both a compute-kernel read and a blit copy) — isolating the negative specifically to the
`MTLHeapTypeSparse` path, not to heaps or private storage in general.

**This experiment does not establish a root cause** and explicitly flags one strong untested
candidate: macOS 26.0 introduces a *separate* sparse-texture mechanism
(`MTLTextureDescriptor.placementSparsePageSize`, `MTLHeapTypePlacement`, and `MTL4CommandQueue`'s
`MTL4UpdateSparseTextureMappingOperation`) that this experiment never touches. It is plausible
the classic `MTLHeapTypeSparse`/`MTLResourceStateCommandEncoder` path used throughout this
experiment is a legacy code path with reduced functionality on this OS version, and that the
newer path is required for correct write behaviour. **This is named as the single highest-value
next step for the sparse half of P1.5** (§5).

---

## 4. Timestamp/frequency parameters

OBSERVED (`raw/.../timestamp_ladder.jsonl`, 6 sleep durations 1–500 ms): every sampled
`(cpuTimestamp, gpuTimestamp)` pair from `[MTLDevice sampleTimestamps:gpuTimestamp:]` has
**`cpuTimestamp == gpuTimestamp` exactly**, for all 6×2=12 samples across both runs
(`analysis/summary.json: timestamp.all_pairs_cpu_equals_gpu == true`), and both are
monotonically increasing across every tested interval (`all_pairs_monotonic == true`). CPU-side
`mach_timebase_info` = `{numer: 125, denom: 3}` (i.e. 1 mach tick ≈ 41.67 ns, a ≈24 MHz nominal
tick rate — the standard Apple Silicon continuous-clock value, consistent with independent public
knowledge and reported here only as the constant this harness's own watchdogs are built on, not
as a new GPU-specific finding).

INTERPRETED: this reproduces EXP-0052's "equal/monotonic public CPU/GPU pairs" finding
(`docs/P0-P1-CLOSURE.md` P1.6) under an independently authored harness and a different sleep
ladder, strengthening it as an M4 fact. Because the public API returns CPU and GPU timestamps
in one already-unified, already-converted domain, **raw GPU tick frequency, its conversion
factor, and wraparound behaviour remain UNKNOWN via this path** — this experiment does not
claim to observe them and explicitly defers that to `MTLCounterSampleBuffer`-based raw-counter
work, which is P1.6 / `DRV-QUERY-01` territory (EXP-0052 and successors), not re-attempted here.
`mach_timebase_info` is the one frequency constant genuinely observed and load-bearing for a
driver's own CPU-side timing/watchdog code.

---

## 5. What P1.5 still needs (honest scoping)

This experiment establishes **maximum bounded characterization** of the sparse/VM half that was
completely uncovered before it, but P1.5 does **not** close here. Explicitly remaining:

- **`vm_start`/`vm_end` / kernel-reserved-region boundaries.** Not established as an allocator
  property (only the `2^43` addressing-wraparound boundary is well-evidenced, and — per §2.3 —
  it is not proven to equal the true VA bus width). A dedicated experiment driving allocation
  volume far higher, and probing the low end of the address space, is needed.
- **Protection and sharing rules.** Not probed at all (no attempt to read/write another
  process's or another Metal device context's memory, or to test cross-`MTLDevice`/cross-context
  sharing via `IOSurface`/shared events).
- **Sparse write-persistence root cause (§3.5).** The negative is solid; the mechanism is not.
  The macOS-26 `placementSparsePageSize`/`MTL4` sparse-mapping path is untested and named as the
  concrete next step.
- **Sparse aliasing between resources.** Only single-resource mapping was tested; two sparse
  resources sharing/aliasing the same physical tile backing is untested.
- **A general `firstMipmapInTail` formula.** Per-case values are solid and directly queryable;
  a closed-form rule spanning all format/dimension/page-size combinations is not derived (§3.3).
- **Other access widths and idioms for the `2^43` wraparound.** Only 32-bit `device`-pointer
  loads/stores were tested; texture addressing, argument-buffer-indirect pointers, and other
  bit widths are untested extensions of the same method.
- **A18/G17P.** Hands-off per project directive; every number above is M4-specific and must be
  re-queried (not hard-coded) on other Apple9 targets, consistent with the existing
  `EXP-M4-*`/`docs/m4-deltas.md` device-identity discipline.
- **Kernel-side mechanism.** Everything here is a public-Metal-API black-box observation; no
  claim is made about the underlying kernel/firmware implementation.

## Clean-room provenance

```
Clean-room provenance: HW-PROBE / OWN-SHADER / PUBLIC API
Inputs inspected: harness/probe.m, kernels/guard_access.metal, kernels/sparse_access.metal,
  run.py, verify.py, analysis.py, make_manifest.py (all authored by this experiment); Apple
  SDK public header files (Metal.framework/Headers/{MTLDevice,MTLHeap,MTLTexture,
  MTLResourceStateCommandEncoder,MTLCommandBuffer}.h) read only for public API method
  signatures, exactly as any third-party Metal application would -- standard SDK usage, not
  disassembly, decompilation, or any form of binary introspection.
Apple binary introspection: NONE. No Metal.framework/AGX*/IOGPU binary, dylib, kext, or
  firmware blob was disassembled, decompiled, traced, or otherwise introspected. The only
  machine code inspected anywhere in this experiment's history is our own compiled MSL
  (kernels/*.metal), and only indirectly (its *effects*, via read-back buffers/textures --
  no disassembler was run on it in this experiment).
Reproduction: python3 -B verify.py --selftest && python3 -B verify.py --seqtest &&
  python3 -B run.py --build && python3 -B run.py --smoke && python3 -B verify.py --preflight
  (capture requires explicit run.py --execute --run-id <id>; see README.md for the full
  sequence actually used for m4-20260828-run01/run02).
Evidence: raw/m4-20260828-run01/*.jsonl, raw/m4-20260828-run02/*.jsonl (28 raw artifacts,
  manifest.json), analysis/summary.json, analysis/report.txt, CAPTURE_CONTRACT.json.
```
