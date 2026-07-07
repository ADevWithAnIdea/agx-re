# RT8 — Synthesis-doc consistency & cross-doc contradiction sweep

**Reviewer:** RT-8 red-team consistency reviewer (host-only, read-only).
**Date:** 2026-07-07.
**Scope:** (1) `docs/kernel-interface.md` firmware-managed boundary; (2) `docs/capability-matrix.md`
+ `docs/capability-completeness.md` classifications & tallies; (3) cross-doc contradiction sweep of
all of `docs/` (+ `PROVENANCE.md`). Ground-truth for the recent corrections is the measured doc that
owns the experiment (`pipeline/README.md` for RT-4/EXP-0021, `tiling/README.md` for RT-3/EXP-0017,
`cmdstream/README.md` for EXP-O2H) plus the red-team RT-N results recorded in `ROADMAP.md`. **No file
edited; nothing committed.**

## TL;DR verdicts
- **Area 1 — kernel-interface.md: NOT CLEAN (1 HIGH).** The RT-4 "sample positions are userspace-
  emittable" correction landed in §4.2 **only**; §6 (the whole G-11 reconciliation), §6.1, §6.2 and §7
  still route sample positions to the kernel — the doc now contradicts itself on a userspace↔kernel
  boundary. All *other* firmware-managed claims (BVH build, ZLS/depth-store, partial-render, doorbell,
  scratch/UVB, isp_scissor, code-BO handoff) are consistent with the measured docs.
- **Area 2 — capability-matrix / capability-completeness: NOT CLEAN (3 HIGH + several MED).** Neither
  the sample-positions=native nor the tessellation=native correction propagated to the classification
  rows or the bucket counts; the mesh "honesty note" and the 64-bit-atomic note are stale; and
  capability-completeness carries **three mutually-inconsistent grand totals**.
- **Area 3 — cross-doc sweep: NOT CLEAN.** Three corrected facts (sample-positions/RT-4,
  tessellation/O2-H, tiling-model/RT-3) are split-brained across the corpus; the ROADMAP status line
  lags by ~74 native rows; and `PROVENANCE.md` has **no RT-2a/RT-3/RT-4 rows** while its superseded rows
  still assert the pre-correction facts. The three *previously*-flagged items (memory-index byte+5,
  USC/shader-entry note, descriptor width 14-bit) **are fixed**.

---

## AREA 1 — `docs/kernel-interface.md`

### HIGH 1.1 — Sample positions: §4.2 says userspace, §6/§6.1/§6.2/§7 still say kernel (self-contradiction, wrong boundary)
The RT-4 correction is present in exactly one place and contradicted in four others **within the same
doc**:

| Location | Says |
|---|---|
| §4.2 (line 174–176) | "**CORRECTED (RT-4): sample positions ARE userspace-emittable** … written to a client BO (`0x100000e8000` 4× / `0x100000e0000` 2×) at +0x40 … **NOT kernel-managed.**" |
| §6 title (line 225) | "Reconciling the contradiction (G-11): **ZLS & sample positions — firmware or userspace?**" → resolution (241–244) decides **both** are kernel-populated submit params |
| §6.1 table (line 260) | `ppp_multisamplectl` \| `PPP_MULTISAMPLECTL` — **sample positions** \| firmware-owned |
| §6.2 boundary table (line 284) | "**Sample positions** \| emitted in cmd stream? **no** \| submit param? **yes** (`ppp_multisamplectl`) \| firmware **writes register**" |
| §7 item 4 (line 308–311) | groups "the ZLS / **sample-position** / tilebuffer contract" as kernel-marshalled |

Also structural: §4.2 is filed under the §4 header "**Explicitly firmware/kernel-managed (userspace
does NOT emit these…)**" while its body says the opposite; and §3.3 (line 149) routes "the control
registers listed in §6" to firmware, which still includes `ppp_multisamplectl`.

