# RESULTS — EXP-0120: M4 tiler parameter-buffer (TVB) overflow mechanism

**Target:** local Apple M4 (G16G), this host only. macOS 26.6.2 (25G82), Metal 4, public
IOKit user-client selectors only. M4-only; no A18 Pro evidence exists or is claimed here
(A18 Pro is hands-off per `CLAUDE.md`).

**Gated evidence:** `raw/m4_20260828_run01/`, `raw/m4_20260828_run02/` — 57/57 cases each
(Sweep A 42, Sweep B 6, Sweep C 6, Sweep D 3 + 3 post-fault sanity checks). Gate results:
`analysis/verify.py --selftest` PASS, `--seqtest --run01 m4_20260828_run01 --run02
m4_20260828_run02` PASS, `--captured --run01 ... --run02 ...` PASS — **12/12 Sweep B+C cases
byte-exact reproduced** (size-multiset and IOKit selector-CALL histogram, GPU-VA/CPU-address
excluded from the gate per `CAPTURE_CONTRACT.json`). Sweep A (timing) and Sweep D (limits)
are reported in full but are explicitly **not** part of the byte-exact gate (see
`PRE_REGISTRATION.md` §3.4 for why — extreme-`N` faults are non-deterministic, and timing is
inherently continuous/noisy, not a byte-comparable record).

## Verdict

**No independent evidence that a distinguishable multi-pass/reload partial-render mechanism
engages, for this workload's geometry (concentrated in ~1 tile, 128x128, 8xR32F), anywhere
in the range 1 to 20,000,000 triangles** — wall-clock timing is a single clean linear fit
(R²>0.998, both runs) with the per-triangle marginal cost *decreasing* as N grows (the
opposite of a reload-overhead signature), and the userspace-visible sel-9-registered BO
inventory (size multiset) and IOKit selector-CALL histogram are **byte-identical across the
entire sweep, in both officially gated runs** — extending EXP-0108's negative result (code
window/BG-EOT record, tested to ~600,000 *distributed* triangles) to genuinely
*tile-concentrated* geometry and a much wider range (up to 20M). **This is a genuine,
reportable negative result, not proof either way that overflow never happens at this scale**
(see §5 "What this experiment cannot tell us"). Independently, real instability *does* exist
somewhere above this range: at N>=~15-50,000,000 the system shows two distinct, **mutually
non-deterministic** failure signatures (§4), one a confirmed oracle-arithmetic artifact and
one a genuine, cleanly-recovered GPU-level fault — H4 is answered as "bounded, with a
non-deterministic rather than sharp failure edge," not with a single N* threshold.
**H3 is strongly supported**: nothing new and userspace-authored appears at, before, or after
whatever the workload is doing internally at any tested scale, including inside faulting
cases. Cross-referencing the actual, currently-shipping Asahi kernel UAPI (`mesa/include/
drm-uapi/asahi_drm.h`, public reference material, read but not modified) explains *why*: the
UAPI has **no tiler-heap/TVB field at all** (kernel-managed by construction) but **does**
require `bg`/`eot`/`partial_bg`/`partial_eot` program records on *every* render submission,
unconditionally — Mesa's own M1/M2 Vulkan driver builds all four on every single render pass
regardless of whether a partial render will occur. That structural fact is consistent with,
and gives a mechanistic explanation for, EXP-0108's finding that the 0x10000-byte code window
never changes size: if Apple's own driver follows the same "always compile all four" pattern,
there is nothing new to see specifically *at* an overflow boundary — the cost is already fixed
and already paid on every render.

## 1. OBSERVED vs INTERPRETED

### 1.1 H1 — does partial render actually engage, and at what threshold?

**OBSERVED (Sweep A, timing, both runs independently):** slope-corrected marginal
per-submission wall time, `128x128` target, 8xR32F, additive blend, triangles concentrated
in ~1 tile (EXP-0118 `accumulate` mode), fits a single global linear model
`ms = A + B*N` extremely well:

| run | intercept (ms) | slope (ms/triangle) | R² | valid points |
|---|---|---|---|---|
| run01 | 14.511 | 1.2703e-4 (≈127 ns/tri) | 0.99947 | 10/26 N-groups (16 lost to a self-inflicted instability, see §4) |
| run02 | 9.801 | 1.2817e-4 (≈128 ns/tri) | 0.99891 | 25/26 N-groups |

