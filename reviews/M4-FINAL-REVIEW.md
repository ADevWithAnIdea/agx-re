# M4 Final Consistency + Acceptance Review

**Reviewer role:** final gate for the Apple **M4** validation of the clean-room A18 Pro GPU docs.
**Bar (formal):** `docs/` (A18 baseline) **+ `docs/m4-deltas.md`** must suffice to implement a full
M4 GPU userspace driver from the documentation alone.
**Scope:** host-only, read-only. Adversarial. Method: whole-tree `grep` of every M4 coverage-sweep
correction against `docs/`, then a per-subsystem docs-only implementability pass.

**Headline:** Consistency = **SPLIT-BRAIN FOUND** (not consistent — the coverage-sweep corrections
landed in the *authoritative* spec docs but were **not propagated** to the derived/reference docs, and
in three cases not into `m4-deltas.md` itself). Acceptance = the authoritative spec for each subsystem
is implementable, **but the gate is NOT clean** until the split-brain below is reconciled — one stale
formula (`aux = image_bytes/128`) is memory-unsafe at bpp≠4 and appears in a *spec* doc
(`descriptors/format-table.md`) and in `m4-deltas.md`.

---

## (1) Consistency sweep — SPLIT-BRAIN LIST

For each landed correction: the authoritative doc is correct; the docs listed under "STALE" still carry
the superseded value as current fact. `ROADMAP.md` occurrences are the historical A18 status log (they
describe the pre-M4 state chronologically) → **low severity**, listed for completeness. Everything else
is a doc a driver author reads as authoritative → **must fix**.

### A. Compression aux size — `numTexels/32` (NOT `image_bytes/128`)  ⛔ HIGH
Authoritative & CORRECT: `tiling/README.md` §4.3 (`aux_bytes = numTexels/32 = paddedImageBytes/(32·bpp)`,
EXP-M4-07, memory-safety). The old `/128` over-allocates 2×/4× at bpp8/16 and **under-allocates 4×/2× at
bpp1/bpp2 → buffer overrun** — a real memory-safety bug where still stated.

| Doc:line | Stale text | Should be |
|---|---|---|
| **m4-deltas.md:71** | `aux=image/128` (delta doc never mentions EXP-M4-07 / numTexels/32) | `numTexels/32` |
| **descriptors/format-table.md:367** | `aux_bytes = image_bytes / 128` | `numTexels/32` |
| **porting-guide.md:288** | `aux metadata buffer = image_bytes/128` | `numTexels/32` |
| **capability-completeness.md:384** | `aux = image/128` | `numTexels/32` |
| **mesa-userspace-requirements.md:124** | `aux placement + size (image/128 …)` | `numTexels/32` |
| **tiling/README.md:280** (§5, compression×mipmaps) | `size ≈ totalImageBytes/128` | `Σ paddedLevel/(32·bpp)` |

*Note:* `descriptors/README.md` compression section (lines 30–32, 89–112) is CLEAN — it defers the size
to `tiling/ §4` and never restates the ratio. `tiling/README.md:233,236` mention `/128` only to flag it
as WRONG for bpp≠4 — those are correct/contextual, not stale.

### B. Tile edge `T` — bpp1→**128**; `T = largest pow2 with T²·bpp ≤ 16KiB` (NOT "T=64 for bpp≤4")  ⛔ HIGH
Authoritative & CORRECT: `tiling/README.md` §1.1 (lines 24–29, 63, 68, 84; bpp1→128 EXP-M4-06).

| Doc:line | Stale text |
|---|---|
| **porting-guide.md:271–272** | `T = 64 for bpp ≤ 4, T = 32 for bpp ≥ 8` (misses bpp1→128) |
| **capability-completeness.md:381** | `tile edge T = 64 for bpp ≤ 4 / 32 for bpp ≥ 8` |
| **mesa-userspace-requirements.md:120** | `tile edge T = 64 for bpp ≤ 4 / 32 for bpp ≥ 8` |
| **mesa-userspace-requirements.md:121** | `tile edge T = 64 bpp≤4 / 32 bpp≥8` |
| ROADMAP.md:230 | `T=64/32 boundary` (historical log — low severity) |

