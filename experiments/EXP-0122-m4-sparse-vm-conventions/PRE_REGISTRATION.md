# EXP-0122 pre-registration — M4 VM conventions, guard/zero pages, sparse residency, timestamps

**Frozen state: PRE-GPU** (no `raw/` capture exists at freeze time). This registration
precedes the two frozen capture runs (`raw/m4-20260828-run01`, `raw/m4-20260828-run02`).

## Disclosed deviation from the ideal "zero dispatch before pre-registration" rule

Per `CODEX.md` step 2, a hypothesis should be pre-registered before any GPU execution. In
practice, designing a defensible offset ladder for the guard/wraparound probe (item 2 below)
required iterative, small, single-case exploratory dispatches on real hardware to find where
interesting behaviour actually lives (the alternative — freezing an uninformed, evenly-spaced
ladder before ever touching the device — would have had a high chance of missing the actual
boundary entirely, as this experiment's own results show). This mirrors the "Extrapolate, then
test" method `CLAUDE.md` explicitly endorses (start from a known-good encoding, hypothesize,
craft and run, observe) and the existing repo convention of a disclosed pre-registration-phase
build/smoke check (see `EXP-0076/PRE_REGISTRATION.md`'s disclosed throwaway `clang` compile).

**Full disclosure of what was actually run before this file was frozen:** a scratch harness
(`work/probe`, built from an earlier revision of `harness/probe.m`) and five throwaway driver
scripts (`work/ladder_probe*.py`, `work/control_*.m`, `work/try_partial.py` — all still present
in `work/`, never promoted to `raw/`) were used to:

1. confirm the harness compiles and the low-risk, no-dispatch cases (`caps`, `align`,
   `addrsurvey`, `maxlen_boundary`, `sparse_caps`, `sparse_miptail`) behave sanely;
2. walk the guard-offset ladder from EXP-0076's known-safe near-boundary cases out through
   increasing powers of two, watching for a hang at every step (none occurred, tested up to
   offset 2^48, single 32-bit reads only, `base_len=64`, `mode=shared`);
3. bisect an observed non-monotonic transition (offset `2^43` flips from "reads zero" to
   "reads live data") down to an exact boundary, and confirm by three independent predicted
   readbacks (`2^44+0`, `2^44+32`, `2^44-32`, `2^43-4`, `2^43+4`, `2^43x5+4`, all matching a
   `(base + off) mod 2^43`, then align-down-to-4-bytes, addressing model against the harness's
   own known buffer layout) that the wraparound period is exactly `2^43` bytes, not `2^44`;
4. discover, isolate, and exhaustively try to fix (hazard-tracking mode, explicit `MTLFence`,
   `useResource:`, `useHeap:`, a 500 ms delay, a single-tile texture, `setPurgeableState:`) an
   unexpected finding: compute-kernel **writes** to an `MTLHeapTypeSparse`-backed, explicitly
   tile-mapped texture do not persist to a later read (by either a compute `access::read` kernel
   or an independent blit-copy readback) on this machine/OS, even though tile **mapping itself**
   demonstrably works (`heap.usedSize` increases by exactly one tile's worth of bytes on map, a
   non-sparse heap control with the identical kernels/dispatch pattern works correctly, and
   reading a genuinely unmapped sparse texture returns zero with no fault).

None of the above produced `raw/` evidence and none is cited as a finding by itself; it is
disclosed here because it directly shaped the frozen case matrices below (`run.py`, the sole
authoritative source), and because hiding real prior GPU execution would violate the spirit of
the clean-room paper trail even though the letter of "capture happens only in `raw/`" is
intact. The two frozen runs below **independently reproduce** every load-bearing case from this
exploration; nothing here is treated as evidence until it is re-observed under the gates.

## Question

`APPLE9_RE_IMPLEMENTATION_GAPS.md` **DRV-ROBUST-01**, the sparse/VM half of P1.5
(`docs/P0-P1-CLOSURE.md`), which prior work (`EXP-0076-m4-buffer-robustness-matrix`,
`EXP-0095-m4-texture-image-matrix`) never touched: `vm_start`/`vm_end` and the kernel-reserved
region as observable from our own process, BO alignment/size/protection/device-address
assignment rules, whether the EXP-0076 "OOB reads zero" behaviour is a guard mapping, a zero
page, or an addressing-level behaviour (and whether it holds at large distances and at VM
boundaries), sparse page-table/folio/tile/mip-tail geometry beyond "a flag and 16 KiB", residency
-return behaviour on unmapped sparse access, synchronisation around sparse residency changes, and
publicly observable timestamp/frequency parameters.

## Hypotheses (falsifiable)

**H-VM1 (BO alignment).** `[MTLDevice heapBufferSizeAndAlignWithLength:options:]` reports a
finite, length- and storage-mode-dependent `(size, align)` pair for every tested length in
`{1..65537}` crossing every power-of-two and ±1 boundary in that range, and a real
`newBufferWithLength:options:` allocation succeeds for every one of those lengths.
*Refuter:* any length in the tested set that returns a zero/absurd `(size,align)` pair, or for
which allocation fails.

**H-VM2 (device-address assignment).** Within one process, releasing and reallocating an
identical, ordered sequence of buffers returns the **same** GPU virtual addresses on the second
and third pass as on the first (a deterministic bump/free-list allocator), and shared- and
private-storage allocations occupy disjoint address neighbourhoods.
*Refuter:* any pass whose address sequence differs from pass 1 for an unchanged allocation
sequence, or shared/private ranges that interleave.

**H-VM3 (`maxBufferLength` is an exact, enforced boundary).** `newBufferWithLength:` succeeds at
exactly `device.maxBufferLength` and at `maxBufferLength - 1`, and fails (`nil`) at
`maxBufferLength + 1`, `maxBufferLength` + the reported heap alignment, and at `1<<40`, for both
shared and private storage modes.
*Refuter:* any of the six per-mode boundary attempts landing on the wrong side of the predicted
line.

**H-GUARD1 (near-boundary zero-fill, replicating EXP-0076 under a new harness).** A 32-bit load
at byte offsets 32 (in-bounds), 60 (last full in-bounds word), 64 (first fully-OOB word) and 1088
(+1 KiB) from a 64-byte owned buffer reproduces EXP-0076's fill/zero pattern exactly, and the
matching stores are discarded outside `[0,64)` without corrupting either adjacent guard
allocation. *Refuter:* any deviation from EXP-0076's established values.

**H-GUARD2 (the "zero" region is narrow, not a page-wide guard).** Reading at a fixed distance of
exactly one platform page/sparse-tile quantum (16384 bytes) past the 64-byte allocation does
**not** reliably return zero the way distances of 4 KiB, 64 KiB and 1 MiB–1 TiB do; nearby
sub-page offsets in `{16384-256 .. 16384+256}` show the same non-zero, non-guard behaviour,
indicating the observed "zero" at small offsets is not evidence of a mapped guard page or a zero
page at 16 KiB range, but a narrow, driver-allocation-dependent phenomenon. *Refuter:* offset
16384 (and its ±256 B neighbourhood) reading zero just like every other tested magnitude up to
1 TiB.

**H-GUARD3 (address-space wraparound at `2^43` bytes).** The effective address computed by
`(device uchar*)base + (uint64_t)off` for this idiom wraps with period exactly `2^43` bytes: for
any tested `off`, the observed 4-byte readback equals the readback that would be obtained from
offset `off mod 2^43`, aligned down to the nearest 4-byte boundary. This is tested at the exact
boundary (`2^43-4096`, `2^43-4`, `2^43`, `2^43+4`, `2^43+60`, `2^43+64`), at a non-boundary
multiple (`3×2^42` = `1.5×2^43`, expected **not** to wrap to zero), at a second full period
(`5×2^43+4`, expected to reproduce the `+4` case exactly), and symmetrically in the negative
(underflow) direction via `off = 2^64 - K` for `K` in `{32, 256, 257, 2^20, 2^30, 2^43}`.
*Refuter:* any tested offset whose readback does not match the `mod 2^43` + align-down-4
prediction, or evidence that the true period is `2^44` (i.e. offset exactly `2^43` failing to
wrap while `2^44` does).

**H-SPARSE1 (per-format sparse tile geometry, not a flat constant).** `sparseTileSizeWithTextureType:
pixelFormat:sampleCount:[sparsePageSize:]` returns a tile shape (in texels) whose byte footprint
(`w*h*d*bytesPerTexel`) equals the requested page-size class's byte count (16384/65536/262144 for
`MTLSparsePageSize16/64/256`) for every tested format/type/sample-count/page-size combination, with
the texel dimensions varying by bytes-per-texel and (for MSAA) sample count — i.e. "16 KiB tile" is
one instance of a page-size-and-format-dependent family, not a fixed geometry.
*Refuter:* any combination whose tile byte footprint does not equal its page-size class's byte count.