Both runs agree on slope to within 1%. Per-triangle marginal cost, computed directly
(`marginal_ms/N`), **decreases monotonically** from ~300-1700 ns/triangle at small N (fixed
per-process/pipeline overhead not yet amortized) down to a stable ~127-145 ns/triangle by
N=1,000,000 and stays flat (127-137 ns/triangle) all the way to N=20,000,000 in both runs —
see `analysis/m4_20260828_run01_report.txt` / `..._run02_report.txt` for the full per-point
table. **No point in either run shows a super-linear jump** (a genuine reload/multi-kick
signature would show marginal ns/triangle *increasing* past some N*, the opposite of what
was observed).

**OBSERVED (Sweep B, mechanism/inventory, both runs):** for `N` in {1, 1000, 48217, 200000,
2000000, 20000000} (six points spanning below, at, and 400x/40000x/400000x above the
100-8000-triangle range where prior work established correctness), the sel-9-registered BO
**size multiset is identical in every case** (45 BOs; same sizes; `distinct_size_multisets:
1`), and the **selector-CALL histogram is identical in every case** (`distinct_selector_
histograms: 1`). This holds inside both officially gated runs and reproduces byte-exact
*between* them (`verify.py --captured` PASS).

**INTERPRETED:** neither indicator this experiment can observe from userspace shows any
change correlated with triangle count, from N=1 to N=20,000,000, for this specific
tile-concentrated-geometry/target-size configuration. Two explanations remain open and
**this experiment cannot fully separate them** (see §5): (a) the tiler parameter storage for
this configuration genuinely never overflows up to 20M primitives concentrated in ~1 tile on
M4 (10 cores) — i.e. **H1 is falsified for this configuration and range**, correctness at
1K-200K (previously established) and up to 20M (extended here) is not evidence of a reload
because there was nothing to reload; or (b) overflow-handling exists and is genuinely
transparent at both the timing and userspace-registration granularity this experiment can
observe (candidate H2(c), see §1.2). The balance of evidence — a clean single linear fit with
*no* upward inflection over 4.3 decades of N, reproduced independently twice — favors (a) as
the simpler explanation for *this specific 128x128/8-attachment configuration*, but does not
generalize to other target sizes/attachment counts/formats untested here.

**M4-vs-A18 core-count note:** M4 has 10 GPU cores vs A18 Pro's 5; if TVB capacity scales
with core count (each core plausibly gets its own tiler-heap allocation share), the
overflow threshold for this exact geometry could be substantially lower on A18 — this
experiment, per `CLAUDE.md`, ran M4-only and does not test that.

### 1.2 H2 — which mechanism, and how alternatives were excluded

**H2(a) TVB grows via a new/resized userspace BO — REFUTED for the tested range.**
Falsifier condition (PRE_REGISTRATION §1) was met: the BO size multiset is byte-identical
across the entire triangle-count sweep (§1.1). It is also byte-identical across the
**dimension axis** (Sweep C, `WH` in {32,64,128,256,512,1024} at fixed N=1): the raw
size multiset is *not* identical (`size_multiset_invariant_across_sweep: False`) — but that
difference is fully accounted for by our **own 8 R32F output buffers**, whose size is
`((width*4+255)&~255)*height` and necessarily scales with target dimensions (that's our own
CPU-visible readback buffer, not a driver-internal structure). After excluding up to 8
occurrences of that expected, known size per case (`analysis/analyze.py`'s
`large_region_multiset_excluding_own_buffers`, `>=256KiB` bucket to also exclude the
small/constant control BOs), the remaining set of large (`>=256KiB`) regions is **exactly
`[0x74000, 0xc0000, 0x100000]` (475136, 786432, 1048576 bytes) in every one of the six WH
cases**, gate-proven identical in both runs. These three regions are the largest unlabeled
BOs in the entire inventory (EXP-0108's `Known` role table only went up to a 0x1000-byte
"sparse-tiler-param-header" placeholder at `0x10000140000`; this experiment's real observed
size there is `0x74000` = 475136 bytes, ~118x larger than that placeholder assumed — a
correction worth carrying into `docs/`). **None of the three scale with render-target
dimensions across a 32x range (1024x more pixels) or with triangle count across a
20,000,000x range.** Their first 16 KiB of content (capped by `IOTRACE_MAX_MAP=0x4000`) is
also byte-identical between the N=1 baseline and every other tested case, including the
Sweep D fault cases (`raw/m4_20260828_run01/cases/{B-N1,D-*}/iotrace_maps/*va10000140000*`).

