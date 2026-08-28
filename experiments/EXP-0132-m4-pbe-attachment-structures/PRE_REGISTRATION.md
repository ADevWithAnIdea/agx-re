# PRE_REGISTRATION — EXP-0132: M4 PBE/attachment-descriptor field mapping

Frozen before the first OFFICIALLY GATED capture run (`m4-20260828-run01`/
`m4-20260828-run02`). Pin: git revision recorded in `CAPTURE_CONTRACT.json`
at freeze time (`cf544b4dd1fb37047c7cfee6a70a0d1a87628666`, repo dirty with
unrelated sibling-experiment files only — see `CAPTURE_CONTRACT.json`
`git_dirty_note`); do not gate on live `HEAD` per
`experiments/SUBAGENT_BRIEF.md`.

This document is written AFTER an extensive pre-capture harness-development
and diagnostic phase (all informal, all under `work/`, never `raw/` — see
`PROGRESS.md` milestones M1–M4). That phase is disclosed here in full,
per CODEX's "do not quietly drop what was tried": two real harness bugs
and one real harness-reliability issue were found and fixed before this
freeze, and are recorded as findings in their own right (not polished away).

## 1. Question and why it matters

`APPLE9_RE_IMPLEMENTATION_GAPS.md` DRV-PBE-01 / `docs/P0-P1-CLOSURE.md`
row P1.1 requires decoding **every** field of the storage/PBE descriptor
and the three load/render/store attachment segments: type/layer/mip/
sample/array selection, component mapping, access/control bits, rotation/
mode, coherency, reserved values, program-ID ownership, per-layer/mip/
resolve offsets and strides, memoryless, compression, depth/stencil, mixed
MRT, and every load/store/clear/resolve combination. P1.1 has had no
dispatched agent this wave and its evidence (`EXP-0048`, `EXP-G1b`) is
partly stale/A18-only; `EXP-0108` (a sibling M4 experiment on the adjacent
P0.4 BG/EOT question) produced a *doubly-corroborated but not two-run
byte-exact-gated* finding that depth/stencil reuse the same k-indexed
color-attachment descriptor array — flagged explicitly in its own
RESULTS.md as needing "a harness fix (SIGUSR1 read-race) and a re-targeted,
gated capture" before promotion to `docs/`. That is this experiment's
first priority. Its second and third priorities (per this dispatch) are
field-mapping the three attachment segments by varying one Metal parameter
at a time, and resolving EXP-0108's unidentified `attachment-slot-b`
region.

## 2. What the pre-capture diagnostic phase already established (disclosed,
not hidden, per CODEX)

All of the following were found via informal two-run dry checks in
`work/diag*` (never committed as `raw/` evidence; only cited here as the
basis for this frozen design). They are NOT the officially gated result —
the official result comes from the frozen harness below, run fresh as
`m4-20260828-run01`/`run02`.

1. **Harness bug 1 (found + fixed): unsafe SIGUSR1 fallback.** The first
   `probe.m` draft fell back to `kill(getpid(), SIGUSR1)` if
   `dlsym(RTLD_DEFAULT, "wtrace_snapshot_now")` failed to resolve. Under a
   misconfigured environment (in one diagnostic script, a copy-paste
   omission of `env=env` in a `subprocess.run` call — a diagnostic-script
   bug, not a hardware fact) this actually happened, and because no signal
   handler was loaded in that case, the DEFAULT disposition of SIGUSR1
   (terminate) killed the harness process (`returncode -30` on every
   case). **Fixed:** the fallback path no longer sends a real signal; it
   logs `WTRACE_DIRECT_SNAPSHOT_UNAVAILABLE` to stderr and continues
   with no dump, so a misconfiguration degrades to "no descriptor capture
   for this case" rather than a fatal, misleading-looking crash.
