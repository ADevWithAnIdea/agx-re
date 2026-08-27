# DOC-01 increment — 2026-08-27 (documentation reconciliation)

Scope honoured: only `docs/tiling/*.md`, `docs/cmdstream/*.md`, `docs/descriptors/*.md` were edited.
No new hardware claims; every edit re-expresses a fact already established by a committed experiment
cited inline. Nothing committed (orchestrator reviews).

Source gap: `APPLE9_RE_IMPLEMENTATION_GAPS.md` → **DOC-01** ("Authoritative specifications and stale
references": broken `../mesa` references, superseded facts non-normative, ROADMAP/reviews/cmdstream
open-items/sample-positions/tiling reconciliation, bpp1 tile edge 128 vs stale `T=64 bpp<=4` wording).

---

## PART 1 — tiling tile-edge wording (`docs/tiling/`)

**Finding: `docs/tiling/` contains NO remaining stale `T=64 for bpp≤4` assertion.** The validated rule
("T = largest pow2 with T²·bpp ≤ 16 KiB", bpp1→128) is already stated with the EXP-M4-06 citation in
§1.1 (rule text L24, code comment L29, per-bpp table L36), §1.4 (L84), and §1.3 (L68); §1.5/§1.6/§3 use
the same rule at block/plane/mip granularity. The stale rule survives in `docs/tiling/README.md` L25
only as a *correction note* (correct and intentional).

Edit made (citation-strengthening only, no fact change):

| file:line | change | citation |
|---|---|---|
| `docs/tiling/README.md:63` (§1.2) | `…largest pow2 with T²·bpp≤16KiB, §1.1); tiles are laid…` → `…largest pow2 with T²·bpp≤16KiB, §1.1; the bpp1=128 value HW-shown by EXP-M4-06, per-bpp coverage EXP-M4-07); tiles are laid…` | `experiments/EXP-M4-06-a18-bpp12-granule/RESULTS.md` (A18 320-wide r8 → cols 3, tile 128²·1 = 16 KiB); `experiments/EXP-M4-07-tiling-coverage/RESULTS.md` (0-mismatch at bpp1/2/4/8/16) |