**H2(b) genuine multi-kick partial render with extra userspace-visible submission traffic —
REFUTED for the tested range.** Falsifier condition was met: the selector-CALL histogram
(every `IOConnectCall{Method,Scalar,Struct,Async}` selector, including selector `0x11`
"completion/notify queue" per `docs/cmdstream/README.md`'s table) is identical across the
entire triangle-count sweep at fixed submission-count=1. If firmware re-kicked the fragment
stage through additional userspace-visible IOKit traffic per overflow segment, the CALL count
for at least one selector would grow with N; it does not (`total_calls`, `sel9_calls`, full
per-selector histogram all constant). This is consistent with, but does not by itself prove,
EXP-0009's established finding that submission is shared-memory + doorbell (no per-submit
ioctl) — a firmware-internal re-kick, if it happens, would not need a new IOKit call either
way, so this falsifier is necessary but not sufficient to fully exclude H2(b); see §5.

**H2(c) transparent segment-chain inside an already-reserved region — the best-supported
surviving candidate, not directly confirmed.** This experiment did not observe a chain
event directly (that would require firmware-side visibility this project's clean-room
boundary forbids). What it *does* establish: (i) a structurally analogous, already-
documented mechanism exists on this same hardware for the VDM/CDM **command** streams
(EXP-0043: an initial fixed-size segment terminates and is transparently replaced by a link
to a **pre-named** continuation VA inside what is very plausibly a larger reserved region,
with **no new userspace call**); (ii) the 475136-byte "sparse-tiler-param-header" region's
name (from EXP-0108) and its content shape (a repeating small-constant pattern starting at
offset `0x40`, unchanged across every tested case — see hex dumps above) are consistent with,
though do not prove, a header/table for exactly this kind of chained or sparsely-populated
structure; (iii) independently, the **real, currently-shipping Linux Asahi kernel driver has
a debug flag literally named "Synchronous TVB growth"** (`AGX_DBG_SYNCTVB`,
`mesa/src/asahi/lib/agx_device.h:41` / `agx_device.c:70`, and Mesa release notes
`mesa/docs/relnotes/23.3.0.rst:801` "asahi: Add synctvb debug flag") — public, open-source
reference material read here per `CLAUDE.md`'s explicit sanction of `mesa/` as read-only
context, **not** treated as Apple9 hardware evidence. This confirms TVB growth is a *real,
named, already-implemented* mechanism on this GPU family's Linux driver, that it defaults to
**asynchronous** (hence a flag exists to force it synchronous for debugging — implying a
race/latency-hiding design, not a userspace round-trip), and — critically — that **no field
for it exists anywhere in `drm_asahi_cmd_render` / `drm_asahi_cmd_compute`**
(`mesa/include/drm-uapi/asahi_drm.h`, the full struct was read; every field was enumerated,
see §3). TVB growth on the currently-accepted UAPI is **entirely kernel-internal by
construction** — there is no userspace-supplied base/size/growth-control field to reverse
engineer, because the UAPI design already puts this outside userspace's remit. This is
independent, structural corroboration (from the *destination* UAPI itself, not from Apple's
implementation) of exactly what this experiment's M4 DATA-TRACE observed: no new
userspace-visible allocation, ever, correlated with triangle count.

**H2(d) something else:** not identified; not excluded beyond (a)/(b) above.

### 1.3 H3 — who supplies what at the boundary