*`m4-deltas.md:70` leads with "T=64 bpp≤4 / 32 bpp≥8" but §5 (lines 73–76) narrates the bpp1→128 +
G-column correction — acceptable as before/after narrative, though the lead line reads as fact.*

### C. Column granule — `cols = round_up(ceil(W/T), G)`, `G = 0x4000/(T²·bpp)` (NOT flat `ceil(W/T)`)  ⛔ HIGH
Authoritative & CORRECT: `tiling/README.md` §1.1 (lines 26–39, 83–84; G=2 for bpp2/bpp8 → even columns,
EXP-M4-04/05). Flat `ceil(W/T)` is wrong for bpp2 and bpp8 (off by whole pages).

| Doc:line | Stale text |
|---|---|
| **porting-guide.md:273** | `cols = ceil(W/T)` (flat; no G) |
| **capability-completeness.md:381** | `cols=ceil(W/T), pad multiple-of-T` (flat; no G) |
| **mesa-userspace-requirements.md:120** | `cols=ceil(W/T) + … MULTIPLE-OF-T` (flat; no G) |
| ROADMAP.md:230, 243, 252 | `cols=ceil(W/T)` (historical log — low severity) |

### D. RT attachment format code = byte **+0x21** (NOT +0x22)  ⚠ MEDIUM
Authoritative & CORRECT and mutually consistent: `descriptors/README.md:130–140`, `pipeline/README.md:64`,
`cmdstream/README.md:104` (full word `(0xf<<28)|(swizzle<<16)|(byte1<<8)|(byte0&~0x20)`, 43/43 formats).
The three spec docs the task asked to cross-check **all agree** on +0x21, hi-nibble decode, and aniso.

| Doc:line | Stale text |
|---|---|
| **mesa-userspace-requirements.md:111** | `render-target attachment … pixel-format@+0x22` |
| ROADMAP.md:201 | `format @+0x22` (status doc — low severity) |
| descriptors/README.md:134 (minor) | correction-note still says "`pipeline`/`cmdstream` state byte+0x22" — but those were since fixed to +0x21, so the note's cross-reference is itself stale/confusing |

### E. Occupancy tier = **peak register pressure** (NOT the `f0≥12` / "~12-GPR" threshold)  ⚠ MEDIUM
Authoritative & CORRECT: `cmdstream/README.md:190–203` (EXP-M4-09/CMD-8, A18-cross-confirmed; explicitly
"'sets iff ≥12 GPRs' is FALSE … driven by the compiler's peak register-pressure / occupancy class").

| Doc:line | Stale text |
|---|---|
| **porting-guide.md:100** | `~12-GPR 2-level occupancy tier (config bit23)` |
| **porting-guide.md:471** | `~12-GPR occupancy tier` |
| **isa/README.md:195–199** | frames bit23 as a GPR-count threshold ("clear ≤11 / set ≥12 GPRs … INTERPOLATED"). RT-7 *softened* it to "interpolated" but it was never updated to the later peak-register-pressure framing that CMD-8 says supersedes the ≥12 framing entirely. |