**Flagged (outside my editable scope) — stale tile-edge rule still asserted as fact:**
- `docs/m4-deltas.md:86` (§5 first sentence): "Tiled Morton (T=64 bpp≤4 / 32 bpp≥8), cols=ceil(W/T)" —
  superseded later *in the same section* (L88–L92 record the G-granule rule and "bpp1 uses tile edge
  T=128 (not 64)", EXP-M4-05/06). Note: the dispatch's "m4-deltas.md Bonus section" does not exist as a
  heading; the tiling section is §5 and carries the correction.
- `docs/mesa-userspace-requirements.md:146`: "tile edge **T = 64 bpp≤4 / 32 bpp≥8**" — superseded by
  `docs/mesa-userspace-requirements.md:145` (same file, one row up), which already states the corrected
  rule with EXP-M4-06.

---

## PART 2 — broken relative-path survey (`docs/**/*.md`)

Method: extracted every markdown link target and every path-like backticked/plain token, resolved each
against three bases (file's dir, `docs/`, repo root), brace-expanded `{a,b}`, resolved globs; then
manually verified each survivor against the experiment trees.

### Result for the editable dirs (`docs/tiling/`, `docs/cmdstream/`, `docs/descriptors/`)
**No unambiguous broken reference — no path edits made.** Every file reference in these three dirs
resolves:

| file:line | reference | status |
|---|---|---|
| `docs/cmdstream/README.md:150–151,233,255,257,339,355` | `../../experiments/EXP-0049…/analysis/{summary.json,report.txt}`, `EXP-0054…/analysis/…`, `EXP-0055…/analysis/…`, `EXP-0055…/raw/m4_20260817_run{01,02}/04_boundary_preflight.json`, `EXP-0053…/analysis/…`, `EXP-0052…/analysis/…` | **exists** (verified on disk) |
| `docs/tiling/README.md:275` | `raw/til_a18_verify.txt` | **exists** — `experiments/EXP-M4-07-tiling-coverage/raw/til_a18_verify.txt` (experiment-relative shorthand, experiment named in the same sentence) |
| `docs/descriptors/format-table.md:112` | `experiments/EXP-M4-08-descriptor-coverage/analysis/format_decode.txt` | **exists** |
| `docs/descriptors/README.md:83` | `[format-table.md](format-table.md)` | **exists** |

### Genuine broken references found elsewhere in `docs/` (NOT edited — outside the editable file set)

| file:line | current text | target status | proposed fix |
|---|---|---|---|
| `docs/isa/README.md:14` | "…descriptor lengths for the four-byte byte0 `0x60` form…" blockquote cites `experiments/EXP-0041-m4-scratch-helper-abi` | **missing** — the directory is `experiments/EXP-0041-scratch-helper-abi` (only unresolvable experiment slug in all of `docs/`) | rename the citation to `experiments/EXP-0041-scratch-helper-abi` |
| `docs/ROADMAP.md:103` | "stop deferring to `tools/db.json`" | **missing** — the DB is `tools/agx-isa/db.json` | change to `tools/agx-isa/db.json` |
| `docs/ROADMAP.md:6`, `docs/mesa-userspace-requirements.md:4,5,40,53,54`, `docs/kernel-interface.md:19,251,268,369` | `../mesa/src/asahi`, `../mesa/src/gallium/drivers/asahi`, `../mesa/include/drm-uapi/asahi_drm.h`, `../mesa/src/asahi/libagx/libagx_dgc.h`, `../mesa/src/asahi/lib/agx_device.c` | **unresolvable in this checkout**: `mesa/` is a gitlink (mode 160000, no `.gitmodules`) whose tree is not materialized — `ls mesa/` is empty | materialize the pinned Mesa checkout; then re-verify. `mesa/src/gallium/drivers/asahi` is additionally likely a stale Mesa layout (modern Mesa has `src/asahi`); `mesa/src/poly/` (`mesa-userspace-requirements.md:183`, "renamed libagx") cannot be checked either way |
| `docs/mesa-userspace-requirements.md:77–96,129,139` | Mesa source citations `isa/AGX2.xml`, `isa/agx_minifloat.h`, `compiler/agx_*.c/py`, `genxml/cmdbuf.xml`, `layout/*`, `libagx/*`, `hk_*.c` | **unverifiable** (same cause: `mesa/` absent). They are Mesa-tree paths, not repo paths — resolving them needs the checkout | verify after materializing `mesa/`; no doc edit implied |
| `docs/hardware-overview.md:80` | `experiments/EXP-0002…/raw/metal_caps.txt` | **exists** (`experiments/EXP-0002-hw-identity-recon/raw/metal_caps.txt`); the `…` is an ellipsis, not part of the path | none |
| `docs/ROADMAP.md:166` | Mesa's `src/asahi/isa/AGX2.xml` | unresolvable (mesa absent) | verify after checkout |

### False positives ruled out (checked, resolve fine)
Experiment-relative shorthand in `docs/P0-P1-CLOSURE.md:65,75,76,78`, `docs/capability-completeness.md:350`,
`docs/capability-completeness-m5.md:73,142`, `docs/capability-matrix-m5.md:13` — every cited
`raw/…` / `analysis/…` file exists inside its named experiment (`EXP-0051`, `EXP-0052`, `EXP-0060`,
`EXP-0063`, `EXP-0066`, `EXP-M5-08`, `EXP-M5-12`). Bare experiment IDs (`EXP-M5-10`, `RT-4`, …) are
citation shorthand, not paths. `experiments/EXP-M4-*/`, `experiments/EXP-M5-*` globs resolve.
`gpu_knowledge/apple_official/{wwdc,msl_spec}` (root-relative) exist.

---

## PART 3 — superseded-value marking (`docs/cmdstream/`, `docs/descriptors/`)

### Aligned (edited)

| # | file:line | old → new | citation |
|---|---|---|---|
| 1 | `docs/descriptors/README.md:18` (texture-descriptor table, "type" row) | `byte0 bits[0:2]` / codes `1D=0, 2D=2, 2DArray=3, 2DMS=4, 3D=5, Cube=6 (1D/CubeArray/MSArray ⏳ untested)` → `byte0 bits[0:3] (low nibble)` / all nine codes `1D=0, 1DArray=1, 2D=2, 2DArray=3, 2DMS=4, 3D=5, Cube=6, CubeArray=7, 2DMSArray=8 — all HW-validated (EXP-0028; supersedes EXP-0015's 3-bit reading…)` | `experiments/EXP-0028*/RESULTS.md` §1 ("the type field is **4 bits** (`word0[0:3]`), not 3. … **2DMSArray=8** is new"; explicit "Correction to EXP-0015 / `docs/descriptors`") |
| 2 | `docs/descriptors/format-table.md:17` (§1 heading) | `(word0 bits[0:2] = byte0 low nibble)` → `(word0 bits[0:3] = byte0 low nibble — EXP-0028; supersedes EXP-0015's 3-bit bits[0:2] reading)` (also fixes the heading's internal 3-bit/low-nibble contradiction) | EXP-0028 §1 |
| 3 | `docs/descriptors/format-table.md:27–32` (§1 rows + note) | 1DArray `(likely 1) untested`, CubeArray `(likely 7) untested`, 2DMultisampleArray `(unassigned) untested` → codes `1`/`7`/`8` **HW-validated (EXP-0028 `type_1darray`/`type_cubearray`/`type_2dmsarray`)**; note "Codes 1 and 7 are not confirmed…" → "EXP-0028 HW-validated all nine codes … superseded (see also §8 and 'Extended format codes')" | EXP-0028 §1 table (`type_1darray` `0x21`, `type_cubearray` `0x27`, `type_2dmsarray` `0x28`) |
| 4 | `docs/descriptors/format-table.md:39` (§2 intro) | "`byte0` bits[0:2] carry the texture type" → "`byte0` bits[0:3] (low nibble) carry the texture type" | EXP-0028 §1 |
| 5 | `docs/descriptors/format-table.md:115` (§2c decode block) | `byte0 = arrangement[4:7] \| texture_type[0:2]` → `byte0 = texture_type[0:3] \| arrangement[5:7]<<5      # bit4 always 0 (EXP-0028 type field is 4 bits)` | EXP-0028 (4-bit type + `chanArr[4:7]`) + EXP-M4-08 §2c (`arr = byte0[5:7]`, bit4 always 0 — both already cited in that section) |
| 6 | `docs/descriptors/format-table.md:335` (§5 field map) | "texture type \| word0 bits[0:2]" → "texture type \| word0 bits[0:3] (byte0 low nibble; EXP-0028)" | EXP-0028 §1 |
| 7 | `docs/descriptors/README.md:145` | stray subagent meta-note `*(These are not my files to edit — flag for the orchestrator.)*` → "(`../pipeline/README.md` and `../cmdstream/README.md` both now state the corrected **byte+0x21**.)" (verified: `docs/pipeline/README.md:71` and `docs/cmdstream/README.md:155` both already carry the EXP-M4-08 DESC-1 correction) | EXP-M4-08 DESC-1 |
| 8 | `docs/cmdstream/README.md:46–51` (CDM record tail) | "⏳ threadgroup-memory-size field is elsewhere (not here)." → "Threadgroup-memory-size is also not here — it was later located in the **shader BO** (EXP-0024, see 'Compute config word + threadgroup-memory size' below)." (the ⏳ open-marker contradicted the resolved section at L317–319 of the same file) | `experiments/EXP-0024-usc-ppp-config/RESULTS.md` (`field = (tgmem_bytes << 2) \| 0x80` at `0x10000090000`, HW-validated 256…32768 B) |
| 9 | `docs/cmdstream/README.md:461–464` ("Open items") | "Compute: decode `+0x00` config/register word; find the threadgroup-memory-size field." → struck through and marked **RESOLVED** with the two citations | EXP-0020 (config word bit19/bit23) + EXP-M4-09/CMD-8 (occupancy-tier correction) + EXP-0024 (tgmem field) — all already cited in the resolved sections above |
| 10 | `docs/cmdstream/README.md:8–14` (status blockquote) | appended: "*(First-pass status — superseded below by the per-structure decodes: FF state + USC grammar (EXP-0019/0024, RT-2a/RT-11), indirect/occlusion/timestamps (EXP-0027), geometry output + tessellation (EXP-O2A/O2H), VDM draw record + blend state pool + occupancy tier (EXP-M4-09/CMD-*), attachment format word (EXP-M4-08 DESC-1).)*" — the header still claimed "full bit-level decode deferred to follow-up cmdstream experiments" while the body contains those decodes | the experiments named, all already cited in the same file |
| 11 | `docs/cmdstream/README-M5-deltas.md:120` | unbalanced backtick typo: "`0x10000250000` (M5)`;" → "`0x10000250000` (M5)**;" (formatting only, no fact) | — |

### Already correct (verified, no edit needed)
- **Sampler stride 0x20 (RT-2a):** `docs/cmdstream/README.md:413–416` ("sampler entries are 0x20 apart,
  not 8; the earlier `/8` overcounted 4×") and `docs/descriptors/README.md:39–43` (8-byte descriptor
  payload vs 0x20 argument-buffer slot — reconciles the two). No stale `/8` sampler-stride sentence
  remains in either file.
- **Indexed-VDM `instanceCount +0x78` (RT-2a):** `docs/cmdstream/README.md:104` ("instanceCount @+0x78
  (moved from +0x6c)"). The indirect-draw offsets at L328–329 (`+0x74`/`+0x78`) are consistent with the
  shifted indexed record, not a stale value.
- **Native tessellation (EXP-O2H):** `docs/cmdstream/README.md:441–454` states "native graphics/tiler-path
  stage — NOT compute-emulated … Emulation is OPTIONAL"; no contrary "emulate tessellation" sentence
  remains in the editable dirs (`docs/cmdstream/README-M5-deltas.md:97` matches for M5).
- **RT-9 / tiled-Morton cols:** `docs/tiling/README.md` §1.1/§1.4 carry the RT-9 correction; the stale
  `cols = ceil(W/T)` wording survives only at `docs/m4-deltas.md:86` (flagged above).
- **Attachment format byte +0x21 (EXP-M4-08 DESC-1):** corrected in `docs/cmdstream/README.md:155`,
  `docs/descriptors/README.md:138,148`, `docs/descriptors/README-M5-deltas.md:36–40`, and
  `docs/pipeline/README.md:71`.
- **Sample positions userspace-emittable (RT-4):** no sample-position sentence exists in
  `docs/cmdstream/` or `docs/descriptors/`; the fact lives in `docs/pipeline/README.md` (out of scope),
  which already states the RT-4 correction per `docs/ROADMAP.md:59`.

### Uncertain — reported, not edited
1. `docs/descriptors/README-M5-deltas.md:10` — "**SAME:** type byte0[0:2] (1D=0,2D=2,2DArray=3,…)". The
   `byte0[0:2]` width is the superseded 3-bit reading on the A18 (EXP-0028: 4 bits), but this is an **M5
   delta file** and no committed M5 experiment validates the type-field width; changing it would assert an
   M5 fact from A18 evidence (CODEX target-discipline rule). Suggested fix for the orchestrator: reword to
   "type byte0[0:3] (4-bit field per A18 EXP-0028 — *inherited*, not re-probed on M5)" or equivalent.
2. `docs/cmdstream/README.md:18` — "ring BO + doorbell write proven to exist, exact location pending —
   **see Open items**": the "Open items" section no longer lists the ring/doorbell location. The claim
   itself (location pending) is still true; only the cross-reference is stale. I did not want to expand
   the open-items list without knowing the intended owner (kernel-interface item). Suggested: point it at
   `../kernel-interface.md` instead.
3. `docs/descriptors/format-table.md:336` (§5 row) — "format channel arrangement | word0 bits[4:7] (byte0
   hi nibble)" vs §2c's "arrangement is effectively the 3-bit value `byte0[5:7]`, bit4 always 0". Both
   readings appear in the file; §2c is the decoded one. Left alone (renaming the field would be a
   fact-adjacent restructure); flagging for a possible "(bit4 always 0, §2c)" parenthetical.
4. `docs/descriptors/README.md:20` — "(Full 31-format table in EXP-0015 RESULTS.)" is superseded by the
   96-format table in `format-table.md` §2d (EXP-M4-08) and the 60-format EXP-0028 table; the row is
   otherwise correct. Left as-is since `format-table.md` §2d already declares itself authoritative
   ("This supersedes the 31-/60-format tables in §2 / 'Extended format codes'").

---

## Claims I could not trace to establishing evidence
None newly introduced by these edits. Two pre-existing doc statements remain un-verifiable **in this
checkout** (not evidence gaps in the repo, but worth the orchestrator's attention):
- All `../mesa/...` citations (12) — the pinned Mesa tree is not materialized (`mesa/` is an empty
  gitlink), so `mesa/src/gallium/drivers/asahi`, `mesa/include/drm-uapi/asahi_drm.h`,
  `mesa/src/asahi/libagx/libagx_dgc.h`, `mesa/src/asahi/lib/agx_device.c` and `mesa/src/poly/` cannot be
  confirmed to exist at those paths.
- `docs/isa/README.md:14`'s `experiments/EXP-0041-m4-scratch-helper-abi` — no experiment directory with
  that slug exists; the RT-1a-FIX evidence it points at is presumably `experiments/EXP-0041-scratch-helper-abi`.

## Files changed (git diff --stat)
```
 docs/cmdstream/README-M5-deltas.md |  2 +-
 docs/cmdstream/README.md           | 11 +++++++++--
 docs/descriptors/README.md         |  5 +++--
 docs/descriptors/format-table.md   | 18 ++++++++++--------
 docs/tiling/README.md              |  2 +-
 5 files changed, 24 insertions(+), 14 deletions(-)
```