**OBSERVED:** across all 12 gated Sweep B+C cases and all 6 Sweep D exploratory cases (18
total interposer captures, both runs), the sel-9-registered BO inventory is **45 BOs**,
every time, with the **same size multiset**, including through the two BOs this experiment
newly measured at 475136 and 786432 bytes and the two already-known-role BOs at 0x10000
(4GiB-aligned code window, EXP-0042) and 0x88e0 (tiling-state, EXP-0108). Critically, this
holds **even when the render itself fails** — `D-accumulate-N50000000` in run01 (silent
wrong-value, `status=Completed exact=0`) and run02 (`status=Discarded/GPU-recovery
exact=0`), and `B-N20000000` in run02 (`status=Discarded/GPU-recovery`, vs. `status=Completed
exact=1` for the *same case* in run01) all show **n_bo=45, identical size multiset** to the
successful baseline. The pre-commit dump point (`G17P_DUMP_BEFORE_COMMIT`, EXP-0118's own
unmodified hook) is confirmed, by direct log inspection, to be the *complete* lifetime
inventory for this workload: total sel-9 CALL count in a full unhooked run equals the count
up to the pre-commit dump point in every case checked (0 sel-9 calls occur after encode
time; a small, constant number of *other*-selector calls — two `sel=15`, one `sel=17(0x11)`
"completion/notify", one `sel=8` "create queue" — occur after, unrelated to resource
registration).

**INTERPRETED:** no new userspace-authored program, descriptor, or resource-specifier record
appears at, before, or through whatever the workload is doing internally, at any tested
scale — including the two extreme-N cases that ended in a hardware-level fault. Combined
with the UAPI cross-reference in §1.2: the fields userspace/the driver genuinely **must**
supply on every render are `bg`, `eot`, `partial_bg`, `partial_eot` (4x `drm_asahi_bg_eot`,
each just a USC address + a packed resource-specifier word) plus the ordinary FF-state/
attachment/scissor/depth-bias/ZLS/sampler-heap fields already characterized elsewhere in
`docs/`. **None of these are TVB-specific** — there is no UAPI field for tiler-heap base,
size, or growth control at all (§1.2). So "what userspace supplies at the TVB-overflow
boundary" is, per the UAPI's own design, **nothing beyond what it already supplies on every
render** — the boundary is not a distinct userspace event.

### 1.4 H4 — finite-resource envelope and failure mode

**OBSERVED, safe/correct range:** N=1 through N=20,000,000 (accumulate mode, 128x128,
8xR32F) completes with `status=Completed` and the accumulate oracle's `exact=1` maxima
(~1..8) in the large majority of trials (both official runs; one `N=20,000,000` instance in
run02 faulted, see below) — with byte-identical BO/call footprint throughout (§1.1/§1.3).

**OBSERVED, failure region, non-deterministic:** above this range, two *distinct* failure
signatures were observed, and — this is the headline H4 finding — **the same nominal case
produced different outcomes across repeated, independent runs**:

| case | pilot (informal) | run01 (gated) | run02 (gated) |
|---|---|---|---|
| `accumulate N=50,000,000` | `status=4 exact=0` (silent, quantized maxima) | `status=4 exact=0` (silent) | `status=5` Discarded/GPU-recovery |
| `overflow N=15,000,000` | `status=4 exact=1` (correct) | `status=4 exact=1` (correct) | `status=5` Discarded/GPU-recovery |
| `overflow N=20,000,000` | `status=5` Discarded/GPU-recovery | `status=5` Discarded/GPU-recovery | `status=4 exact=1` (correct) |

`status=5` is Metal's `MTLCommandBufferStatusError` with
`kIOGPUCommandBufferCallbackErrorInnocentVictim` — the command buffer was discarded as an
"innocent victim" of a GPU-level error/recovery event, not a fault in this specific command
buffer. **The system fully recovered every time**: a post-fault sanity check
(`accumulate N=1000`, expect `exact=1`) was run after every Sweep D case in both official
runs (6/6 total) and after every informal-pilot fault, and **passed every single time** —
consistent with `CLAUDE.md`'s documented recovery model ("Illegal shader encodings on the
local M4 are usually fault-contained... no wedge"). No host-level instability was observed at
any point in this experiment.