### Corrections that ARE fully propagated (no split-brain) — verified GREEN
- **CDM threadgroup field verbatim for barrier/tgmem kernels** — `cmdstream/README.md:43` (CMD-8). ✅
- **Per-attachment clear color @ `0x10000128000 + 0x170 + k·0x10`** — `pipeline/README.md:79`; `cmdstream/README.md:105`. ✅
- **ISA saturate = native byte+7 bit1 (0x02)** — `isa/README.md:148–154`. ✅
- **ISA high-register `(reg<<1)|is32`** — `isa/README.md:143,174,239,402` + `encoding-tables.md`. Consistent. ✅
- **ISA integer immediate inline ≥65536** — `isa/README.md:243–246` (EXP-M4-10 ISA-4). ✅
- **ISA `device_store` byte+8 inert** — `isa/README.md:402` (EXP-M4-10 ISA-1). ✅
- **aniso >16× → 1× (Metal clamps to 1×, not 16×; >16× untested)** — `descriptors/README.md:49,76`, `descriptors/format-table.md:268,403`, consistent with `capability-*`/`hypotheses` (which track the separate "does injected >16× work on HW" question). ✅
- **Sampler stride 0x20, `num_samplers=(term−samp)/0x20`** — `cmdstream/README.md:283`, `descriptors/README.md:42`. ✅
- **Format hi-nibble decode (`numtype<<5|sizeclass`)** — agrees across `descriptors`/`pipeline`/`cmdstream`. ✅
- **+3 non-2D texture read codes** — `isa/README.md:452,725`, `agx3.xml`. ✅

**Consistency verdict: NOT consistent — SPLIT-BRAIN in 5 correction families across 4 derived docs
(`porting-guide`, `mesa-userspace-requirements`, `capability-completeness`, `descriptors/format-table`)
plus `m4-deltas.md` itself (aux, and the T/cols lead line) and one intra-file miss (`tiling/README §5`).**
The pattern is uniform: the sweep edited the *authoritative* subsystem doc (`tiling/`, `cmdstream/`,
`pipeline/`, `descriptors/README`) and the summary/reference layer was never re-synced.

---

## (2) Acceptance — implementable-M4-driver-from-[A18 docs + m4-deltas]

Verdict per subsystem is against the **authoritative** spec doc (what a diligent implementer converges on).
"Blocking gap" = cannot emit from docs. The split-brain above is tracked as **required-fix** rather than a
capability gap, because the authoritative spec is present and correct — but see the overall caveat.

| Subsystem | Verdict | Basis / residual |
|---|---|---|
| Compiler / ISA | **PASS** | `isa/README.md` + `encoding-tables.md` + `m4-deltas §1/§2` (97.4% M4 byte coverage, round-trip green, 96-GPR machine model splice-validated). Residue = out-of-scope blend microprogram + SFU tail + ⏳ operand sub-fields (round-trip-green templates). |
| Command stream (CDM/VDM/USC/state) | **PASS** | `cmdstream/README.md` + `m4-deltas §3` (byte-identical, HW-run on M4). Occupancy-tier correction present here (authoritative). |
| State packets | **PASS** | `cmdstream/README.md` (depth/stencil/raster/PPP, clear-color BO). |
| Descriptors | **PASS** | `descriptors/README.md` + `format-table.md` + `m4-deltas §4` (32B texture, 8B sampler, PBE two-descriptor RW, 14-bit dims, +0x21 format). ⚠ `format-table.md:367` carries the stale aux formula (split-brain D-item is here). |
| Tiling & compression | **PASS (authoritative) / required-fix** | `tiling/README.md` is complete & correct (T rule, G-granule cols, aux=numTexels/32, block/3D/array/MSAA, mip). ⚠ every *derived* doc + `m4-deltas §5` contradicts it (split-brain A/B/C). Codec bitstream + state-byte semantics honestly opaque (disable-fallback documented). |
| TBDR / pipeline | **PASS** | `pipeline/README.md` + `m4-deltas §6` (32×32 tile, MSAA, userspace sample positions @+0x40, memoryless). 10-core = no userspace field. |
| Kernel interface | **PASS** | `kernel-interface.md` + `m4-deltas §7`. M4 deltas explicit: user-client **`AGXAcceleratorG16G`** (§7), **10 cores** (§0/§7), **maxBufferLength ~8.88 GiB — "query the device, don't hard-code"** (§0/§7). |
| Capabilities | **PASS** | `capability-matrix.md` + `capability-completeness.md` + `m4-deltas §8` (zero capability deltas; 189 native / 11 emulated / 5 kernel / 9 NYC apply unchanged). |

