# PRE_REGISTRATION — EXP-0108: M4 BG/EOT program-record ABI matrix

Frozen before the first live capture run. Pin: git revision recorded in
`CAPTURE_CONTRACT.json` at freeze time (see that file; do not gate on live
`HEAD` per `experiments/SUBAGENT_BRIEF.md`).

## 1. Question and why it matters

`APPLE9_RE_IMPLEMENTATION_GAPS.md` DRV-UAPI-04 / `docs/P0-P1-CLOSURE.md` P0.4:
the unchanged Asahi UAPI requires userspace to supply BG (background/load),
EOT (end-of-tile/store), partial-BG and partial-EOT program records. Without
their ABI a driver cannot start a render pass. `EXP-0048-bg-eot-pbe`
established reproducible empty-tile Clear/Store and Load/Store behavior and
six PBE format/control record variants across a narrow 12-case matrix and
four fixed allowlisted state BOs, but explicitly did **not** locate a BG/EOT
tagged program address, a resource-specification bit layout, a program
input/output ABI, or partial-render records; its own "Open items" name
"BG/EOT/partial program tags, resource specs, ABI" as unresolved.

This experiment widens both the traced-state surface (every registered
process BO, not four fixed ones) and the configuration matrix (load/store
action, MRT count, mixed format, per-format sweep, MSAA + resolve,
memoryless, depth, stencil, combined depth+stencil, empty-tile, and a
partial-render probe) to establish as much of the program-record ABI as
this evidence allows, and to produce a precise, falsifiable negative where
it does not.

## 2. Falsifiable hypotheses

- **H1 (program pointer exists and varies structurally).** There exists a
  captured region, distinct from the four EXP-0048 roles, whose presence,
  size, or content is correlated with render-pass configuration in a way
  consistent with a BG/EOT program or resource-specifier record.
  Falsifier: across the full 40-case matrix, no such region is found — i.e.
  every configuration-correlated difference is fully explained by the
  already-known descriptor fields (format/control words, clear-value
  floats, action-selector bytes) and by benign allocator-order noise.
- **H2 (depth/stencil produce a captured state record).** EXP-0048 stated
  depth/ZLS as firmware-managed/not captured. Falsifier (of the *prior*
  claim): a depth or stencil attachment reproducibly adds a distinct
  captured region relative to an otherwise-identical baseline, independent
  of format/MRT changes (isolated by a same-shape format-only control case).
- **H3 (format conversion is fixed-function, not program-supplied).** If no
  distinct executable-shaped program record is found to vary with pixel
  format (H1's negative holds across the format axis specifically), then
  for the tested formats, conversion must be performed by fixed-function
  hardware paths already encoded in the PBE descriptor's format word, not by
  a userspace/driver-supplied program.
- **H4 (partial-render leaves no distinct userspace-visible record).**
  Forcing a much larger primitive/pixel workload than a small reference
  case does not introduce a new BO role or grow the known control BOs
  (VDM/FF-state/tiling-state) by more than ordinary per-draw geometry
  content, within the tested magnitude.

## 3. Independent / controlled variables

Independent variable: the case's `axis` and its one or two varied fields
(see `harness/casematrix.py`, single source of truth, 40 cases across 11
axes). Controlled: 32x32 target (except the `partial` axis, which
intentionally varies target size as its own controlled experiment),
identical authored VS/FS pattern per attachment count/format, identical
clear color (0.125,0.25,0.375,0.5) and per-attachment draw output
(0.25,0.5,0.75,0.5) or the R32Uint-specific (37,0,0,1), identical viewport,
one triangle instanced 1x unless the `partial` axis, one command buffer per
case, one case per process.

## 4. Expected observation and refuters

- If H1 holds: a specific new region (by size/hash multiset, VA-independent
  — see §6) appears/disappears correlated with a specific axis change and
  not with unrelated axis changes (isolated via the `format` axis as a
  negative control against `depth`/`stencil`).
- Refuter for H1/H2: the same region-count delta appears for an UNRELATED
  axis change (e.g. format-only), which would mean the signal is allocator
  noise, not attachment-type-specific state.
- Refuter for H3: an executable-shaped region (see content-capture policy,
  §7) is found to vary specifically with format, independent of MRT/action.
- Refuter for H4: `k1` (64x64, 1 instance) vs `k2`/`k3`/`k4` (2048x2048
  and/or 200000 instances) show a NEW role, or the known roles change size
  class (not just content), beyond ordinary geometry/viewport bytes.

## 5. Known confounders

- **Allocator-order sensitivity.** An early iteration of this harness tried
  to identify a depth/stencil candidate region by VA arithmetic anchored on
  a reconstructed buffer address; the offset shifted between two harness
  revisions that differed only in unrelated JSON-parsing code executed
  before the Metal calls. VA-based identification of *new, unnamed* regions
  is therefore explicitly OUT of the frozen design (see run.py's
  in-source methodological note). The frozen design uses only
  allocation-order-independent signals: role assignment for the 8
  pre-established named roles (fixed absolute VAs, validated stable across
  this experiment's own exploration and EXP-0048/EXP-M4-08/09), and a
  VA-free size+hash multiset for everything else.
- **Two distinct registrations per render-target buffer.** A buffer-backed
  color target receives (at least) two separate sel-9 registrations: the
  client `MTLBuffer`'s own CPU-side registration (exact requested size, e.g.
  0x4000) and a second, larger fixed-size-class (0x20000) registration
  associated with the texture view built on top of it. Both are legitimate,
  both are "ours" (derived from a buffer we allocated), and only the first
  is what EXP-0048/EXP-M4-08's address-reconstruction formula (`low40<<4`
  of the qword at record+0x08) resolves to.