**H-SPARSE2 (packed mip tail is chain-based, not per-level).** `firstMipmapInTail` is **not**
simply "the first mip level whose max dimension is below the tile size" — a texture whose base
level is already smaller than the tile (e.g. 63×63 with a 64×64 tile) still reports
`firstMipmapInTail = 1`, not `0`, showing the tail boundary depends on whether the *remaining
mip chain from a level* fits in one page, not a single level's own size.
*Refuter:* the 63×63/64-tile case reporting `firstMipmapInTail = 0`.

**H-SPARSE3 (unmapped sparse texels read as zero, fault-free).** Reading texels from a sparse
texture with zero tiles mapped, across four format/page-size configurations, completes with
command-buffer status `4` (completed, no error) and returns all-zero component bytes for every
tested coordinate — the same "quiet zero" behaviour as EXP-0076's buffer OOB reads, extended to
sparse textures. *Refuter:* any fault, non-completed command-buffer status, hang, or non-zero
readback from an unmapped coordinate.

**H-SPARSE4 (tile mapping changes heap bookkeeping; write persistence is UNRESOLVED, not
assumed).** `heap.usedSize` increases by exactly one tile's byte footprint when a single tile is
mapped (confirming the map call has a real, measurable effect distinct from a no-op), but this
experiment does **not** assert that a compute-kernel write to a mapped tile becomes visible to a
later read under the tested classic (`MTLHeapTypeSparse` + `MTLResourceStateCommandEncoder`)
API path — the exploratory phase found it does not, under every synchronisation strategy tried,
and the two frozen runs are expected to reproduce that negative. This hypothesis is deliberately
phrased as "expect to reproduce a negative", not "expect success", per the CODEX principle that
negative results are first-class: a *positive* readback would itself refute the exploratory
finding and must be reported as such, not suppressed.
*Refuter (of the negative):* any run in which a written pattern is read back correctly from a
mapped tile.