**M4-specific deltas — clearly documented? YES.** `AGXAcceleratorG16G`, 10 GPU cores, and
`maxBufferLength > 4 GiB (query, do not hard-code)` are all called out explicitly in `m4-deltas.md`
§0 and §7 (and the delta summary table). SIMD width / maxTG / tg-mem / sparse page / arg-buffer tier all
validated IDENTICAL. Codename `applegpu_g16g` recorded.

**Overall acceptance verdict: CONDITIONAL PASS — NOT a clean gate yet.**
No *capability* blocking gaps: every subsystem is emittable from its authoritative spec, and the M4 config
deltas are documented. **However the gate cannot be signed off as clean** because the acceptance basis is
"A18 docs **+ m4-deltas.md**", and `m4-deltas.md` itself still states `aux = image/128` (memory-unsafe at
bpp≠4) with no pointer to the numTexels/32 correction, and a driver author reading the reference layer
(`porting-guide` / `mesa-userspace-requirements` / `descriptors/format-table`) is handed three
contradictory, partly memory-unsafe tiling formulas with no signal which wins. That is exactly the failure
mode the consistency job exists to catch. **Required to clear the gate:** propagate corrections A–E to the
docs listed (priority: `m4-deltas.md:71` aux + T/cols lead, `descriptors/format-table.md:367`,
`porting-guide.md` §1.1/occupancy, `mesa-userspace-requirements.md`, `capability-completeness.md`,
`tiling/README §5`). None require new experiments — the authoritative values already exist and are
HW-validated; this is pure text propagation.

---

## (3) Acceptable-residue count

**~11 acceptable-residue clusters** (consistent with ROADMAP's "11 clusters + 5 polish"), all documented
with a fallback or honest ⏳/opaque flag — **none blocking**:

1. Fragment **blend microprogram** — deliberately out of scope (documented).
2. Compression **block codec bitstream** + state-byte numeric semantics — opaque; disable-fallback documented.
3. Per-sample **MSAA compression aux ratio** — grows with N, exact divisor not pinned.
4. **RT BVH build / intersector AS-select sub-fields** — INFERRED, round-trip-green templates (EXP-O2C over-claim reverted).
5. **ISA operand sub-fields** — `device_store` data-reg exact position (amode-dependent), integer srcA/srcB exact widths — round-trip-green templates.
6. **Dynamic Caching dynamic curve** + full occupancy/latency-throughput curve — microarch, NYC (perf-only, not an encoding).
7. **Scratch-base location** — follow-up.
8. **Spill-frame marker (0x60)** exact semantics — byte+3 live, role follow-up.
9. **USC shared-layout magic bytes** — partial.
10. **CDM** indirect global/local mode + barrier bits + per-gen extra word — partial.
11. **PBE** full bit layout render-only Rotate90/Flip/Mode fields + SW sideband — partial.

Plus the **9 NYC capability rows** (capability-completeness): 6 microarch-only + 3 truly Metal-unreachable
(aniso>16×, wide/smooth lines, conditional rendering) — honestly excluded, Metal-exposed-not-exercised = 0.

These are correctly distinguished from the **split-brain (§1)**, which is *not* acceptable residue — it is
stale-value contradiction of already-established facts and must be reconciled.

---

## Bottom line
- **Consistency:** ✗ split-brain found — 5 correction families stale across `porting-guide`,
  `mesa-userspace-requirements`, `capability-completeness`, `descriptors/format-table`, and `m4-deltas.md`
  itself (+ `tiling/README §5`). Authoritative subsystem specs are all correct; the summary/delta layer was
  not re-synced.
- **Acceptance:** authoritative specs are implementable and the M4 deltas (G16G / 10 cores / buf>4 GiB) are
  documented — **but CONDITIONAL**: the gate isn't clean while `m4-deltas.md` and a `descriptors/` spec doc
  carry a memory-unsafe aux formula and contradictory tiling rules. Fix the §1 list (text-only, no new
  experiments) and the gate passes.
- **Acceptable residue:** ~11 clusters + 9 NYC capability rows — none blocking.