- **Single-RT vs MRT-arena descriptor layout differ internally.** The
  single-attachment path (`single-rt-color-descriptor`, fixed VA
  `0x10000110000`) uses the three-segment LOAD(+0x000)/RENDER(+0x300)/
  STORE(+0x600) layout documented in `docs/pipeline/README.md`, with the
  populated sub-record at segment-relative +0x20; the MRT/MSAA/memoryless
  path (`mrt-attachment-descriptors`, fixed VA `0x10000018200`) uses the
  k=0..3 fixed 0x20-byte-stride array at +0x20 (LOAD) / +0x220 (STORE).
  Conflating these two layouts (reading MRT-style offsets from the
  single-RT region) was caught in this experiment's own dev exploration
  before freezing (see `run.py` `ROLE_WINDOW`).
- **The `0x10000018200`-based tiler-heap arena carries unrelated incidental
  content** (previously documented: a vertex-buffer allocator alias at
  `+0x500`). Whole-region hashing of that arena is noisy; only the specific
  established k-record offsets are trusted for field-level content.
- Compiler-generated per-shader epilog differences (established in
  EXP-0091/EXP-0093 as the ordinary unconditional fragment-program epilog,
  not a BG/EOT program) are a possible confound if the 4GiB-aligned code
  window's size or hash is naively read as evidence of a new BG/EOT
  program; this experiment treats code-window size (always observed 0x10000
  across this experiment's exploration, for every tested configuration) as
  a coarse self-check only, never disassembles it, and never reports its
  content.
- Fresh-process allocator determinism (established by EXP-0048's own
  byte-identical two-run repeat) is relied upon for the cross-run gate; it
  is re-verified here as part of `captured()`, not assumed.

## 6. Content-capture policy (frozen; implemented in `harness/wtrace.c`
`capture_eligible()`)

Full content (capped to size, max 0x20000 bytes) is captured for:
1. The three EXP-0048 low fixed-VA roles: `0x18000` (vdm-command-state),
   `0x58000` (fixed-function-render-state), `0x68000` (tiling-state).