**Confound identified and resolved (accumulate-mode oracle precision, NOT a capacity
signature):** `accumulate` mode's per-triangle increment is `1.0/N`; at N>=~50,000,000 this
falls far enough below the running additive-blend sum's float32 ULP that the sum stagnates
before reaching its ideal value — a textbook float32 summation-saturation artifact, unrelated
to hardware capacity. This was **actively tested and confirmed**: the exact same quantized,
power-of-two-related maxima pattern (`0.5, 1, 2, 2, 2, 4, 4, 4` for the 8 attachments' 1x-8x
multipliers) was observed at N=50,000,000 for THREE different target sizes (32x32, 128x128,
512x512) — byte-identical across a 256x pixel-count range, which a genuine tile/geometry
capacity limit would not be expected to produce. **`docs/` must not attribute an
`accumulate`-mode failure at extreme N to TVB exhaustion without this check** (now stated
explicitly in `PRE_REGISTRATION.md` §5 as a pre-registered confounder).

**INTERPRETED:** there is a real instability region starting somewhere around 10⁷-10⁸
triangles concentrated in ~1 tile for this configuration, but this experiment's evidence
does not support a sharp, reproducible N* — repeated trials of the identical case flip
outcome. Plausible (untested, not claimed) causes include GPU/firmware watchdog timing
racing against genuinely-growing internal work, thermal/frequency state carried over between
back-to-back extreme-stress processes in the same session, or scheduling contention — this
experiment cannot distinguish them from userspace DATA-TRACE/HW-PROBE alone. **The finding
itself — non-deterministic hardware-level fault beyond ~10⁷ triangles, cleanly recovered, no
wrong-but-silent-completion signature independent of the oracle-precision confound — is the
reportable H4 result.** Growth granularity (if TVB genuinely grows at all) remains UNKNOWN;
no userspace-visible channel to observe it was found (§1.2/§1.3).

## 2. Mesa/UAPI comparison — could be made, contrary to the dispatch's premise