2. **Harness bug 2 (found + fixed): JSON `null` treated as truthy.**
   `probe.m` read `cfg[@"readback_slices"]`/`cfg[@"readback_levels"]` and
   used Objective-C truthiness (`if (x)`) to decide whether the caller
   supplied an override list. A JSON `null` (the default for every case
   that doesn't set these) decodes to `NSNull`, a real non-nil object, so
   the truthy check passed and the code tried to enumerate an `NSNull` as
   if it were an `NSArray`, raising an uncaught `NSInvalidArgumentException`
   (`countByEnumeratingWithState:` not implemented) that aborted the
   process. **Fixed:** explicit `isKindOfClass:[NSArray class]` guards.
3. **Harness bug 3 (found + fixed): `replaceRegion`/`getBytes` on a live
   multisample texture.** The MSAA (`samples>1`) color/attachment-0 texture
   is not a valid target for `replaceRegion:`/`getBytes:` (Metal validation
   rejects direct CPU-side read/write of a multisample texture's samples);
   attempting it raised an uncaught NSException (observed as a corrupted-
   looking `NSConstantArray`/`getObjects:range:` message — almost certainly
   a secondary symptom of an unwound/garbage stack after the real Metal
   validation failure, not a literal array-bounds bug in this harness's own
   code). **Fixed:** the canary pre-fill and the final `cells` readback
   both skip the raw `colorTex[i]` for `samples > 1`; those cases are read
   back only through the separately allocated, always-single-sample
   `resolveTex[i]`.
4. **Methodological finding (found + fixed): a client buffer aliased the
   fixed VA `wtrace.c` treats as `mrt-attachment-descriptors`.** The first
   probe.m draft (forked from EXP-0108, which allocates the small 32x32
   color target as a client `MTLBuffer` + `newTextureWithDescriptor:
   offset:bytesPerRow:`) produced a captured "descriptor" region whose
   entire content was the exact rendered pixel byte pattern
   (`4080bf80` repeating), because the client buffer's own `gpuAddress`
   landed exactly on `0x10000018200` in this harness's specific allocation
   order — the same class of VA coincidence EXP-0048's own
   `raw/preflight_failures.md` already documented for a different
   configuration ("a small user allocation occupied GPU VA
   `0x10000018200`, demonstrating that VA alone is not a role guarantee
   under arbitrary allocation schedules"). **Fixed at the root, not
   patched around:** every color/resolve attachment in the frozen
   `harness/probe.m` is a plain (non-buffer-backed) `MTLStorageModeShared`
   texture; no client `MTLBuffer` is ever allocated for a render target, so
   there is no client allocation competing for the same VA class as the
   tiler-heap descriptor arena. Readback uses `getBytes:...:fromRegion:
   mipmapLevel:slice:` uniformly.
5. **Harness-reliability finding (found + fixed): the interposer's
   `mach_vm_read_overwrite` of the `mrt-attachment-descriptors` BO
   sometimes failed even for the simplest (`a1`) case specifically inside a
   rapid back-to-back subprocess loop, though it succeeded reliably in
   isolation.** With the original EXP-0108-derived retry budget (6 tries *
   5 ms), this case showed a **consistent** (both dry-run repetitions,
   `tries=7` i.e. all 6 attempts exhausted) read failure in the loop
   context, while a structurally near-identical sibling case (`d1`,
   differing only in pixel format) succeeded reliably. **Fixed:** the retry
   budget was widened to 40 tries * 10 ms (400 ms worst case, still far
   under any per-case timeout); after widening, all 16 cases captured this
   role successfully and reproducibly in both dry-run repetitions. This is
   recorded as an open, only-partially-understood harness-reliability
   phenomenon (not attributed to a specific hardware mechanism) — see
   `PROGRESS.md`.
6. **Positive finding (already visible in the diagnostic phase, to be
   formally confirmed by the gated capture, not asserted here as final):**
   with the above fixes, the `mrt-attachment-descriptors` k-indexed
   0x20-byte-stride LOAD/STORE array (`+0x20+k·0x20` / `+0x220+k·0x20`,
   established by EXP-0048/EXP-M4-08/09) shows, address-subfield-masked,
   **byte-for-byte identical** depth/stencil k-records across two dry
   repetitions for every one of `g1`/`h1`/`i1`/`i2`, generalizing
   EXP-0108's `ncolor=1`-only finding to `ncolor=2` (`i2`) as an
   independent adversarial test. Array slice and mip level (`l1..l4`,
   `m1..m3`) do **not** change this record at all except that
   `mipCount>1` (regardless of which `level` is targeted) sets what is
   structurally identical to the sampled-texture-descriptor's "mipmapped"
   flag (word1 bit26, `format-table.md` §5) — a new cross-descriptor
   structural confirmation. An MSAA+resolve case (`r1`/`r2`) shows the
   resolve target populating the **next** k slot (`k=ncolor`) in **both**
   the LOAD and STORE arrays, generalizing the "next free k slot" pattern
   EXP-0108 found for depth/stencil to a third kind of attachment.
   `attachment-slot-b` (the fixed VA `0x10000120000` EXP-0108 named) never
   appeared in ANY of the 16 cases in this harness, despite exercising
   axes EXP-0108 reported it correlating with (action, MRT, MSAA, format,
   depth/stencil) — see the falsifiable H5 below.

These are reported here as the **basis for the frozen design**, not as the
experiment's evidence of record. The evidence of record is the officially
gated `m4-20260828-run01`/`run02` pair captured after this freeze, using
the exact harness this document locks in.

## 3. Falsifiable hypotheses

- **H1 (depth/stencil slot-reuse, EXP-0108's flagged open item).** The
  `mrt-attachment-descriptors` k-indexed array's k=`ncolor` slot is
  populated by the depth attachment and k=`ncolor+1` by the stencil
  attachment, for both LOAD and STORE, address-subfield-masked, byte-exact
  across two official runs, for `ncolor∈{1,2}`.
  **Falsifier:** any officially gated run pair shows a byte mismatch in
  the masked k=ncolor/k=ncolor+1 windows between the two runs of the same
  case, or shows the depth/stencil content at a DIFFERENT k index than
  predicted, or shows no such record for `i2` (ncolor=2) even though it
  exists for `i1`/`g1`/`h1` (ncolor=1).
- **H2 (array/mip selection is NOT encoded in the per-attachment k-record,
  except a coarse "mipmapped" flag).** Varying `slice` (0/1/last, fixed
  `arrayLength`) produces byte-identical k=0 LOAD/STORE records; varying
  `level` (0/last, fixed `mipCount`) likewise produces byte-identical
  k=0 records to each other, but differs from a `mipCount=1` baseline only
  in word1 bit26 (and the already-known opaque high-address-adjacent
  field). **Falsifier:** any run shows the k-record's non-address bytes
  differing between two different `slice` values at fixed `arrayLength`,
  or between two different `level` values at fixed `mipCount` — either
  would mean layer/mip selection IS encoded here after all, refuting the
  diagnostic-phase observation and requiring the exact changed field to be
  reported instead of this null result.
- **H3 (array/mip boundary behavior).** An out-of-range `slice`
  (`slice==arrayLength`) or `level` (`level==mipCount`) does not raise a
  Metal API error and does not abort the process; the command buffer
  completes with status Completed/no error. The exact readback pattern
  (whether it aliases a valid slice/level, stays untouched, or writes
  zero) is recorded as an open, exactly-characterized observation, not
  assumed in advance. **Falsifier:** an invalid slice/level causes
  `PIPELINE_FAIL`/`ENCODER_CREATE_FAIL`/`NSEXCEPTION_*`/`CMDBUF_ERROR`, or
  a `PROCESS_ABORT` (negative subprocess return code) — any of these would
  refute "silently accepted" and must be reported as the actual boundary
  behavior instead.
- **H4 (MSAA resolve target uses the next free k slot).** For a
  `samples>1` case with a `MultisampleResolve`/`StoreAndMultisampleResolve`
  store action, the resolve target's own descriptor populates k=`ncolor`
  in BOTH the LOAD and STORE arrays (a plain, non-multisample texture-type
  record), while the STORE array's own k=0..ncolor-1 slots (the MSAA
  color attachment's own STORE record) are entirely zero.
  **Falsifier:** the resolve descriptor appears at a different k index, in
  a different named role entirely, or the k=0 STORE slot is non-zero for
  the MSAA color attachment.
- **H5 (`attachment-slot-b` non-reproduction).** `attachment-slot-b`
  (`0x10000120000`) does not appear as a captured or even present-but-
  uncaptured named role in ANY of the 16 cases in this harness, despite
  exercising the axes (action-adjacent load/store combinations, MRT via
  `i2`, MSAA via `r1`/`r2`, depth/stencil, per-format via `d1`) EXP-0108
  reported it correlating with. **Falsifier:** any officially gated run
  shows `attachment-slot-b` present in the per-case inventory — if so, its
  content is to be extracted and reported per the original priority-3
  mandate instead of reporting non-reproduction.

## 4. Independent / controlled variables

Independent variable: each case's one or two deliberately varied fields
(`harness/casematrix.py`, single source of truth, 16 cases across 8 axes:
`depth-stencil-reverify` (7 cases), `array` (3), `array-boundary` (1),
`mip` (2), `mip-boundary` (1), `resolve` (2)). Controlled: 32x32 target
(fixed for every case — this experiment does not vary target size),
identical authored VS/FS pattern per attachment count/format, identical
clear color (0.125,0.25,0.375,0.5), identical drawn fragment output
(0.25,0.5,0.75,0.5) or the R32Float-specific value for the `i2` MRT-mixed
case, identical viewport, one triangle instanced 1x, one command buffer
per case, one case per fresh process.

## 5. Expected observation and refuters

Stated per-hypothesis in section 3. General refuter shared by all: a
byte mismatch between the two officially gated runs (`m4-20260828-run01`
vs `run02`) in any field NOT already known/proven non-deterministic (see
section 7) falsifies byte-exact reproducibility for that field and
demotes the associated claim to `PARTIAL`/`INFERRED` rather than
`HW-VALIDATED`.

## 6. Known confounders

- **GPU-allocator-address-dependence.** As in EXP-0048/EXP-0108, the
  5-byte surface-address subfield at each k-record's relative `+0x08`
  (low 40 bits of that qword, reconstructing to `VA>>4`) is
  allocation-schedule-dependent and is masked to zero before any
  cross-run byte-exact comparison — see `CAPTURE_CONTRACT.json`
  `address_normalization`. This experiment additionally masks 2 specific
  bytes within the (32 KiB, uncharacterized, out-of-scope) `clear-color-
  arena` role at fixed relative offset `+0x536`/`+0x537` (decimal
  1334/1335 in the captured window), found nondeterministic between two
  dry runs of the SAME case with no configuration change — see section 7.
- **Client-buffer VA aliasing with a named role** — see section 2 finding
  4. Addressed at the root (no client `MTLBuffer` render targets); the
  frozen harness never allocates a client-visible buffer for a color,
  depth, stencil, or resolve target.
- **`mach_vm_read_overwrite` transient read failures** — see section 2
  finding 5. Mitigated with a widened retry budget (40 tries * 10 ms);
  NOT proven eliminated, only proven sufficient across the diagnostic
  phase's own repetitions. The officially gated capture's own
  `--captured` gate still tolerates a bounded number of read-timing
  flakes (budget: <=3 across the 16-case x 2-role-of-interest matrix,
  narrower than EXP-0108's <=5-over-40-cases budget since this matrix is
  smaller and the retry fix is expected to all but eliminate the flake,
  not just bound it) — any occurrence is logged and does not silently
  pass.
- **Two distinct registrations per render-target-shaped allocation** and
  **allocator-order sensitivity of unnamed regions** — both already
  documented by EXP-0108's own confounders section and inherited
  unchanged; `attachment-slot-b`'s non-reproduction (H5) is itself
  consistent with this class of confounder, not necessarily evidence that
  EXP-0108's own finding was wrong on ITS harness.
- **Compiler-generated per-shader epilog differences** (EXP-0091/EXP-0093:
  the ordinary unconditional fragment-program epilog, not a BG/EOT
  program) are out of scope here exactly as in EXP-0108; this experiment
  does not read or interpret the 4 GiB-aligned code window's content.
- **Fresh-process allocator determinism** is relied upon for the cross-run
  gate and is re-verified by the gate itself (`verify.py --captured`), not
  assumed.

## 7. Raw-record schema (frozen; single source of truth `run.py`)

`03_results.jsonl` (gated, cross-run byte-exact after masking): per case,
`i`, `name`, `axis`, `boundary`, `status`, `cb_status`, `cb_error`, `rts`
(the probe's own authored readback — already fully deterministic, our own
bytes), and `named` — for each of the five named roles that appear in this
matrix (`vdm-command-state`, `fixed-function-render-state`,
`tiling-state`, `mrt-attachment-descriptors`, `clear-color-arena`;
`single-rt-color-descriptor`, `attachment-slot-b`, and
`sparse-tiler-param-header` are recorded if present but are not expected
per section 2 finding 6/H5): `present`, `size`, `content_captured`, and,
for `mrt-attachment-descriptors` only, `k_records` — the masked hex of
LOAD/STORE for k=0..7 (`+0x20+k·0x20` / `+0x220+k·0x20`, 0x20 bytes each,
address subfield `+0x08..+0x0c` zeroed) plus the arena's own two 0x20-byte
"header" words at absolute `+0x00` and `+0x200` (also address-masked at
the same relative sub-offset if a `+0x08` qword is present); for
`clear-color-arena`, a fixed 0x200-byte window's hex with the 2 known-flaky
bytes (relative offset `0x536`/`0x537`) masked.

`03_timing.jsonl` (ungated, never cross-run compared): `i`, `name`,
`duration_ms`, `stdout_raw`, `stderr_raw`, full unmasked inventory
(VA/size/role/captured/sha256/read-tries for every registered BO), and the
unmasked address subfields.

## 8. Environment / target / timeouts

Target: local Apple M4 / G16G, this host, macOS 26.6.2 (25G82), Metal 4
(Apple9), Apple clang, `xcrun` 72. Public Metal API + public IOKit
`IOServiceOpen`/`IOConnectCallMethod` selectors only (same technique as
`tools/iotrace` and EXP-0048/EXP-0108's interposers, independently
reimplemented here as a fork of EXP-0108's `wtrace.c` with the fixes in
section 2). Per-case hard timeout 60 s; build timeout 120 s; env-command
timeout 15 s. Two runs, `m4-20260828-run01` / `m4-20260828-run02`, each
case its own fresh process (16 cases), one variable changed from the
relevant axis baseline per case.

## 9. What this experiment does NOT attempt

- Component mapping / rotation / coherency bits: per `docs/descriptors/
  README.md`'s existing (A18) finding, the render-target PBE component
  byte is format-derived, not an independently steerable knob; this
  experiment does not invent a synthetic probe for a field that structural
  prior work already shows has no independent hardware knob to vary. If
  the gated capture's own format sweep (inherited via `d1`/`i2`'s mixed
  format) surfaces evidence to the contrary, it is reported, not assumed
  away.
- Program-ID ownership / BG-EOT program identity: explicitly out of
  P1.1's own scope overlap with P0.4/DRV-UAPI-04, owned by EXP-0108 and
  any successor; this experiment does not re-attempt EXP-0108's own
  program-record search.
- Attachment index boundary (0..7 valid, 8 fatal): already
  `HW-VALIDATED` by `EXP-0117` (`docs/P0-P1-CLOSURE.md` cites it); not
  re-probed here to avoid a redundant, uninformative fatal-abort case —
  cited instead.
- 8x MSAA rejection mode: already documented (`docs/pipeline/README.md`,
  sourced from EXP-0021/A18); not re-probed.
- Width/height boundary (16384 max): already `HW-VALIDATED`
  (EXP-M4-08/EXP-G1b, both PBE-specific); not re-probed.
- Compressed/ASTC/BC formats, sparse residency, cube/cube-array
  attachments, indirect/ICB-driven render passes, layered rendering via
  `[[render_target_array_index]]` in the vertex/geometry stage (this
  experiment only exercises the `MTLRenderPassColorAttachmentDescriptor
  .slice`/`.level` host-side selection path), any A18 Pro evidence: all
  untested, named here as explicit remaining scope for a successor.

## Clean-room provenance

```text
Clean-room provenance: HW-PROBE / DATA-TRACE / OWN-SHADER
Inputs inspected: complete authored MSL generated per case from
  harness/probe.m; authored render-pass config JSON; IOKit call/resource-map
  metadata for every BO the process registers; capped content for a
  pre-registered, bounded set of small structured control/descriptor
  regions (the same known-role list as EXP-0108, reproduced verbatim in
  harness/wtrace.c)
Apple binary introspection: NONE
Apple auxiliary/helper program bytes committed: NONE (hash-only outside the
  bounded named-role set; the 4GiB-aligned code window is excluded from
  content capture entirely, by construction in harness/wtrace.c)
Pointer following: NONE (region identification is either a fixed named VA
  or per-case JSON metadata from our own probe; the one address-
  reconstruction formula in use, EXP-0048/EXP-M4-08's low40<<4, is applied
  only to already-established color/depth/stencil/resolve descriptor
  k-records, never to select or follow into another region's content)
Reproduction: see README.md
```