**Which is right:** userspace-emittable / **native**, per `pipeline/README.md` (RT-4, the owner of
EXP-0021), lines 29–32 ("EXP-0021 wrongly said 'byte-identical' because it diffed the wrong BOs …
written to a client BO … **NOT kernel-managed**") and line 64. **Fix:** strike sample positions from
§6/§6.1/§6.2/§7 (leave §6 as a ZLS-only reconciliation), move §4.2 out of the firmware-managed section.
Note `PROVENANCE.md` is itself stale here (see 3.5), so the authority is the measured doc + RT-4.

### The other firmware-managed claims — CONSISTENT (verified)
Each cross-checks against its measured source with no later contradiction:
- **BVH build + node format** — `isa/README.md` 391–394, capability-completeness §8 (244): kernel-managed. ✓
- **ZLS / depth store-action** — `pipeline/README.md` 44, 51 (still an open kernel-side item, **not**
  corrected by RT-4). ✓
- **Partial-render / tiler-param overflow trigger** — `pipeline/README.md` 48. ✓
- **Doorbell / ring advance** — `cmdstream/README.md` 61–66. ✓
- **Scratch / UVB / uniform-heap** — kernel-interface §"Scratch/doorbell" 349–354; UVB `cmdstream` 186–187. ✓
- **isp_scissor (multi-scissor)** — `cmdstream/README.md` 201–203. ✓
- **Code-BO-base → firmware shader-entry handoff** — `cmdstream/README.md` 126–139 (EXP-0024). ✓

Boundary is otherwise internally consistent and consistent with `pipeline.md`/`cmdstream.md`.

---

## AREA 2 — `docs/capability-matrix.md` + `docs/capability-completeness.md`

### HIGH 2.1 — capability-matrix: sample positions still 🔥 Kernel/FW
- §3 row (line 74): "**Programmable MSAA sample positions** \| 🔥 Kernel/FW … Not in any userspace BO
  (msaa4-vs-custom captures **byte-identical**)". That parenthetical **is exactly the error RT-4
  identified**, and the row **cites** `pipeline/README.md` MSAA § — which now states the opposite.
- §5 count (line 105) + summary (103–106): "🔥 Kernel/FW **5**" includes sample positions.
- **Correct:** Native/userspace-emittable. Kernel/FW bucket should be **4**; sample positions moves to
  the native set. (Per `pipeline/README.md` RT-4; `capability-completeness.md` line 515 already
  acknowledges the move but the matrix never did.)

### HIGH 2.2 — capability-matrix: tessellation still ⛔ Emulate (contradicts its own §4)
- §2 row (line 57): "**Tessellation** \| ⛔ Emulate … assume compute-emulated."
- §5 Emulate count (line 104) lists tessellation; honesty note (110) repeats "GS / tessellation / XFB … emulate".
- §4 row (line 92): "**CORRECTED (EXP-O2H): A18 has NATIVE hardware tessellation** … NOT compute-emulated."
- **Correct:** Native, per `cmdstream/README.md` §"Tessellation — NATIVE hardware stage" (243–256) and
  `PROVENANCE.md` line 104 ("Corrects capability-matrix"). Emulate bucket should be **6**.

### MED 2.3 — capability-matrix: mesh "honesty note" says mesh is NOT native
- §5 honesty note (line 113): "**Mesh shading is explicitly unknown (MSL-exposed, HW decode TODO), not
  native.**" Contradicts §4 row (line 91, "✅ Native (EXP-0030)") and §5 summary (106, "Mesh … now ✅
  native") in the **same file**, and `PROVENANCE.md` line 44. Stale note left over from before EXP-0030.

### MED 2.4 — capability-matrix: 64-bit atomic parenthetical is stale
- §2 row (line 53): "64-bit atomic-add \| … (64-bit **min/max exist**; 64-bit add does not)".
- **Correct:** *all* 64-bit atomics are absent from MSL — `capability-completeness.md` §4 (163),
  `hypotheses.md` #9 (25), and `PROVENANCE.md` line 98 (EXP-O2D, "64-bit atomics ENTIRELY absent …
  corrects EXP-0018"). The matrix is the last doc still claiming 64-bit min/max exists.

### HIGH 2.5 — capability-completeness: sample-pos & tessellation rows/tallies not updated; three inconsistent totals
Same two corrections stalled at the row level even though the §17 footer claims them:
- Sample positions still **kernel-managed** at §12 row (340), §16b list (474), §17 count table (507),
  and the §12 per-section tally (513, "13/0/**3**/0") — while §17 "Totals:" note (515) says it "moved
  kernel-managed → native-decoded". Same for tessellation: **emulated** at §9 row (268), §17
  emulated-explanation (506), §9 tally (512, "5/**3**/0/1"), while §16c (481) and §17 (508/515) call it
  Metal-exposed/native.
- **Internally-inconsistent grand totals** (task explicitly asks to flag tally inconsistency):
  - §17 summary table (505–508): **native 184 / emulated 11 / kernel 6 / NYC 13**
  - §17 "Totals:" line (515): **native 189 / emulated 11 / kernel 5 / NYC 9**
  - EXP-O2G footer (557): **native 187 / emulated 11 / kernel 6 / NOT-YET 10**

  The printed per-section tallies (lines 511–514) actually **sum to 184 / 11 / 6 / 13** — so line 515's
  "189/11/5/9" is arithmetically inconsistent with the tallies it claims to total. (OBJ2-AUDIT Finding 2
  flagged the 184-vs-187 split on 2026-07-07; the RT-4/O2-H edits since then added a *third* total rather
  than reconciling.) §17 line 508 also contradicts line 515 on tessellation: "1 remaining Metal-exposed
  residue is **tessellation** (exercise pending)" vs "tessellation … **CLOSED (EXP-O2H): NATIVE HW**".

### MED 2.6 — capability-completeness: pre-RT-3 tiling summary
- §14 row (line 380): "Morton / Z-order twiddle … tiling: pow2-padded Morton, **byte = morton(x,y)·bpp**".
  This is the exact model RT-3 corrected. **Correct:** row-major grid of Morton tiles, tile edge
  T = 64 (bpp≤4) / 32 (bpp≥8) — `tiling/README.md` §1.1 (17–32).

---

## AREA 3 — Cross-doc contradiction sweep

### Previously-flagged items — CONFIRMED FIXED
- **Memory-op index register = byte+5** (RT-1a): consistent everywhere (`isa/README.md` 11, 256, 262;
  `encoding-tables.md` 546/568/1219; agx3.xml). No stale byte+1/byte+6 index claim remains (the byte+6
  hits are unrelated shift/deriv/compare fields). ✓
- **USC / graphics shader-entry ⏳ note**: resolved and annotated as superseded (`cmdstream/README.md`
  86, 219). ✓
- **Descriptor width/height = 14-bit** (RT-3): consistent in `descriptors/README.md` 22–23 and
  `format-table.md` 195–196. ✓

### HIGH 3.1 — Sample-position classification is split-brained across the corpus
Ground truth (RT-4): **userspace-emittable / native**. Docs that agree: `pipeline/README.md` (29–32, 51,
64), `kernel-interface.md` §4.2, `ROADMAP.md` RT-tracker (230), `capability-completeness.md` §17 footer
(515). Docs still saying **kernel/firmware-managed** (all stale):
- `hypotheses.md` #15 (line 31) — records the outcome as "**NO (userspace) — firmware/register-managed;
  Mesa must route via kernel**". This is the primary register of probe results and is now **wrong**;
  should read WORKS/userspace.
- `capability-matrix.md` §3/§5 (2.1 above)
- `capability-completeness.md` §12/§16b/§17 (2.5 above)
- `kernel-interface.md` §6 (1.1 above)
- `mesa-userspace-requirements.md` line 133 ("decided **firmware/register-managed** … not in any BO")
- `porting-guide.md` lines 203, 319, 355, 362, 402 (route-to-kernel in 5 places)
- `isa/README.md` line 393 (passing "…kernel-interface item, like ZLS / **sample positions**")
- `PROVENANCE.md` line 88 (EXP-0021, "NEGATIVE (firmware-managed…): programmable sample positions … NOT
  in userspace BOs")

### HIGH 3.2 — Tessellation classification is split-brained
Native (correct, EXP-O2H): `cmdstream/README.md` 243–256, `PROVENANCE.md` 104, `capability-matrix.md`
§4 (92), `ROADMAP.md` 180. Still emulate/absent (stale): `capability-matrix.md` §2/§5 (2.2),
`capability-completeness.md` §9 (2.5), `mesa-userspace-requirements.md` 157/246 ("Confirm A18 still
lacks a fixed-function tessellator"), `porting-guide.md` 388–389/446.

### HIGH 3.3 — Tiling model (RT-3) is split-brained
Correct (RT-3): **row-major grid of Morton tiles, T depends on bpp** — `tiling/README.md` §1.1.
Still asserting the pre-RT-3 "pure full-texture Morton / one block / bpp-independent / morton(x,y)·bpp":
- `porting-guide.md` 269–270 ("Twiddle = **pure Morton over the whole padded texture — NO per-page
  sub-tile** … byte_offset = morton(x,y)·bpp. This **supersedes**…" — asserts the wrong model as the
  authority)
- `mesa-userspace-requirements.md` 120–121 ("`byte_offset = morton(x,y)·bpp`"; "**whole (padded) texture
  is one Morton block**")
- `capability-completeness.md` §14 (380) (2.6 above)
- `PROVENANCE.md` line 73 ("**whole texture is one Morton block, identical for all bpp**")

### MED 3.4 — ROADMAP status-line lag
`ROADMAP.md` line 121: "STATUS (capability-completeness.md, 214 rows): **native 110 · emulated 9 · kernel
6 · NOT-YET 89**" contradicts line 180 in the same file ("**184 native / 11 emulated / 6 kernel / 13
NOT-YET**") and the census itself. Line 121 lags by ~74 native rows / ~76 NYC rows.

### MED 3.5 — PROVENANCE paper-trail gap (RT-2a/RT-3/RT-4 never logged)
`PROVENANCE.md` has an RT-1a-FIX row (line 105) but **no RT-2a, RT-3, or RT-4 rows**. Consequently its
newest word on tiling (line 73) and sample positions (line 88) is the *pre-correction, now-wrong* model,
directly contradicting `tiling/README.md` and `pipeline/README.md`. Per `CLAUDE.md` ("Every fact that
enters docs/ gets a row here"), the RT-3 grid-of-tiles / 14-bit-dim facts and the RT-4 sample-position
fact are in `docs/` with no provenance row — a clean-room-defense completeness gap, not just cosmetics.

### LOW 3.6 — cmdstream sampler-stride wording self-inconsistent (RT-2a)
`cmdstream/README.md` line 211–213: "then **8-byte sampler descriptors** …" but "num_samplers =
(terminator − samp_ptr)/**0x20** … (RT-2a correction: samplers are **0x20-stride, not 8**)". The "8-byte
sampler descriptors" phrase wasn't updated to the 0x20 stride; the count formula is right but the prose
reads as a contradiction. (The 8-byte sampler *descriptor* in `descriptors/README.md` §Sampler and the
8-byte bindless `gpuResourceID` in EXP-O2B are genuinely different things — not a contradiction.)

---

## Severity-ordered fix list
1. **[HIGH]** kernel-interface §6/§6.1/§6.2/§7 + §4 header: remove sample positions from the kernel side
   (keep §6 = ZLS-only). (1.1)
2. **[HIGH]** capability-matrix: move sample positions Kernel/FW→Native (bucket 5→4) and tessellation
   Emulate→Native (bucket 7→6); update §5 counts + honesty note. (2.1, 2.2)
3. **[HIGH]** capability-completeness: propagate sample-pos→native (§12/§16b/§17) and tess→native (§9),
   then reconcile the three grand totals to one. (2.5)
4. **[HIGH]** Propagate RT-4 to hypotheses #15, mesa-req 133, porting-guide, isa/README 393; RT-3 tiling
   to porting-guide 269, mesa-req 120–121, completeness 380; O2-H tess to mesa-req/porting-guide. (3.1–3.3)
5. **[MED]** capability-matrix §2 line 53 (64-bit min/max); capability-matrix §5 line 113 (mesh); ROADMAP
   line 121; capability-completeness §14 line 380. (2.3, 2.4, 3.4, 2.6)
6. **[MED]** Add PROVENANCE rows for RT-2a/RT-3/RT-4 (or mark rows 73/88 superseded). (3.5)
7. **[LOW]** cmdstream line 213 sampler-stride wording. (3.6)

**Root cause:** the RT-4 (sample positions), O2-H (tessellation), and RT-3 (tiling model) corrections
were applied to the *owning measured doc* and to a single footer/note in each synthesis doc, but never
fanned out to the classification rows, bucket counts, hypotheses register, porting-guide, mesa-req, or
PROVENANCE. "Finding nothing" would have meant these fanned out cleanly; they did not.
