# OBJ2-AUDIT — Capability-completeness audit (objective 2)

**Auditor:** objective-2 auditor (host-only, read-only, adversarial).
**Date:** 2026-07-07.
**Bar under test:** *"We've exercised all hardware functionality that Metal exposes."* — i.e. every
Metal/MSL-exposed capability has been **provoked & tested on real A18 Pro hardware** (or is honestly,
correctly excluded), verified by cross-checking the census against the **PROVENANCE HW-exercise log and
the on-disk experiments** — NOT by trusting the census's own Status column.

**Sources read:** `docs/capability-completeness.md` (558 lines, full), `PROVENANCE.md` (full),
`docs/capability-matrix.md`, `docs/isa/msl-feature-map.md` (family scope), `docs/isa/README.md`,
`docs/cmdstream/README.md`, `docs/mesa-userspace-requirements.md` (§2g/§4), and the raw device captures in
`experiments/EXP-O2A…O2G`, `EXP-G1a/b`, plus the classic experiment set. No Apple binary introspected.

---

## VERDICT: **PASS** — with one documented caveat and one doc-integrity defect

- **Metal-exposed capabilities that the census FALSELY claims were exercised: 0.** Every
  `native-decoded` / `emulated` row I spot-checked (18 across all subsystems) traces to a real
  on-device experiment whose `raw/` captures contain the observed HW behavior the census cites. This is
  the central integrity bar for objective 2 and it holds.
- **Metal-exposed capabilities genuinely NOT exercised on A18: 1 (borderline).** Tessellation
  (`drawPatches` + tessellation-factor buffer + post-tessellation vertex function) **is** a Metal-exposed
  path, and it was **never run on A18**. The census carries it **honestly** (marked *emulated / unknown /
  NYC re-probe*, never falsely native, flagged "scoping-critical" in 4+ docs) — so it is not the failure
  mode objective 2 guards against (a claimed-but-unexercised capability). But its stated exclusion
  justification is imprecise (see Finding 1). A strict auditor who counts it makes the residue **1, not 0**.
- The NYC/kernel/microarch exclusion set is otherwise **honest and correct**: 6 microarch-only (no
  emittable encoding), 6 kernel-managed (firmware/register state), 4 Metal-edge/extrapolate probes.

I return **PASS** because the census does not misrepresent a single unexercised capability as exercised,
every characterized row is HW-backed, and the one genuine gap (tessellation) is disclosed rather than
hidden — which is exactly what the honesty rule demands. The caveat and the tally defect below should be
fixed but do not overturn the objective.

---

## Finding 1 (caveat) — Tessellation is the one Metal-exposed capability not HW-exercised; its exclusion label is imprecise

The census puts "GS / tessellation / transform-feedback — A18-native re-probe" (§9, and §16c) under the
header **"(c) Extrapolate-and-test probes (Vulkan/GL wants, Metal does NOT expose)."** That header is
correct for **geometry shaders** and **transform feedback** (Metal genuinely exposes neither → honest
emulate). It is **factually wrong for tessellation**: Metal *does* expose tessellation on Apple9 —
`MTLRenderPipelineDescriptor` tessellation state, `drawPatches:`/`drawIndexedPatches:`, a tessellation-
factor buffer, and an MSL post-tessellation vertex function (`[[patch(...)]]`). So tessellation is a
Metal-exposed capability whose A18 hardware representation was **not provoked**.

Mitigating facts (why this is a caveat, not a hard FAIL):
- The census **never claims tessellation is decoded**. It is marked `emulated` (on the M1/M2 default) and
  cross-listed NYC/"unknown", with the explicit note *"not independently probed on A18 … scoping-critical"*
  in `capability-matrix.md` §4, `mesa-userspace-requirements.md` §4/§246-247, `porting-guide.md` §446, and
  census §16c. This is disclosed, not masked.
- The project's own Metal-surface index (`msl-feature-map.md`, families A1–A21 / B1–B8) deliberately scopes
  tessellation/GS/XFB **out** of the characterized families and into the "classically-Apple-absent, re-probe
  later" bucket — a consistent (if debatable) scoping choice, not an oversight.
- The audit brief itself lists "GS/tess/XFB A18-native" among acceptable Metal-unreachable exclusions.

**Recommended fix (small):** either (a) run one experiment — build a tessellation pipeline, `drawPatches`,
capture the tiler/VDM stream, and confirm whether A18 drives a fixed-function tessellator or a compute
pre-pass (this also resolves the "tessellation VDM sub-word ordering — guessed" gap noted in
`mesa-userspace-requirements.md` §294); or (b) at minimum correct the §16c header so tessellation is not
filed under "Metal does NOT expose." Until then, the honest residue count is **1**, not the census's **0**.