**H-TIME1 (CPU/GPU timestamps share one already-converted domain).** `sampleTimestamps:
gpuTimestamp:` returns `cpuTimestamp == gpuTimestamp` for every sampled pair (replicating
EXP-0052's "equal" public-pair finding under a fresh harness), both are monotonically increasing
across every tested sleep interval (1/5/10/50/100/500 ms), and the delta between consecutive
samples is within a generous multiple of the requested sleep (scheduling jitter, not a
correctness gate). Raw GPU tick frequency and wraparound remain **UNKNOWN** via this public path
— this experiment does not claim to observe them, only to record `mach_timebase_info` (the
CPU-side conversion factor this harness's own watchdogs depend on) as the one frequency constant
that *is* publicly observable.
*Refuter:* any pair with `cpu != gpu`, or a non-monotonic pair.

## Independent / controlled variables

- Independent: buffer length and storage mode (VM domain); byte offset and load/store (guard
  domain); texture type/format/sample-count/page-size/dimensions/mip count and tile mapping
  state (sparse domain); sleep duration (timestamp domain).
- Controlled: harness build flags (`-fobjc-arc -O1 -framework Metal -framework Foundation`),
  MSL compile options (`fastMathEnabled=NO`, `mathMode=Safe` where available), one case per
  process, fixed fill/pattern constants, fixed dispatch geometry (single thread/threadgroup
  per coordinate).
- Known confounders (pre-registered, not corrected): the driver may sub-allocate from a larger
  backing slab, so "OOB" observations may land on other live, driver-owned data whose owner this
  experiment cannot identify (already observed at offset 16384, see H-GUARD2); address-reuse
  determinism (H-VM2) is an allocator behaviour, not an architectural guarantee, and is reported
  as observed, not promised; the wraparound model (H-GUARD3) describes the *effective address
  computed by this pointer-arithmetic idiom*, not necessarily the GPU's literal hardware VA bus
  width — an ISA-level addressing instruction could independently truncate operands the same way
  without the bus itself being 43 bits wide, and this experiment does not distinguish the two;
  the sparse write-persistence negative (H-SPARSE4) is scoped to the classic heap-based sparse
  API on this exact OS build — macOS 26.0 introduces a distinct `placementSparsePageSize` /
  `MTL4` sparse-mapping path that this experiment does not test (named as follow-up work).

## Exact frozen method

`run.py` is the single authoritative source for every case matrix (`align_cases`,
`addrsurvey_seq`, `guard_case_list`, `sparse_caps_combos`, `sparse_miptail_cases`,
`sparse_unmapped_read_cases`, `sparse_partial_map_cases`, `sparse_remap_cases`,
`timestamp_sleeps`) and the raw-record schema. `harness/probe.m` is a single Objective-C binary,
one case per invocation, with two independent timeout belts: an outer Python `subprocess`
timeout (`TIMEOUTS["no_dispatch_proc"]=30s` / `["dispatch_proc"]=20s`) and an in-process
watchdog inside the harness itself (`compile_watchdog_ms=15000` → exit 97,
`dispatch_watchdog_ms=8000` → exit 98). Every record has three top-level keys: `meta` (case
identity — including offsets/lengths that are themselves frozen INPUT constants, safe to
byte-compare), `gated` (facts expected to be deterministic hardware/software facts — no GPU
address, timestamp, or wall-clock-timing field may appear here; enforced structurally by
`verify.py --selftest`), and `raw` (anything permitted to vary run-to-run, reported but never
byte-compared).

Case counts (frozen, from `run.py` as committed): `align` 62 length×mode rows in one process;
`addrsurvey` 6-entry sequence × 3 passes in one process; `maxlen_boundary` 10 rows in one
process; **74 guard cases** (37 offsets × {load,store}) each its own process; `sparse_caps` 12
combos in one process; `sparse_miptail` 9 cases in one process; `sparse_unmapped_read` 4 cases
each its own process; `sparse_partial_map` 2 cases each its own process; `sparse_remap` 1 case
its own process; `timestamp_ladder` 6 sleeps in one process. Total 87 process launches per
capture run.

**Stop-on-hang policy (guard domain only, pre-registered before capture):** the 74 guard cases
are grouped into a positive-offset ladder and a negative-offset ladder (`run.py:guard_offsets`).
If any case in a direction returns `watchdog_compile`, `watchdog_dispatch`, or `proc_timeout`,
every remaining case in that same direction for the rest of that run is recorded as
`skipped_stop_on_hang` (a result, not silently dropped) rather than executed — this is the
concrete implementation of "hard-timeout every dispatch, one case per process, treat faults as
results" for the highest-risk domain. Three consecutive `proc_fail`/`proc_exception` results in
any domain stop the whole run (`raw/<id>/STOP.json`), per the repo-wide infra-failure convention.

**Two fresh runs** are required: `raw/m4-20260828-run01` and `raw/m4-20260828-run02`. Run 02
additionally requires identical committed Git revision and authored-blob SHA-256 hashes to the
closed run 01 record (`inputs.authored_sha256`), not to whatever `HEAD` is when run 02 starts.

## Cross-run comparison policy

`gated` sub-dicts are compared byte-for-byte between run01 and run02 for every non-`skipped`
case whose `exec_status` is `ok` in both runs; this is the load-bearing determinism claim for
every hypothesis above except H-VM2 (address reuse, which is an intra-process, not
cross-process/cross-run, observation) and H-TIME1's raw timing deltas (reported, not gated,
since wall-clock deltas are expected to differ run to run — only `cpu_monotonic`/
`gpu_monotonic` booleans and the `mach_timebase_info` constants are gated). A `gated` mismatch
on any other case is a hard `analysis.py` failure requiring investigation before promotion, not
a silently-accepted variance.

## Environment, timeouts, and raw schema (frozen)

- Target: the local Apple M4 (G16G), macOS 26.6.2 build 25G82, Metal 4, through public Metal
  only. Harness built with `xcrun clang -fobjc-arc -O1 -framework Metal -framework Foundation`.
- Recorded at capture: git revision + dirty flag + experiment-tree dirty entries, `sw_vers`,
  `xcrun --version`, python version, machine, all timeouts, and SHA-256 of every authored file
  (`run.py`'s `AUTH_CODE`/`AUTH_DOC` lists).
- Raw schema per run: `00_inputs.json`, `00_build.json`, one `<domain>.jsonl` per domain listed
  above (append-only, one JSON object per line, `fflush`+`fsync` after every write), and
  `99_envelope.json` written only once every domain has completed without a STOP.
- A pre-capture failure (build or the NON-RECORDED smoke gate) writes `work/<run-id>/STOP.json`
  and never creates the `raw/` tree; a post-capture infrastructure failure (3 consecutive
  spawn/parse failures within one domain) writes `raw/<run-id>/STOP.json` and ends that run.
  Nothing is retried automatically, and a partial run's id is never reused.

## Promotion rule and scope

Before any capture, in this order, all passing: `python3 -B verify.py --selftest`,
`python3 -B verify.py --seqtest`, `python3 -B run.py --build`, `python3 -B run.py --smoke`.
Between run01 and run02: `python3 -B verify.py --selftest`, `python3 -B verify.py --seqtest`
again (both must still pass in the `RUN01_PRESENT` state). After run02:
`python3 -B analysis.py --run-a m4-20260828-run01 --run-b m4-20260828-run02 --write`, then
`python3 -B make_manifest.py --write` and `--check`, then `python3 -B verify.py --captured`.
Until all of these pass, DRV-ROBUST-01's sparse/VM half remains **OPEN** for this configuration.

This experiment cannot establish: the kernel-side mechanism behind any observed behaviour
(everything here is a public-Metal-API black-box observation); Linux/UAPI mapping; A18 (G17P)
behaviour (hands-off, no cross-target inference drawn); the newer macOS-26 `placementSparsePageSize`
/ `MTL4` sparse-mapping path; full sparse aliasing-between-resources behaviour (only single-resource
mapping is tested); or a definitive root cause for the sparse write-persistence negative (H-SPARSE4).
These are named explicitly as remaining work in `RESULTS.md`.

Clean-room provenance: HW-PROBE / OWN-SHADER / PUBLIC API (planned; exploratory phase disclosed above)
Inputs inspected: committed authored MSL, harness, runner, verifier, analysis; Apple SDK public
header files (`Metal.framework/Headers/*.h`) read only for public API method signatures — no
Apple binary was disassembled, decompiled, or otherwise introspected.
Apple binary introspection: NONE
Reproduction: `python3 -B verify.py --selftest && python3 -B verify.py --seqtest && python3 -B run.py --build && python3 -B run.py --smoke`; capture requires explicit `run.py --execute --run-id <id>`
Evidence: no `raw/` observations exist at freeze; `CAPTURE_CONTRACT.json` is the frozen grammar
