# PRE_REGISTRATION — EXP-0106 m4-texture-isa-semantics

Pinned revision (frozen at pre-registration; do NOT gate on live `HEAD`):
`75eb840a011ffbfa3fe2eb1721e2acbbcc24c1e7` (working tree dirty with unrelated concurrent
experiment directories at freeze time — normal per `SUBAGENT_BRIEF.md`'s HEAD-move note; this
experiment gates on the **authored blob hashes** recorded in `CAPTURE_CONTRACT.json`, not on
`HEAD` or tree cleanliness).

Target: **local Apple M4 (G16G) only**, macOS 26.6.2 (25G82), Mac16,10, arm64, Metal 4. A18
Pro/G17P is hands-off (no data collected here). Public-Metal-API-level probing plus, for the
mip-count/dimension items, plain `MTLTextureDescriptor` validation — the same boundary
(`public Metal only; owned in-bounds resources; no binary/archive/BO inspection`) EXP-0095 used.
No raw ISA descriptor/instruction splicing is attempted in this experiment (see per-item
deferrals below for the items that need it).

## 0. Scope statement (read first)

Part II's `TEX-*` cluster in `APPLE9_RE_IMPLEMENTATION_GAPS.md` has **28 items** — the largest
cluster in the document. Per the dispatch brief and `CODEX.md` §10 ("freeze a coherent subset...
state explicitly which items were NOT exercised"), this experiment:

1. Enumerates **all 28 items** below with an explicit **coverage/deferral decision** — none
   silently dropped.
2. For items EXP-0016/EXP-0034/EXP-0094/EXP-0095 already substantially answer, states precisely
   **what remains** and either closes the remainder here or defers it with a named reason.
3. Freezes **one coherent subset of ~9 new-evidence families (b01..b09, ~14 individual TEX
   sub-answers)** for actual new M4 hardware/compiler evidence in this experiment — chosen for
   (a) highest gap-doc-flagged value, (b) tractability at the public-Metal behavioral level
   without raw descriptor/instruction splicing (kept out of scope here for risk/time reasons;
   every deferred splice-needing item gets an exact, actionable successor spec citing the known
   bit offsets from `docs/descriptors/format-table.md`).
4. Everything else is closed by **citation** (already HW-validated by a named prior experiment or
   by a direct, checked public-source fact — MSL spec search performed in this pre-registration,
   not assumed from memory) or explicitly **deferred** with a concrete reason and successor plan.

**Public source used:** `gpu_knowledge/apple_official/msl_spec/metal-shading-language-spec.pdf`
(Apple's public Metal Shading Language Specification, 2025-10-23 edition, already present in the
repo's read-only `gpu_knowledge/` reference tree) — converted locally to text with `pdftotext`
(a standard PDF-text-extraction utility, not a disassembler, applied to a public PDF, not an
Apple binary) purely to `grep` for API surface facts (which member functions/parameters Metal
exposes) that bound which `TEX-*` questions are even reachable through the public API. This is
`PUBLIC` per `CLAUDE.md`'s allowed-technique #4. No hardware or algorithmic fact is taken from
it; it only tells us what Metal's compiler can be asked to emit.

## 1. Per-item decisions (all 28)

Legend: **CITE** = closed here by citing prior HW evidence + response block, no new M4 work;
**NEW** = frozen for new M4 work in this experiment (family tag in brackets); **DEFER** = out of
scope for this contract, reason + successor stated.

| # | One-line question | Decision | Notes |
|---|---|---|---|
| TEX-01 | native projective-divide (`txp`) form | **DEFER** | Metal exposes no `sample`-with-w-divide entry point (MSL spec §6.12 has no such overload) — the compiler NEVER emits an unlowered projective form, so there is no compiler-emitted evidence to observe. Answering it needs raw `op+2` bit-space fuzzing on a spliced, otherwise-valid `tex_sample` bundle (EXP-0016/34's decoded companion+sampler-op bytes) beyond every value the compiler is known to reach — a dedicated opcode-fuzzing campaign, out of this contract's time budget. Successor: splice `op+2` through its full unused range on a HW-validated baseline (EXP-0016 `f_sample`), oracle = does the texture unit apply a w-divide to the coordinate before lookup. |
| TEX-02 | native 4-independent-offset gather | **CITE (structural)** | MSL spec §6.12.6 `gather()`/`gather_compare()` take exactly one `int2 offset` parameter (checked directly against the spec text, not memory) — Metal's compiler can never be asked to emit a 4-offset gather. EXP-0034 HW-validated the single-offset encoding. Answer: **No** compiler-reachable one-op 4-offset form exists; `lower_tg4_offsets` remains necessary. Raw hardware capability beyond the compiler-reachable single-offset form is a separate, lower-priority ISA question (same class of gap as TEX-01) — deferred, not exercised here. |
| TEX-03 | full [-8,+7]^2 offset-pair encoding, no aliasing | **NEW [b09]** | EXP-0034 HW-validated 4 points ((1,0),(0,1),(1,1),(3,-2)). This experiment adds a **boundary-and-corner sweep** (not the full 256 pairs — declared explicitly as NOT exhaustive) via `gather()` against a per-texel-distinct 8x8 grid, executed on real M4 hardware. |
| TEX-04 | dynamic (non-constant, per-lane) GPR offset | **NEW [b09]** | Folded into the same family: one case passes a **runtime, buffer-loaded, per-thread-varying** `int2` as the `offset` argument (not a literal) and asks whether Metal's compiler accepts and correctly executes it. A compile rejection is itself the answer (closes the compiler-facing half decisively either way); if it compiles, behavior is HW-checked against distinct per-lane offsets. The deeper "does the raw ISA support a non-preadjusted dynamic offset independent of MSL's front door" question is deferred alongside TEX-01/02 if MSL rejects it. |
| TEX-05 | dynamic `min_lod_clamp()` operand, all forms | **NEW [b04]** | EXP-0094 (GLTEX-A01) tested the **sampler-object** `lodMinClamp`/`lodMaxClamp` (a static per-sampler-descriptor property) composing with `bias()`. It did **not** test MSL's separate **per-call** `min_lod_clamp(float)` argument (MSL spec §6.12, listed alongside `level`/`bias`/`gradient*` as an `lod_options` value) — a materially different mechanism (an instruction operand, not a descriptor field). This experiment tests `min_lod_clamp()` as a **dynamic, runtime-computed** value across ordinary(implicit)/level/bias/gradient/`sample_compare` forms. The spec explicitly restricts `lod_options` overloads (hence `min_lod_clamp`) to `sample`/`sample_compare` only — **not** `gather`/`gather_compare` — so the gather sub-question is closed structurally (checked against the spec text) without a hardware test. |
| TEX-06 | `txs`/mip-count/sample-count query at dynamic bindless index | **NEW [b05]** | Not addressed by any prior experiment (EXP-0016 established queries are free preloaded-uniform reads for *directly bound* textures only; EXP-0095 tested bindless *sample/read/write*, not bindless *queries*). Tests `get_width()`/`get_num_mip_levels()` through a bindless argument-buffer array at a **per-lane, thread-ID-derived (non-uniform)** index. |
| TEX-07 | native `samples_identical`-equivalent | **CITE (structural)** | MSL spec has no such member function (grep of the full spec text: zero matches for any "identical"-named texture primitive). Answer: **No** — NIR's conservative-false lowering is the only option; there is no MSL entry point through which Apple's compiler could ever emit a native form, so no HW test is possible from the compiler side. Confirming a *hidden* HW primitive with no MSL front door would need the same class of opcode fuzzing as TEX-01 — deferred with that group. |
| TEX-08 | distinct pre-dispatch prefetch op | **CITE (structural)** | MSL spec has no "prefetch" texture function (grep: zero matches). Answer: **No** compiler-reachable distinct prefetch primitive; NIR `tex_prefetch` selects as an ordinary sample. Same opcode-fuzzing caveat as TEX-07 for a hidden HW-only primitive — deferred. |
| TEX-09 | no native `R32G32B32_*` sampled/texel-buffer format | **CITE** | Already closed by EXP-0095 (GLTEX-A07): no `MTLPixelFormatRGB32*` constant exists in the public `MTLPixelFormat` enum (a structural, directly-checked API fact, not an absence-of-evidence inference) — confirmed **12-byte texels have no representable Metal format at all**, consistent with `docs/descriptors/format-table.md`'s closed §2 format-code table (max texel size 16 bytes, no 12-byte entries). No new work needed; formalized as a response block here. |
| TEX-10 | one-op YCbCr conversion vs. multi-plane | **CITE (structural)** | MSL spec has no Y'CbCr/planar sampler-conversion type (grep for "ycbcr"/"planar": zero matches) — Metal exposes no multi-plane-conversion sampler object at all, structurally answering "No general conversion API" without needing the raw-descriptor probe the item's own wording anticipates. Packed native 4:2:2 (`gbgr422`/`bgrg422`, sizeclass `0x10`) **is** HW-validated as an ordinary sampled format (`docs/descriptors/format-table.md` §2b, EXP-M4-08) — distinguishing exactly the two cases the item asks to distinguish. |
| TEX-11 | no arbitrary sampler border color beyond 3 presets | **CITE** | Closed by EXP-0015/EXP-M4-08 (`docs/descriptors/format-table.md` §4c): exactly 3 presets HW-validated, 2-bit field exhausts to 4 possible codes, code `3` unreached via any Metal API path (no 4th `MTLSamplerBorderColor` case exists publicly) — same "Metal-unreachable" status as the address-mode gap codes. The item's second half (two-sample clamp-to-zero/clamp-to-one emulation of an arbitrary border, incl. shadow-compare) is answered **analytically** here from already-HW-validated building blocks (compare-func table EXP-0034/M4-08, clamp modes EXP-0015) — a small confirmatory rendering case is included as bonus if the frozen budget allows, else explicitly left as a nice-to-have, not the core finding. |
| TEX-12 | sparse-texel residency + color correctness | **DEFER** | Needs `MTLHeap`-backed sparse textures and `updateTextureMapping:` residency control — a materially different, larger harness than anything else in this contract (region mapping lifecycle, not a single dispatch). EXP-O2B decoded the sparse-tier descriptor bit and established residency lives in the kernel-managed page table, but never exercised `sparse_sample`/`sparse_read`/`sparse_gather`'s reported color+residency code. Successor: a dedicated sparse-residency experiment. |
| TEX-13 | OOB coordinate/layer/mip/sample-index robustness matrix | **CITE + NEW [b06] remainder** | Substantially covered: EXP-0016 (2D read OOB), EXP-0095 GLTEX-A04 (array-layer fetch-vs-sample/gather divergence), EXP-0095 GLIMG-A01 (2D/cube OOB read+write, no corruption). Explicit **remainder** not yet tested by any prior experiment: mip-level-argument OOB on `read(coord, level:)`, MSAA sample-index OOB on `read(coord, sample:)`, and 3D depth-axis OOB fetch. These three are added as new cases in `[b06]`. |
| TEX-14 | all 128 direct textures simultaneously/independently selectable | **CITE + NEW [b07]** | EXP-0095 GLIMG-A02 tested indices {0,63,127} of a 128-argument kernel with distinguishable canaries — the gap doc explicitly says this is **not sufficient** and names 7/8, 15/16, 31/32, 63/64 as required boundary pairs. This experiment adds exactly those 8 indices (plus reconfirming 0) in one new 65-argument kernel with distinguishable canaries, closing the boundary-pair requirement without repeating the already-closed 127/129 ends. |
| TEX-15 | complete selector encoding for 0..127 | **DEFER** | Explicitly flagged in the gap doc as **not closed** by the existing `op+4` single-bit (index-0-vs-1) splice (EXP-0016/34). Closing it needs differential compilation across many distinct texture-argument counts to grow the field past one proven bit, correlate companion/op byte changes with selector value, and distinguish resource selection from coordinate/destination register fields — a dedicated ISA decode campaign (own-shader-diff across N in {2,3,4,8,9,16,17,32,33,64,65,127}, no HW dispatch required but substantial `tools/shdump`-based analysis). Out of this contract's time budget; the boundary-selectability BEHAVIORAL question (TEX-14) is closed above without needing the byte-level decode. Successor: an EXP dedicated to `op+4`'s full field-width decode, reusing `tools/agx-isa`/`tools/shdump` (read-only) exactly as EXP-0016/34 did. |
| TEX-16 | 129th direct texture: deterministic rejection | **CITE + note** | EXP-0095 already established a 129-argument kernel is an MSL **compile-time** error (structural, deterministic). The item's second half ("raw table/selector injection") is coupled to TEX-15's still-open field-width question — can't meaningfully inject a "129th" selector without first knowing the field is wide enough to address it — deferred together with TEX-15. |
| TEX-17 | all 16 direct samplers simultaneously/independently selectable | **NEW [b08]** | Current evidence (EXP-0063/EXP-0066) is explicitly **insufficient** per the gap doc's own wording ("current evidence shows those encodings share instruction bytes"; EXP-0063 additionally found its own filter-distinction probe **falsified** because every tested UV was non-discriminating). This experiment builds a genuinely distinguishing 16-sampler test (address-mode divergence at an out-of-range coordinate, which EXP-0063 showed DOES discriminate) in one kernel, all 16 populated simultaneously. |
| TEX-18 | 17th direct sampler: deterministic rejection | **NEW [b08]** | Folded into the same family: a second, minimal kernel source with a 17-sampler-argument function, tested for MSL compile-time rejection (structural, like TEX-16, but never previously tested at n=17 specifically for samplers — EXP-0016/34 only ever populated 1-2). |
| TEX-19 | bindless texture selection to the full 1,000,000 limit | **DEFER** | EXP-0095 GLIMG-A02 already closed the **shape** of the answer (silent zero, no aliasing, no period-256 mirroring, unlike the buffer base-slot family) at `CAP=256`/`K=8`, with feasibility-only exploration to N=4096. Exhaustively confirming the documented 1,000,000 ceiling is a large allocation-and-sweep campaign, not a small addition to this contract. Successor: reuse EXP-0095's exact GLIMG-A02 methodology at boundary values near 1,000,000. |
| TEX-20 | behavior >=1,000,000 / unpopulated / nonresident | **DEFER** | Same family as TEX-19 — EXP-0095 established the pattern at small scale; confirming it holds at the documented ceiling needs the same large-scale successor. |
| TEX-21 | bindless sampler selection to 499,999 | **DEFER** | EXP-O2B (**A18 Pro**, historical, pre-dates the M4-only directive) established `maxArgumentBufferSamplerCount = 500000` as a queryable device capability and demonstrated dynamic shader-computed sampler-heap indexing works for a handful of entries — it explicitly did **not** sweep the range or the boundary. Also a target-discipline note: that evidence is A18, not M4-validated under the current directive. Successor: an M4 re-run of EXP-O2B §4's methodology at boundary values near 499,999. |
| TEX-22 | 500,001st sampler / destroyed-ID reuse | **DEFER** | EXP-O2B's own "Recommended next" section names exactly this gap ("check whether identical sampler descriptors dedup to one ID"); never executed. Same successor as TEX-21. |
| TEX-23 | dimension ceilings (16384 / 2048 / 2048) independently enforced | **NEW [b01]** | Not previously HW-tested as a creation-boundary sweep (the values are cited as public/architectural limits in `docs/mesa-userspace-requirements.md`/`docs/descriptors/format-table.md`'s 14-bit width/height field, but the *first-illegal* boundary was never exercised). |
| TEX-24 | 4-bit mip-count field to 15 levels; negative/excessive/Inf/NaN explicit LOD | **NEW [b02]** | The mip-COUNT ceiling (15 levels via a 16384-wide chain) was never tested. EXP-0094 GLTEX-A01/A02 fully characterized `bias()`/`gradient2d()` NaN/Inf behavior but not **explicit** `level()`'s response to negative/excessive/Inf/NaN values, which is a materially different operand path (no clamp-then-lookup rho/lambda computation — level() supplies the mip index almost directly). |
| TEX-25 | MSAA sample-count set exactly {1,2,4}, 8x+ rejected | **NEW [b03]** | Not previously tested as a creation-boundary sweep (EXP-0095 used a FIXED `sampleCount=4` MS image case; never tried 1/2/8). |
| TEX-26 | anisotropy limited to 16x; raw codes for 32/64/128x | **CITE (Metal-clamp half) + defer (raw-field half)** | `docs/descriptors/format-table.md` §4 / EXP-M4-08 already HW-validated (M4+A18 cross-confirmed) that **requesting** `maxAnisotropy=32` through the public API does **not** clamp to the 16x field value — it clamps all the way to **field 0 (1x)**, a materially different and already-established fact. The **raw 3-bit field literally holding 5/6/7 (32x/64x/128x)** — unreachable through any Metal API call — needs write-capable descriptor injection, which EXP-M4-08 explicitly attempted (`splice.m`) and found blocked for the explicit-argument-buffer path (gpuResourceID indirection, not inline bytes). Deferred with an exact successor spec (§3 below): attempt the injection via the **direct** `[[sampler(n)]]` per-stage table instead (the mechanism EXP-0016 proved is inline-pointer-based and HW-spliceable for texture slots), not the explicit-AB path that already failed. |
| TEX-27 | sampler max LOD limited to 14.0; raw field to 15.875 | **CITE (Metal-clamp half, + NEW behavioral cross-check in [b02]) + defer (raw-field half)** | Same structure as TEX-26: EXP-M4-08 already HW-validated (descriptor-byte level, M4+A18) that requesting `lodMaxClamp > 14.0` saturates the field at exactly `112` (14.0), not the field's true 7-bit range (up to 15.875). This experiment adds a **behavioral** (rendered-LOD, not descriptor-byte) cross-check via the `[b02]` mip-count/LOD family, requesting `lod_clamp(0, 15.875)` and `lod_clamp(0, 14.5)` samplers and observing the actual ceiling through an explicit high `level()` request. The raw-field-injection half defers exactly like TEX-26 (same successor). |
| TEX-28 | exhaust all unnamed sampler address/border/swizzle/filter codes | **DEFER** | This is the general form of TEX-26/27's raw-field-injection gap plus the still-untested address codes 4/6/7 and border code 3 (`docs/descriptors/format-table.md` §4a/§4c, `EXP-M4-08` DESC-4: explicitly flagged "beyond this read-only pass... needs a write-capable interposer or a device-global-table patch"). Also newly noted here (public-source check, this pre-registration): **MSL 4.0 adds a per-sampler `bias(float)` state field** (spec §2.7, "The level-of-detail (LOD) bias to apply before sampling") — a static descriptor-level bias distinct from the per-instruction `bias()` operand EXP-0094 fully characterized, and not decoded in any existing descriptor doc. Flagged as a genuinely new probe target for the same successor. All of TEX-28 needs write-capable descriptor patching; out of this contract's time budget. Successor spec: §3 below. |

## 2. Falsifiable hypotheses for the frozen [b01..b09] families

For every family: independent variable = the swept parameter named; controlled variables = texture
format (r32uint/r8uint canaries unless noted), texture/sampler build path (public
`MTLTextureDescriptor`/`MTLSamplerDescriptor`, `newLibraryWithSource:`), M4 target, fresh process
per case; confounders considered = allocator/compiler placement (controlled by reading back through
the fixed 96-byte guarded OUT buffer convention, same guard-byte technique as EXP-0095, so any
neighbor corruption is directly visible), Metal-level clamping vs. hardware-level clamping (kept
separate by citing EXP-M4-08 for the descriptor-byte view and only adding NEW behavioral
cross-checks here), silent-zero-vs-fault (recorded, not assumed, per
`docs/isa/register-move-and-liveness.md`'s general warning that a wrong operand is more often a
silent zero than a fault).

- **[b01] TEX-23.** H: the 14-bit width/height field's decoded max (16384) and the corresponding
  3D-axis/array-layer ceilings (2048) are the exact creation boundary; H0 (refuter): a boundary
  value one past a limit is silently accepted (texture_ok=true) rather than rejected, OR a value
  well inside the limit is unexpectedly rejected. Expected observation: last-legal accepted,
  first-illegal rejected (mechanism TBD by direct test — NSException, hard abort, or nil return are
  all legitimate outcomes; pre-freeze exploration determines which so the frozen contract encodes
  the correct `expect_status`, per EXP-0095's identical practice for its texel-buffer ceiling).
- **[b02] TEX-24/27.** H: `get_num_mip_levels()` on a maximal 16384-wide chain returns exactly 15;
  explicit `level()` at negative/huge/Inf/NaN clamps rather than faults, and (unlike `bias()`'s
  established mip-0 NaN behavior) may differ since `level()` bypasses the rho/lambda formula
  entirely; H0: any of these produces a GPU fault, hang, or a level index outside [0, count-1].
  Sampler `lod_clamp(0, 15.875)`/`(0, 14.5)` ceiling behaviorally matches EXP-M4-08's byte-level
  14.0 saturation; H0 (refuter): the rendered LOD exceeds 14.0 for the 15.875 request.
- **[b03] TEX-25.** H: `device.supportsTextureSampleCount:` and actual `MTLTextureDescriptor`
  creation agree, are true for {1,2,4} and false for 8; H0: any disagreement between the query and
  actual creation behavior, or 8 succeeding.
- **[b04] TEX-05.** H: `min_lod_clamp()` is a genuine dynamic (runtime, not baked-constant) operand
  for sample/level/bias/gradient/sample_compare, composing with the sampler's own
  lodMinClamp/lodMaxClamp exactly as EXP-0094 established for the sampler-level field; H0: the
  value is silently ignored (result identical with/without a varying `min_lod_clamp` value) or
  faults. `gather`/`gather_compare` + `min_lod_clamp` is expected to be a **compile-time rejection**
  since the spec's `lod_options` overload list excludes gather forms; H0 (refuter): it compiles
  successfully.
- **[b05] TEX-06.** H: a per-lane, thread-ID-derived, non-uniform bindless texture index's
  `get_width()`/`get_num_mip_levels()` returns the value for THAT lane's selected texture, not a
  broadcast single value; H0: all lanes report the same (uniform-selection) value regardless of
  their distinct index.
- **[b06] TEX-13 remainder.** H: mip-level OOB read, MSAA sample-index OOB read, and 3D depth-axis
  OOB read all follow the established project-wide silent-zero pattern (matching the public MSL
  spec's own OOB-read rule already confirmed for coordinate/layer OOB); H0: any of the three
  produces nonzero garbage, a fault, or aliases a neighboring texel/level/sample.
- **[b07] TEX-14.** H: all of 7,8,15,16,31,32,63,64 (plus 0) read their own distinct canary with
  zero cross-talk in one 65-argument kernel; H0: any two indices alias (same value observed for two
  distinct canaries) or any index reads a wrong/zero value despite being populated.
- **[b08] TEX-17/18.** H: 16 simultaneously-bound samplers with alternating ClampToEdge/ClampToZero
  address modes each independently produce their own address-mode's result at an out-of-range
  coordinate (zero vs. edge-color), proving all 16 selector slots are live and distinguishable; a
  17-sampler-argument kernel fails to compile (MSL compile-time ceiling). H0: any slot reads the
  wrong mode's result (aliasing to a neighbor), or the 17-sampler kernel compiles successfully.
- **[b09] TEX-03/04.** H: the boundary/corner offset pairs in [-8,7]^2 each shift the gathered 2x2
  footprint by exactly that (dx,dy) against a per-texel-distinct 8x8 grid, with no two distinct
  pairs producing the same footprint (no aliasing) and -8 distinguishable from a hypothetical wrap
  to +8 (which the field cannot represent, so no wrap is expected); a dynamic (non-constant,
  per-lane) `offset` argument either fails to compile (MSL requires it inline) or, if it compiles,
  correctly reflects each lane's own offset. H0: any aliasing between distinct offset pairs, or a
  dynamic offset silently reading a WRONG lane's/constant value while still reporting `status: ok`.

## 3. Successor spec for the deferred raw-descriptor-injection items (TEX-26/27/28)

Exact bit locations are already known and committed (`docs/descriptors/format-table.md` §4):
`lodMaxClamp` bits[13:19] (7-bit, `round(lodMax*8)`, want to inject raw value 127 = 15.875),
`maxAnisotropy` bits[20:22] (3-bit log2, want to inject raw values 5/6/7 = 32/64/128x), address-mode
codes bits[29:31]/[32:34]/[35:37] (want raw codes 4/6/7), border color bits[61:62] (want raw code
3), plus the newly-noted MSL-4.0 static sampler `bias` field (location not yet decoded — first sub-
task for the successor). EXP-M4-08's DESC-4 attempt used an **explicit `MTLArgumentEncoder`-created
argument buffer**, whose sampler slot turned out to be an opaque `gpuResourceID` (device-global table
index), not inline bytes — genuinely unreachable by a read-only trace pass. The **direct**
`[[sampler(n)]]` binding path (used by EXP-0015/EXP-0016/EXP-0034/EXP-0094/EXP-0095 throughout this
project) is a **different** mechanism: EXP-0016 proved (HW-validated splice) that the analogous
direct **texture** slot is an inline 8-byte pointer in a per-stage Tier-2 table reachable and
patchable from our own process (`tools/iotrace` BO capture + in-process write before submit). The
successor should locate the **sampler** side of that same per-stage table (not yet attempted for
sampler CONTENT, only for the texture side) and attempt the same technique before falling back to a
fresh write-capable interposer.

## 4. Standing gates implemented

`--selftest` (state-agnostic PRE_GPU/captured schema + synthetic gate self-test), `--seqtest`
(subprocess-driven PRE_GPU/RUN01_PRESENT/RUN02_PRESENT fixture state machine), a **non-recorded**
pre-capture smoke gate (one case, `run.py`'s `smoke_gate`, executed and validated before `raw/` is
ever created, never itself written into a byte-compared record), byte-exact cross-run comparison
with **no nondeterministic field** in any compared record (fixed key sets, `os`/`device`/`machine`
identity strings only — no timestamps, no pointer/address values, no PIDs in any compared payload),
and RECORDED-REALITY fixtures (the `--seqtest` fixture builder derives its case list live from
`CAPTURE_CONTRACT.json`, never hand-copied). Architecture follows the proven EXP-0079/EXP-0083/
EXP-0095 pattern (independently re-authored for this experiment, not copied file-for-file).

Two capture run IDs, chosen fresh and never reused: `m4-20260830-run01`, `m4-20260830-run02`.