2. Any BO in the `0x10000000000`-based sparse global range, EXCLUDING
   `[0x10000000000, 0x10000020000)` — the 4GiB-aligned code window plus a
   doubled safety margin (EXP-0042 established the code window is exactly
   this base and, in this experiment's own exploration, is always exactly
   0x10000 bytes and holds only our own compiled VS+FS) — and EXCLUDING
   `0x6f00000000` (one distant, unclassified, config-invariant region out of
   this experiment's scope), whose size is `<= 0x20000` bytes.

Everything else (the code window itself, any region above 0x20000, the
distant one-off region, and any low VA `< 0x10000000000` other than the
three named ones) gets metadata + a SHA-256 content hash ONLY — no bytes are
read into any committed artifact, and for the code window specifically no
bytes are even copied out of the process for hashing beyond what
`capture_eligible` already governs. This bounds risk: every region this
experiment ever stores bytes from has, in prior work (EXP-0048, EXP-0042,
EXP-M4-08/09) and this experiment's own exploration, been either our own
data or small structured descriptor/control content — never executable
code outside the excluded window. If a captured region nonetheless turns
out, on inspection of only its FIRST bytes and size class, to look
executable/instruction-shaped, this experiment's committed evidence records
only its size and SHA-256 — never its bytes, never a semantic
interpretation — per `CLAUDE.md`'s ban on committing or interpreting
Apple-authored precompiled program content.

Of the 8 named roles, only the two color-descriptor-bearing ones
(`mrt-attachment-descriptors`, `single-rt-color-descriptor`) get per-record
field-level extraction (the k=0..3 LOAD/STORE 0x20-byte windows, per
role-specific offsets in `run.py` `ROLE_WINDOW`); the surface-address
subfield within each window (5 bytes at record-relative +0x08, established
by EXP-0048/EXP-M4-08 as `VA = low40<<4`) is masked to zero in the gated
record and recorded unmasked only in the ungated timing side-channel (see
`CAPTURE_CONTRACT.json` "address_normalization").

## 7. Raw-record schema (frozen; single source of truth `run.py`)

`03_results.jsonl` (CASE_KEYS, gated, cross-run byte-exact): `i`, `name`,
`axis`, `probe_status`, `cb_status`, `cb_error`, `rts`, `named` (per-named-
role size/sha256/+field windows for the 2 color-descriptor roles, address
subfield masked), `unnamed_regions` (VA-free sorted size+sha256+captured
multiset), `status`.

`03_timing.jsonl` (TIMING_KEYS, ungated, never cross-run compared):
`i`, `name`, `duration_ms`, `stdout_raw`, `stderr_raw`, `inventory_full`
(complete inventory WITH VA, informational), `named_addresses` (unmasked
address subfields), `resource_gpu_addresses`.

## 8. Environment / target / timeouts

Target: local Apple M4 / G16G, this host, macOS 26.6.2, Metal 4, Apple
clang. Public Metal API + public IOKit `IOServiceOpen`/`IOConnectCallMethod`
selectors only (the same technique as `tools/iotrace` and EXP-0048's
`allowtrace.c`, independently reimplemented). Per-case hard timeout 90s;
build timeout 120s; env-command timeout 15s. Two runs,
`m4-20260828-run01` / `m4-20260828-run02`, each its own process per case
(40 cases), one variable changed from the `a1` baseline per case where the
axis structure allows it.

## 9. What this experiment does NOT attempt

Layered/array-texture rendering, cube maps, mip levels beyond level 0,
compressed/ASTC/BC formats, sparse residency, 8x MSAA (already established
Metal-rejected), indirect/ICB-driven render passes, tessellation/geometry
stages, any A18 Pro evidence, and — per §6 — any disassembly or semantic
interpretation of executable-shaped content. Closing P0.4 fully requires
independently generated, authored BG/EOT programs the hardware consumes;
this experiment characterizes the ABI surface it can reach without one and
states precisely what remains (see `RESULTS.md` §"What P0.4 still needs").

## Clean-room provenance

```text
Clean-room provenance: HW-PROBE / DATA-TRACE / OWN-SHADER
Inputs inspected: complete authored MSL (generated per case from
  harness/probe.m); authored render-pass config JSON; IOKit call/resource-map
  metadata for every BO the process registers; capped content for a bounded,
  pre-registered set of small structured control/descriptor regions (see §6)
Apple binary introspection: NONE
Apple auxiliary/helper program bytes committed: NONE (hash-only outside the
  bounded named-role set; code window excluded from content capture entirely)
Pointer following: NONE (all region identification is either a fixed named
  VA or a VA-free size/hash comparison; no value read from region content is
  ever used to select another region)
Reproduction: see README.md
```