## Finding 2 (doc-integrity defect) — The census body was never reconciled with its own closing experiment (EXP-O2G)

The top-line claim **native 187 / emulated 11 / kernel 6 / NYC 10 · "no Metal-exposed capability remains
un-exercised"** lives **only** in the appended EXP-O2G footnote (line 556). The body still reflects the
pre-O2G state and **contradicts** it:
- §2 (line 122) still lists **`printf` = NOT-YET-CHARACTERIZED**; §13 (367) **draw-mesh-into-ICB = NYC**;
  §14 (393) **compression × mipmap = NYC**.
- §16a (453) still says printf *"has never been provoked; no experiment has touched it"* — directly
  falsified by EXP-O2G, which provoked it end-to-end.
- §17 summary (507) still says *"3 Metal-exposed objective-2 residue"*; the tally line (514) still reads
  **native-decoded 184 · emulated 11 · kernel 6 · NYC 13**.

The **substance is fine** — EXP-O2G genuinely exercised all three (verified below), and the docs sections
(`isa/README`, `cmdstream/README`, `tiling/README`) carry the facts. But a reader who trusts the row-level
Status column or the §17 tally (exactly what this audit was told *not* to do) would miscount by 3 and
believe 3 Metal-exposed items are still open. The 184/11/6/13 body and the 187/11/6/10 footnote must be
reconciled (propagate the 3 rows to native-decoded, refresh §16a/§17). This is a documentation defect, not
a capability gap.

## Finding 3 (minor) — EXP-O2E / EXP-O2F have no experiment directory

The census header cites "O2-E" and "O2-F". There are no `EXP-O2E*` / `EXP-O2F*` directories; the work is
folded into **EXP-O2C** (labelled "O2-C/O2-F", RT tail) and **EXP-O2D** ("O2-D/O2-E", compute/frag tail),
which the PROVENANCE rows confirm and whose `raw/` data I verified. Harmless labeling quirk; note it so a
third party doesn't hunt for missing dirs.

---

## Spot-check table (census row → docs section → PROVENANCE / raw evidence → verdict)

18 capabilities traced across ISA, atomics, subgroup, matrix, texture, RT, mesh, cmdstream, TBDR,
descriptors, tiling, dispatch, fragment, blend. Verdict = does the census status hold against the raw
device capture?

| # | Capability (subsystem) | Census status | Experiment | Raw HW evidence checked | Verdict |
|---|---|---|---|---|---|
| 1 | Float ALU op-select (ISA §1) | native | EXP-0005/0006 | `raw/opmap.txt` 256-val sweep; splice 1c→1d turns a+b into a·b | ✅ holds |
| 2 | **bfloat ALU group `0x11`** (ISA §1) | native | EXP-O2D | `raw/validation.txt`: splice add↔mul → 0x4040(3.0)↔0x4000(2.0) bf | ✅ holds |
| 3 | **64-bit atomics** (§4) | **emulated** | EXP-O2D | `raw/probe64.txt`: all `atomic<*64>` ops MSL-rejected; 32-bit OK | ✅ holds (correct absence) |
| 4 | Float atomic add (§4) | native | EXP-0018 | op-field splice → 0x26; 1024 threads → 1024 | ✅ holds |
| 5 | Subgroup prefix-scan (§6) | native | EXP-0018 | per-lane distinct-value HW readback; `0xbf` byte+7 0x09/0x0b | ✅ holds |
| 6 | **simdgroup_matrix `0xcf`** full decode (§7) | native | EXP-0022/O2C | opcode diff vs FMA/shuffle (zero 0xcf); A·B+C validated; operand splice | ✅ holds |
| 7 | **int8 cooperative matrix** (§7) | **emulated** | EXP-0022 | integer matrix types rejected by MSL | ✅ holds (correct absence) |
| 8 | `sample_compare` / 2×2 PCF (§5) | native | EXP-0034 | HW shadow test, 8 compare funcs; op+2 bit5 | ✅ holds |
| 9 | **Arbitrary sampler border color** (§5) | **emulated** | EXP-0015 | descriptor exposes only 2-bit 3-preset field | ✅ holds (correct absence) |
| 10 | RT intersect + **motion blur** (§8) | native (partial) | EXP-0023/O2C | `raw/mbval.txt` hit_t 3.0→5.0 across t; `rtrender.txt` 8×8 grid | ✅ holds |
| 11 | HW mesh shading + **mesh-in-ICB** (§9/§13) | native | EXP-0030/O2G | rendered green triangle; `0x70000600` in ICB tiler stream @0x181c4 | ✅ holds |
| 12 | Multi-viewport / point_size / prim-restart (§10) | native | EXP-O2A | 44 param diffs; PPP output-select bits18/19, cut-index @0x18000+0x68 | ✅ holds |
| 13 | **Tile shader inline dispatch + imageblock write** (§12) | native | EXP-O2D | `raw/validation.txt`: pixel readback == tile colour Y; iotrace identical | ✅ holds |
| 14 | Morton/Z-order twiddle (§14) | native | EXP-0017 | GF(2) bit-perm solve of texel→byte; pattern-in / read-out | ✅ holds |
| 15 | **Bindless sampler heap** `gpuResourceID` (§15) | native | EXP-O2B/G1a | `raw/heaparg_k*.txt`; 8B index into 500k table stride 8 | ✅ holds |
| 16 | Programmable + dual-source blend (§10) | native (mechanism) | EXP-0019 | blend-factor change rewrites ~40 FS shader words; 0x58000 static | ✅ holds |
| 17 | **Shader printf / os_log** (§2) | NYC *(body)* / native *(footnote)* | EXP-O2G | `raw/pf_*`: end-to-end os_log decode; record framing captured mid-flight | ✅ exercised — but **census Status stale** (Finding 2) |
| 18 | **Tessellation A18-native** (§9) | emulated + NYC re-probe | *(none)* | no experiment; not run on A18 | ⚠ **Metal-exposed, un-exercised** (Finding 1) |