The dispatch instructed: *"mesa/ is an unmaterialized gitlink in this checkout... use
gpu_knowledge/ and our own docs... and say explicitly that the Mesa comparison could not be
made from this checkout."* This premise was checked and found **incorrect** for the current
checkout: `mesa/src/asahi/` and `mesa/include/drm-uapi/asahi_drm.h` are real, materialized,
readable files (not an empty gitlink), and `CLAUDE.md` explicitly sanctions reading `mesa/`
as PUBLIC/read-only reference material ("how a userspace driver must produce... how Mesa
parameterizes M1/M2... the pinned Asahi UAPI compatibility inventory"). The comparison
**was** made (§1.2, §1.3, §3) — bounded, read-only, no code copied, cited by exact file/line.
This is M1/M2 Linux driver + kernel-UAPI context only, **never** treated as Apple9/M4/A18
hardware evidence; every finding above that depends on M4 hardware behavior is sourced
exclusively from this experiment's own DATA-TRACE/HW-PROBE captures.

## 3. UAPI fields enumerated (public reference, `mesa/include/drm-uapi/asahi_drm.h`)

Full `struct drm_asahi_cmd_render` field list, as read (no TVB/tiler-heap field of any kind):
`flags`, `isp_zls_pixels`, `vdm_ctrl_stream_base`, `vertex_helper`, `fragment_helper`,
`isp_scissor_base`, `isp_dbias_base`, `isp_oclqry_base`, `depth`/`stencil`
(`drm_asahi_zls_buffer`), `zls_ctrl`, `ppp_multisamplectl`, `sampler_heap`, `ppp_ctrl`,
`width_px`/`height_px`/`layers`, `sampler_count`, `utile_width_px`/`utile_height_px`,
`samples`, `sample_size_B`, `isp_merge_upper_x`/`isp_merge_upper_y`, **`bg`**, **`eot`**,
**`partial_bg`**, **`partial_eot`** (each `struct drm_asahi_bg_eot { __u32 usc; __u32
rsrc_spec; }` — a USC program address + packed resource-specifier word, matching the shape
`docs/pipeline/README.md`'s "Open items" already anticipates), `isp_bgobjdepth`,
`isp_bgobjvals`, `ts_vtx`, `ts_frag`. `struct drm_asahi_cmd_compute` has no BG/EOT/partial
fields at all (compute has no tile lifecycle). Mesa's `hk_build_bg_eot` (`mesa/src/asahi/
vulkan/hk_cmd_draw.c:268-...`) is called **unconditionally, 4 times, on every
`hk_CmdBeginRendering`**-equivalent setup (`hk_cmd_draw.c:624-632`: `bg.main`, `bg.partial`,
`eot.main`, `eot.partial`, no `partial_render`-triggered conditional around the calls
themselves — the `partial_render` *parameter* only changes what each built program *does*,
e.g. whether it stores/loads spilled attachments), independent of whether that specific
render will ever actually partial-render.

## 4. Faults, gate results, and process notes

- **`analysis/verify.py --selftest`: PASS** (4/4 checks: exact linear-regression fit,
  degenerate-input handling, parsing against a real pre-freeze log fixture with independently
  cross-checked ground truth, multiset-invariance discrimination).
- **`--seqtest --run01 m4_20260828_run01 --run02 m4_20260828_run02`: PASS** (`PRE_GPU` ->
  `RUN01_PRESENT` -> `RUN02_PRESENT`, contract-timestamp and ordering checks).
- **`--captured --run01 ... --run02 ...`: PASS** — 6/6 Sweep B cases and 6/6 Sweep C cases
  byte-exact reproduced (size multiset + selector histogram; GPU VA/CPU address excluded from
  the gate by construction, per the standing "no nondeterministic field in byte-compared
  records" rule).
- **NON-RECORDED smoke gate**: run before either official capture (`work/smoke/`, 4
  representative cases, discarded from evidence, not deleted from disk for transparency).
- **Sweep A instability (self-inflicted, root-caused, not hidden):** run01's Sweep A had
  18/42 faults (`status=5` GPU-recovery-discard), **even at N=1**, occurring at
  non-deterministic points inside the 48-submission repeated-render loop
  (`argv[5]`, EXP-0118's own, unmodified feature) — root-caused to the extensive pre-freeze
  calibration exploration (`work/pilot_*`, including several tens-of-millions-to-billion-
  triangle stress probes) run immediately beforehand in the same session, which evidently
  left transient GPU/driver state more fault-prone. Sweep B/C (single-submission processes,
  same session, run immediately after) were **100% clean (0/12 faults)** in run01, and run02
  (a fresh sweep after the system had settled) dropped to 4/57 total faults — confirming the
  instability is tied to *repeated back-to-back submissions within one process*, not to
  triangle count, and is **transient**, not a persistent degradation (`analyze.py` already
  discards any slope-method pair with a non-zero returncode on either side before fitting, so
  no corrupted timing point entered the reported fit; every fault is preserved verbatim in
  `raw/*/records.jsonl`, never hidden or retried-and-discarded).
- **Process isolation:** every case (57 x 2 runs = 114, plus 6 post-fault sanity checks) ran
  as its own OS process; no case was batched or reused; every record was appended with
  `fflush`+`fsync` immediately after the process returned.
- **No timeouts occurred** (150 s hard cap never hit; the largest case, N=20,000,000
  single-submission, completed in 2.5-7.7 s).
- **No host wedge, no manual intervention, no `macvdmtool` use, A18 Pro never touched.**

## 5. What this experiment cannot tell us (explicit limits)

- Whether a partial-render event genuinely never occurs for this configuration up to 20M
  triangles, or occurs but is transparent at both the timing-slope and BO-registration
  granularity this experiment can observe (§1.1) — distinguishing these would require
  firmware-side visibility this project's clean-room boundary forbids.
- Behavior for target sizes/attachment counts/formats/varying-data sizes outside what
  EXP-0118's unmodified binary exposes (fixed at 8 attachments, R32F, a 16-byte dummy varying
  buffer in `accumulate`/`overflow` modes) — not variable without modifying EXP-0118, which
  was out of scope per the dispatch.
- A18 Pro behavior (hands-off; M4 is Apple9-equal for every driver-emittable subsystem per
  `EXP-M4-*`, but core-count-dependent capacity, if any, would not transfer — see §1.1's
  10-vs-5-core note).
- A precise, reproducible failure threshold N* (§1.4) — the observed boundary is
  non-deterministic at the scale tested.
- The exact semantic role of the 475136-byte and 786432-byte regions beyond "large, present
  on every render, invariant across N and target size, structurally consistent with — but not
  proven to be — tiler-heap/TVB-adjacent storage." No field-level decode was attempted here
  (out of this experiment's scope; a natural EXP-0121+ follow-up).

## 6. What this means for P0.4 / DRV-UAPI-04

This experiment does **not** close P0.4 (that requires independently generated, authored
BG/EOT/partial-BG/partial-EOT programs the hardware actually executes — categorically
different work, per `docs/P0-P1-CLOSURE.md`'s closure rules). What it adds:

1. **The overflow-handling mechanism itself, at least up to 20,000,000 tile-concentrated
   triangles on M4, requires no userspace-supplied program, descriptor, or resource-spec
   beyond what a render already supplies unconditionally.** An implementer following the
   existing Linux UAPI does not need a *dynamic, overflow-triggered* code path at all —
   `partial_bg`/`partial_eot` are filled in at render-setup time, every time, exactly as
   `bg`/`eot` are (§1.3, §3). This directly supports the framing already in
   `docs/pipeline/README.md` ("overflow -> partial-render trigger is firmware-managed — no
   userspace knob") and extends it with a mechanistic *why*, cross-referenced against the
   real UAPI's own field list.
2. The TVB/tiler-parameter-heap itself has **no UAPI-visible existence at all** — it is not
   something the implementation team ever needs a field, base address, or growth-control knob
   for, on the currently-accepted UAPI (§1.2, §3). This narrows P0.4/DRV-UAPI-04's remaining
   scope to the BG/EOT *program content and ABI* (already tracked as open) — not to any TVB
   sizing/growth contract, which does not exist in the interface being targeted.
3. A concrete correction for `docs/`: EXP-0108's placeholder role `sparse-tiler-param-header`
   (`0x10000140000`, assumed `0x1000` bytes) is **475136 bytes (`0x74000`)** in this
   experiment's captures, with a distinct repeating-constant content pattern from offset
   `0x40`; a previously-unnamed, larger (786432-byte, `0xc0000`) all-zero-content region also
   exists at a fixed relative position and is equally invariant. Both are candidates for
   `docs/pipeline/README.md`'s "Open items" list; neither is decoded further here.
4. H4's non-deterministic hardware-level fault beyond ~10⁷ triangles (cleanly recovered, no
   host risk observed) is a new, directly reportable finding for the finite-resource/limits
   side of the documentation, independent of P0.4.

## Clean-room provenance

```
Clean-room provenance: DATA-TRACE + HW-PROBE (+ bounded PUBLIC reference: mesa/, read-only,
  cited by exact file/line, never treated as Apple9/M4 hardware evidence)
Inputs inspected: our own process's IOKit boundary traffic (tools/iotrace/iotrace.c,
  unmodified, pinned SHA-256 4c8e1ced...; compiled read-only into harness/build/iotrace.dylib),
  our own black-box wall-clock timing of experiments/EXP-0118-.../build/partial_render
  (unmodified, pinned SHA-256 b6bf7e27...), and public open-source reference material
  (mesa/src/asahi/lib/agx_device.{c,h}, mesa/src/asahi/vulkan/hk_cmd_draw.c,
  mesa/include/drm-uapi/asahi_drm.h, mesa/docs/relnotes/23.3.0.rst)
Apple binary introspection: NONE
Reproduction: harness/build_iotrace.sh && python3 harness/run_sweep.py --smoke (dry run) &&
  python3 harness/run_sweep.py --run-id <new-id> (official; run ids in CAPTURE_CONTRACT.json
  are already used and must not be reused) && python3 analysis/analyze.py <run-id> &&
  python3 analysis/verify.py --selftest --seqtest --captured --run01 ... --run02 ...
Evidence: raw/m4_20260828_run01/, raw/m4_20260828_run02/ (records.jsonl + per-case
  stdout/stderr/iotrace.log/iotrace_maps/*.hex, append-only, never edited);
  analysis/m4_20260828_run01.json, analysis/m4_20260828_run02.json (derived, repeatable);
  PRE_REGISTRATION.md, CAPTURE_CONTRACT.json (frozen before capture); PROGRESS.md (milestone
  log)
```