Rows 3, 7, 9 confirm the "emulated" verdicts are **HW-validated absences** (MSL/descriptor rejects the
path), not hand-waves. Rows 2, 6, 10, 11, 13, 17 confirm the objective-2 sweep experiments (O2C/O2D/O2A/
O2G) actually ran on the device and observed the claimed behavior. Row 18 is the single caveat.

---

## Honesty check on the excluded set (NYC / kernel / microarch)

- **Microarch-only (6)** — Dynamic-Caching dynamic curve, flexible unified on-chip memory, 2× ALU
  dual-issue, full occupancy/latency curve, RT reorder stage, lossless-compression block codec. Each has
  **no single emittable descriptor/instruction** (observable only via counters/throughput). Correctly
  excluded — the static models that *do* have encodings (96 GPRs, spill, occupancy tier bit23, RT
  intersect ops) are separately native-decoded. ✅
- **Kernel-managed (6)** — RT BVH build/node format, programmable sample positions, ZLS/depth store,
  partial-render trigger, scissor (`isp_scissor`), graphics shader-entry bind. PROVENANCE shows these were
  probed and found **absent from every userspace BO** (EXP-0021 NEGATIVE, EXP-0024, EXP-O2A) → genuinely
  firmware-routed, not a dodge. ✅
- **Metal-edge / extrapolate (4)** — aniso >16× (Metal caps 16×), wide/smooth lines (Metal line width
  fixed), conditional rendering (no Metal API), and the GS/tess/XFB re-probe. Three are correctly
  Metal-unreachable; the fourth is the tessellation caveat (Finding 1). ✅ / ⚠

---

## Bottom line for the caller

- **PASS.** Every characterized (native/emulated) census row is backed by a real on-device experiment with
  raw HW output; **0 rows falsely claim exercise they didn't perform**. The excluded set is honestly
  microarch/kernel/Metal-unreachable.
- **Metal-exposed-but-not-exercised count: 1 (borderline) — tessellation.** It is Metal-exposed
  (`drawPatches` path) and was not run on A18, but it is *disclosed* as unknown/emulate/NYC and flagged
  scoping-critical, not misrepresented as exercised. The census's "0 residue" is true only if you accept
  the project's scoping of tessellation as a classically-absent stage; a strict reading makes it 1. Fix:
  one `drawPatches` capture, or correct the §16c "Metal does NOT expose" wording.
- **No census `native/emulated` claim lacks PROVENANCE HW-evidence.**
- **Two defects to fix (non-blocking):** (2) the census body/§17 tally still say 184/11/6/13 and mark
  printf/mesh-ICB/comp×mip as NYC — never reconciled with the EXP-O2G footnote's 187/11/6/10, and §16a even
  asserts printf was never provoked; (3) EXP-O2E/O2F have no dirs (folded into O2C/O2D).
