# RESULTS — EXP-0132: M4 PBE/attachment-descriptor field mapping

**Target:** local Apple M4/G16G, this host only. macOS 26.6.2 (25G82), Metal 4, public
Metal API + public IOKit user-client selectors only. M4-only; no A18 Pro evidence exists
or is claimed here. Pinned revision `cf544b4dd1fb37047c7cfee6a70a0d1a87628666`
(`CAPTURE_CONTRACT.json`).

**Officially gated evidence:** `raw/m4-20260828-run01/`, `raw/m4-20260828-run02/`,
16/16 `status=OK` in both runs. `verify.py --selftest` (18/18), `--seqtest` (5/5),
`--preflight` (13/13), `--between-runs` (9/9), and `--captured` (4/4) all PASS. The
`--captured` gate found the two runs byte-exact on every gated field for 15/16 cases and
tolerated exactly 1 content-capture read-timing flake (`m1-mip-level0`,
`mrt-attachment-descriptors`; well under the budget of 3) — size and presence agreed for
that role in both runs, only one run's content read failed despite the widened retry
budget. `analysis.py` falls back to the run that did capture it for that one case/role
(both runs are equally valid GPU observations of the same case; the flake is a harness
read failure, not a hardware difference) and reports the fallback explicitly
(`analysis.json` `flake_fallback_used_for`).

## Verdict

**Priority 1 (depth/stencil slot-reuse) — CONFIRMED, HW-VALIDATED, byte-exact two-run
gated, and generalized beyond EXP-0108's own tested scope.** Priority 2 (three-segment
field mapping) — **PARTIAL**: this experiment's own baseline case does not exercise
EXP-G1b's A18-only-observed 0x300-stride single-RT LOAD/RENDER/STORE chain at all (every
case here relocates to the compact MRT-style k-array, consistent with EXP-0048's own
prior M4 finding that M4 already does this even for 1–2 buffer-backed attachments); the
k-array itself (LOAD/STORE, no separate RENDER segment) is field-mapped in more depth
than before, including two genuinely new fields (array/mip non-encoding + the mipCount
flag, and the MSAA-resolve k-slot). Priority 3 (`attachment-slot-b`) — **NOT
REPRODUCED**: the role never appeared in any of this harness's 16 cases despite
exercising the axes EXP-0108 reported it correlating with; reported as a genuine negative
result, not resolved.

## 1. Tested matrix (exact)

16 cases / 8 axes, `harness/casematrix.py` (single source of truth). All render a 32x32
target.

| axis | cases | what varies |
|---|---|---|
| `depth-stencil-reverify` (7) | a1, d1, g1, g2, h1, i1, i2 | baseline; format-only control; depth (Private/memoryless); stencil; depth+stencil; depth+stencil at ncolor=2 (adversarial generalization) |
| `array` (3) | l1, l2, l3 | color-attachment-0 render slice 0 / 1 / (arrayLength−1), arrayLength=4, full per-slice readback |
| `array-boundary` (1) | l4 | slice = arrayLength (first invalid), full per-slice readback |
| `mip` (2) | m1, m2 | color-attachment-0 render level 0 / (mipCount−1), mipCount=3, full per-level readback |
| `mip-boundary` (1) | m3 | level = mipCount (first invalid), full per-level readback |
| `resolve` (2) | r1, r2 | 4x MSAA, MultisampleResolve / StoreAndMultisampleResolve |

## 2. OBSERVED vs INTERPRETED

### 2.1 H1 — depth/stencil reuse the k-indexed color-attachment array (CONFIRMED)

**OBSERVED**, address-subfield-masked, byte-exact across both officially gated runs
(`analysis.json` `h1_depth_stencil_slot_reuse`, verdict `SUPPORTED`):

| case | ncolor | new k slot(s) populated | k-record structural prefix (8 bytes, address masked) |
|---|---:|---|---|
| a1 (baseline) | 1 | none — only k=0 | `220a88f6017c0008` (k=0, RGBA8) |
| g1 (depth, Private) | 1 | k=1 | `628800f8017c0008` |
| g2 (depth, memoryless) | 1 | k=1 (still populated) | `628800f8017c0000` + zero surface (poison, no real address) |
| h1 (stencil, Private) | 1 | k=1 | `224068f9017c0008` (distinct from depth) |
| i1 (depth+stencil) | 1 | k=1 = depth (matches g1 exactly), k=2 = stencil (matches h1 exactly) | — |
| **i2 (depth+stencil, ncolor=2 — new adversarial test)** | **2** | **k=2 = depth (matches g1), k=3 = stencil (matches h1)** | k=0,k=1 both nonzero (the two color attachments) |

**INTERPRETED.** This is a direct, byte-exact-gated confirmation of EXP-0108's own
"doubly-corroborated but not two-run byte-exact-gated" finding
(`experiments/EXP-0108-m4-bg-eot-programs/RESULTS.md` section 2.3): depth and stencil
attachments are described using the *same* per-attachment k-indexed 0x20-byte-stride
descriptor-record array (`+0x20+k·0x20` LOAD / `+0x220+k·0x20` STORE, EXP-0048/
EXP-M4-08/09) already used for color attachments, not a separate mechanism. **The exact
k=1 depth prefix this experiment observed (`628800f8017c0008`) is byte-identical to the
prefix EXP-0108 reported for its own `g2-depth-write` k=1 LOAD record
(`628800f8017c0008` + masked address + `...`)** — an independent replication under a
different, freshly built, race-fixed harness. **New beyond EXP-0108:** the rule
generalizes to `ncolor=2` (`i2`): depth always lands at `k=ncolor`, stencil at
`k=ncolor+1`, not at a fixed k=1/k=2. **New beyond EXP-0108:** memoryless depth (`g2`)
still populates k=1 (EXP-0108's own region-count-delta method reported "no delta" for
memoryless depth, which is correct at the whole-BO-inventory level — memoryless doesn't
add a *new* BO — but does not mean the *slot inside the existing* `mrt-attachment-
descriptors` region is unpopulated; it is populated). Its structural prefix differs from
non-memoryless depth in exactly one unmasked byte: `628800f8017c0000` (memoryless) vs.
`628800f8017c0008` (Private) — byte 7 (record-relative, immediately before the masked
5-byte address subfield) flips `0x08→0x00`, plausibly a "has real backing" bit, though
this experiment does not decode its exact meaning. The address subfield itself
(record-relative `+0x08..+0x0c`) is masked identically in both cases by this
experiment's own gating policy, so this experiment's gated evidence can neither confirm
nor deny the specific `0x0eeee000`-class poison value `docs/pipeline/README.md` documents
for memoryless color targets — only that byte 7 differs and the record remains
distinctly non-zero (populated) either way. This is a strict refinement, not a
contradiction, of EXP-0108's finding.

**Evidence label: HW-VALIDATED** (two-run byte-exact, address-normalized, adversarial
`ncolor=2` generalization passed, independent replication of an external prior
observation).

### 2.2 H2 — array slice / mip level are NOT encoded in the per-attachment k-record;
mipCount>1 sets a coarse flag (CONFIRMED, negative result)

**OBSERVED**, byte-exact across both runs (`analysis.json` `h2_array_mip_field_mapping`,
verdict `SUPPORTED`): the k=0 LOAD record is **byte-identical** across `l1`/`l2`/`l3`
(slice 0, 1, 3 of an arrayLength=4 target) and **byte-identical** across `m1`/`m2`
(level 0, 2 of a mipCount=3 target). The *only* difference between a `mipCount=1`
baseline (`a1`, record word1 = `08007c01` after little-endian reassembly) and a
`mipCount=3` case (`m1`, word1 = `0c007c01`) is bit 26 of word1, newly set — **the exact
bit position format-table.md §5 already documents as the sampled-texture-descriptor's
"mipmapped" flag** (`word1 bit26 | set when mipmapLevelCount > 1`). This is set
regardless of which `level` is actually targeted for rendering.

**INTERPRETED.** Layer/array and mip **selection** (i.e. *which* slice/level a given
render pass targets) is not carried in this per-attachment 0x20-byte control-word record
at all — it must live elsewhere (the tiler/geometry command stream, a viewport-adjacent
field, or a mechanism this experiment's named-role set does not cover; `vdm-command-
state`/`fixed-function-render-state` were captured only at presence/size granularity in
this experiment's frozen schema, not content, so this cannot be narrowed further here —
see section 4). What the record **does** carry is a coarse **capability** flag
(mipCount>1 present), reusing the exact same bit convention as the ordinary sampled
texture descriptor — a genuine, new, positive structural finding: the render-target/PBE
descriptor and the sampled-texture descriptor share not just the format-code convention
(already documented) but also this specific flag bit.

**Evidence label: HW-VALIDATED** for "slice/level selection is absent from this record"
(negative, byte-exact, two independent slice values and two independent level values
tested); **HW-VALIDATED** for the mipCount>1 flag bit (byte-exact, cross-checked against
an independently-documented bit from a different descriptor family).

### 2.3 H3 — boundary behavior for invalid slice/level: silently accepted, two DIFFERENT
failure modes (CONFIRMED, negative/boundary result)

**OBSERVED**, byte-exact across both runs, `cb_status=4` (Completed), no `cb_error`,
`status=OK` in both boundary cases — **the API neither rejects nor aborts**:

| boundary case | requested value | valid range | observed readback |
|---|---|---|---|
| `l4-array-slice-invalid` | `slice = 4` | `[0, 4)` (arrayLength=4) | **slice 0 reads `00000000` (zeroed — was canary `a0a0a0a0` before the render); slices 1–3 keep their canary untouched** |
| `m3-mip-level-invalid` | `level = 3` | `[0, 3)` (mipCount=3) | **all three levels (0,1,2) keep their canary untouched — no visible effect anywhere** |

**INTERPRETED.** This hardware's default failure mode is documented elsewhere as "silent
zero" (`docs/isa/register-move-and-liveness.md`), and both boundary cases are consistent
with a *silent*, non-faulting failure — but they are **not the same failure mode**:

- An out-of-range **slice** does not simply vanish or alias into the requested (invalid)
  index — it **zeroes slice 0's existing content** (destructive: the pre-render canary at
  slice 0 is overwritten with `0`, even though slice 0 was never the render target).
  This is consistent with the low bits of the slice value being used directly in an
  address/offset computation that, for `slice=arrayLength`, lands on a location whose
  effect is observable as "slice 0 gets a zero write" rather than a modular wraparound to
  a *correct* clear/draw at slice 0 (a true `slice % arrayLength` wraparound would have
  produced the actual clear color, not zero). The exact addressing arithmetic that
  produces this specific outcome is **not** decoded here (no descriptor field was found
  to vary with the boundary case relative to the in-range cases — see section 2.2 — so
  there is no descriptor-level explanation available; the effect must originate in
  whatever mechanism outside this descriptor actually carries slice selection).
- An out-of-range **level** produces **no observable effect at all** in any valid level —
  a true no-op, distinct from the slice case's destructive zeroing.

**Driver consequence:** neither boundary is safe to construct deliberately (both are
API-undefined-but-non-faulting), and a driver must validate `slice < arrayLength` and
`level < mipCount` itself before emitting a render pass — the hardware/API does not do it
for you, and the two fields fail in genuinely different, non-obvious ways (one is
destructive to unrelated state, one is inert). This is exactly the kind of asymmetric
"silent-but-different" boundary behavior CODEX/CLAUDE.md ask to be pinned down rather than
assumed uniform.

**Evidence label: HW-VALIDATED** (two-run byte-exact, both runs `status=OK`/`cb_status=4`,
full per-slice/per-level readback in both boundary cases).

### 2.4 H4 — MSAA resolve target occupies the next free k slot in BOTH LOAD and STORE
arrays (CONFIRMED, new field mapping)

**OBSERVED**, byte-exact across both runs (`analysis.json` `h4_msaa_resolve_slot`,
verdict `SUPPORTED`), for both `r1` (`MultisampleResolve`) and `r2`
(`StoreAndMultisampleResolve`), identically:

- k=0 LOAD is populated with type nibble `4` (2DMultisample, matching `docs/pipeline/
  README.md`'s documented MSAA type-nibble convention) — this is the MSAA color
  attachment's own LOAD/RENDER record.
- **k=0 STORE (the MSAA color attachment's own STORE/PBE slot) is entirely zero** — the
  multisample surface itself is never described by a STORE/PBE record in this arena.
- **k=1 LOAD and k=1 STORE are BOTH populated**, with k=1's type nibble `2` (ordinary
  non-multisample 2D) — this is the **resolve target's own descriptor**, appearing in
  BOTH the LOAD-side and STORE-side arrays at the next free k index (`k=ncolor=1`).

**INTERPRETED.** This generalizes the "next free k slot" pattern this experiment already
confirmed for depth (2.1) to a **third** kind of attachment: whatever attachment-like
resource needs its own descriptor slot beyond the declared color attachments (depth,
stencil, or an MSAA resolve target) consumes the next sequential k index, in the fixed
order color → depth → stencil (2.1) / resolve (here tested with ncolor=1, no depth/
stencil present, so resolve lands at k=1 uncontested; the relative priority between
resolve and depth/stencil when *both* are present in the same pass is untested — see
section 4). The MSAA surface's own STORE slot staying zero is consistent with "an MSAA
surface is never itself the object being stored to main memory — only its resolve
target is" — i.e. the resolve target's k=1 STORE record *is* the store side of this pass,
not a second, independent record.

**Evidence label: HW-VALIDATED** (two-run byte-exact, two independent store-action
variants tested (`MultisampleResolve` / `StoreAndMultisampleResolve`), identical result).

### 2.5 H5 — `attachment-slot-b` does not reproduce in this harness (negative result,
reported honestly, not resolved)

**OBSERVED**, both runs, all 16 cases: the fixed VA `0x10000120000`
(`attachment-slot-b` in EXP-0108's own naming) never appears as a `present` named role
anywhere in this matrix (`analysis.json` `h5_attachment_slot_b`, `present_in_cases: []`),
despite this matrix exercising every axis EXP-0108 reported it correlating with (action-
adjacent load/store combinations via the depth-stencil-reverify axis's baseline/format
control, MRT via `i2`, MSAA via `r1`/`r2`, depth/stencil via `g1`/`h1`/`i1`/`i2`,
per-format via `d1`).

**INTERPRETED.** This experiment does **not** conclude EXP-0108's own finding was wrong
on its own harness — EXP-0108's own confounders section already documents that unnamed-
region identification by fixed VA is allocation-order-sensitive (a *different* candidate
region shifted between two of EXP-0108's own harness revisions that differed only in
unrelated JSON-parsing code executed before any Metal call). This experiment's harness
differs from EXP-0108's in exactly the ways PRE_REGISTRATION.md section 2 discloses
(different color-attachment allocation strategy — plain Shared textures, never a client
`MTLBuffer` — different case ordering, different config-parsing code before the Metal
calls), any of which is independently sufficient, per EXP-0108's own documented
confounder, to shift what (if anything) lands at a specific fixed VA in a fresh process.
**The safe conclusion is that `0x10000120000` is not a stable, harness-independent
hardware-facing address for whatever role it plays** (consistent with every other
"unnamed" region in this class of experiment) **— not that the role itself does not
exist.** Resolving it requires the VA-free size/hash region-count-delta method EXP-0108
itself used for its *positive* findings (depth/stencil), applied to this harness's own
full BO inventory, which this experiment's frozen schema does not capture in the needed
form (only presence/size for non-deep roles) — named explicitly as remaining P1.1 work
(section 4), not attempted here as an unplanned scope expansion.

**Evidence label: STRUCTURAL negative** (non-reproduction is byte-exact-gated; the
underlying role's existence/meaning remains `UNKNOWN`).

## 3. PBE / attachment field map — consolidated (existing docs + this experiment's new
fields)

Field names below are structural interpretations (byte/bit offsets and observed
behavior), never names read from Apple code. Rows marked **[NEW]** are established by
this experiment; all other rows restate already-`HW-VALIDATED` prior work
(`docs/descriptors/README.md`, `format-table.md`, `docs/pipeline/README.md`, cited inline)
for a single self-contained reference table, per DRV-PBE-01's own ask for a complete
field map.

| field | location | encoding / behavior | evidence |
|---|---|---|---|
| type + arrangement | k-record byte0 | texture-type low nibble (2=2D, 4=2DMultisample — confirmed here for the MSAA k=0 record and the resolve k=1 record) + arrangement hi-nibble; identical codes to the sampled descriptor | EXP-0015/EXP-0028 (`format-table.md` §1/§2c) + **[NEW, cross-checked]** this experiment's `r1`/`r2` type-nibble observation |
| format numtype+sizeclass | k-record byte1 | `numtype<<5\|sizeclass`, full 96-format table | `format-table.md` §2d |
| **width−1 / height−1** | k-record word0 top byte + word1 low bits | packed exactly as the PBE (storage-image) descriptor: width−1 low8=word0 byte3, height−1=word1 bits[6:19] | EXP-G1b §1b/§2c (A18); reproduced structurally (byte positions consistent) on M4 here |
| **base surface VA** | k-record `+0x08` qword, low 40 bits | `VA = (qword & 0xFFFFFFFFFF) << 4` | EXP-0048/EXP-M4-08; masked as the address-normalization field throughout this experiment |
| **opaque high-address-adjacent control byte(s)** | k-record `+0x0d..+0x1f` | config-dependent (format/sRGB/mip flag all land here); not fully decoded | EXP-0048 (sRGB delta); **[NEW]** mipCount flag (word1 bit26) isolated here |
| **layer/array selection** | **NOT in this record** | byte-identical across all tested `slice` values at fixed `arrayLength` | **[NEW, negative]** section 2.2 |
| **mip LEVEL selection** | **NOT in this record** | byte-identical across all tested `level` values at fixed `mipCount` | **[NEW, negative]** section 2.2 |
| **mipCount>1 capability flag** | k-record word1 bit26 | set iff the attachment's `mipmapLevelCount>1`, independent of which level is targeted | **[NEW]** section 2.2, cross-checked against `format-table.md` §5's identical bit for the sampled descriptor |
| sample count | k-record word1 bits[24:25] (also RT-attachment `+0x24` in the pipeline docs' framing) | 1x=`0x0000fc03`-class, 2x/4x bit24/25; 8x Metal-unreachable | `docs/pipeline/README.md` "MSAA — sample count & positions"; **[NEW, cross-checked]** this experiment's `r1`/`r2` byte3 `0x08→0x09` (bit24) observation for the MSAA k=0 record |
| **MSAA resolve target slot** | k=`ncolor` LOAD **and** STORE (both populated); MSAA color's own STORE slot at k<ncolor is zero | non-multisample (type nibble 2) descriptor at the resolve target's own next-free k index | **[NEW]** section 2.4 |
| **depth attachment slot** | k=`ncolor` LOAD+STORE | structural prefix `628800f8017c0008` (Private) / `628800f8017c0000` (memoryless, byte7 flips 0x08→0x00); address subfield masked either way so this experiment cannot confirm/deny the specific poison value | **[NEW under a clean two-run gate]**, corroborates EXP-0108 §2.3; section 2.1 |
| **stencil attachment slot** | k=`ncolor+1` LOAD+STORE (when depth also present); k=`ncolor` when stencil alone | structural prefix `224068f9017c0008`, distinct from depth | **[NEW under a clean two-run gate]**, corroborates EXP-0108 §2.3; section 2.1 |
| component mapping (PBE store) | format-derived byte (r=`0x00`, rg=`0x04`, rgba=`0xe4`/`0xc6`) | **not an independently steerable field** — no free knob to vary; format alone determines it | EXP-G1b §1b / `docs/descriptors/README.md` "Storage-image (PBE) descriptor"; not re-probed here (PRE_REGISTRATION.md section 9) |
| linear stride | `((word3>>12)+1)×16` = bytesPerRow (buffer-backed only) | unchanged from prior docs; this experiment used only Shared-storage (non-buffer-backed, non-linear) targets throughout, so this field was not independently re-exercised here | EXP-G1b §1b/§2c/§2d |
| access/control 8-byte word, coherency, rotation/mode, reserved values, program-ID ownership | **UNKNOWN** | not located by this experiment (out of the tested named-role set; see section 5) | still open — P1.1 remainder |
| 3-segment LOAD(+0x000)/RENDER(+0x300)/STORE(+0x600) 0x300-stride chain | **A18-only observed** (EXP-G1b); this experiment's M4 harness never used it — every case relocated to the compact k-array arena, consistent with EXP-0048's own prior M4 finding | EXP-G1b (A18); EXP-0048 (M4, already notes "not a universal MRT rule"); **[NEW confirmation]** this experiment shows the SAME M4 preference holds even for a plain 1-color, non-buffer-backed, non-MSAA case (`a1`) |

## 4. Finite-resource rows — boundary behavior summary

| field | valid range (tested) | first-invalid tested | observed negative behavior | evidence label |
|---|---|---|---|---|
| array slice | `[0, arrayLength)`, arrayLength=4 tested | `slice = arrayLength` (4) | **silently accepted** (no reject, no abort, `cb_status=4`); **destructively zeroes slice 0's prior content** while other in-range slices stay untouched — not a modular wraparound to a correct clear, not a pure no-op | HW-VALIDATED (2-run byte-exact) |
| mip level | `[0, mipCount)`, mipCount=3 tested | `level = mipCount` (3) | **silently accepted** (no reject, no abort, `cb_status=4`); **pure no-op** — no valid level shows any effect | HW-VALIDATED (2-run byte-exact) |
| color-attachment index | `[0, 8)` | `8` (9th, 0-based) | **fatal, uncatchable process abort** the instant the array index is touched — cited, not re-probed (redundant/risk-only re-test avoided per PRE_REGISTRATION.md section 9) | HW-VALIDATED — `EXP-0117` (cited) |
| MSAA sample count | `{1,2,4}` | `8` | Metal-rejected at texture-creation/pipeline-creation time (not GPU-fault); cited, not re-probed | HW-VALIDATED — `docs/pipeline/README.md`/EXP-0021 (A18; cited, INFERRED-by-family for M4 per `docs/m4-deltas.md` ISA-identity) |
| attachment width/height | up to 16384 | untested here | already established elsewhere | HW-VALIDATED — EXP-M4-08/EXP-G1b (cited, not re-probed) |

## 5. What P1.1 (DRV-PBE-01) still requires

Per the closure rules in `docs/P0-P1-CLOSURE.md` and this experiment's own honest
scoping (`PRE_REGISTRATION.md` section 9), still open after this experiment:

- **Where layer/mip selection actually lives**, if not in the per-attachment descriptor
  record (section 2.2/2.3): a follow-up needs full-content capture (not just presence/
  size, as this experiment's frozen schema used) of `vdm-command-state` and
  `fixed-function-render-state` across the same `l1..l4`/`m1..m3` matrix, diffed the same
  way this experiment diffed `mrt-attachment-descriptors`.
- **`attachment-slot-b`'s role**: non-reproduced here (section 2.5); needs EXP-0108's own
  VA-free region-count-delta method applied to this harness's full inventory (this
  experiment's frozen schema captured only presence/size for non-deep roles, precisely
  because widening the deep-capture set was judged out of this dispatch's time budget —
  named explicitly, not silently dropped).
- **Access/control 8-byte word, coherency bits, rotation/mode, reserved-value
  enumeration, program-ID ownership**: not located by this experiment; EXP-0108 already
  owns the program-ID/BG-EOT-program overlap with P0.4 and found no program at all in its
  own much wider matrix — a future attempt at these fields should not re-search for a
  program, only for descriptor-level control bits.
- **The 3-segment 0x300-stride LOAD/RENDER/STORE chain**: still only A18-observed
  (EXP-G1b); this experiment adds a second, independent M4 confirmation that M4 does not
  reach it even for the simplest single-attachment case, but does not itself map it on M4
  — a genuinely single-RT-forcing M4 harness variant (if one exists) would be needed.
- **Depth+stencil+resolve interaction** (does resolve take k=ncolor and push depth/
  stencil to k=ncolor+1/+2, or does depth/stencil take priority?) — untested combination.
- **Compressed/ASTC/BC attachments, cube/cube-array, sparse residency, layered rendering
  via `[[render_target_array_index]]`** (this experiment only exercised the host-side
  `.slice`/`.level` selection path, not the shader-side array-index output): untested.
- **Any A18 Pro evidence** (M4-only per current target discipline).

## 6. Gate results

| Gate | Result |
|---|---|
| `verify.py --selftest` | **18/18 PASS** — includes 3 full-pipeline byte-level mutators proving the masking scheme both (a) is sensitive to a real semantic-field change, (b) is insensitive to the known allocator-address field, and (c) is insensitive to the two empirically-found-flaky `clear-color-arena` bytes while still sensitive to an adjacent byte — built from `harness/fixtures/` (real recorded-reality inventory + descriptor excerpts from this experiment's own pre-capture diagnostic phase) |
| `verify.py --seqtest` | **5/5 PASS** — `PRE_GPU`/`RUN01_PRESENT`/`RUN02_PRESENT` tree-state detection, tested against a temp directory, never the real `raw/` |
| `verify.py --preflight` | **13/13 PASS** (run before run01) |
| Non-recorded smoke gate | `run.py`'s `smoke_gate()` — one scratch case (`CM.CASES[0]`) into `work/`, never `raw/`, required `status=OK` before either official run was authorized to start; ran automatically as part of both `--execute` invocations |
| `verify.py --between-runs` | **9/9 PASS** (run after run01 closed, before run02 started) |
| `raw/m4-20260828-run01` | 16/16 `status=OK` |
| `raw/m4-20260828-run02` | 16/16 `status=OK` |
| `verify.py --captured` | **4/4 PASS** — byte-exact on every gated field for 15/16 cases; 1 tolerated `content_captured` flake (budget ≤3), size/presence agreed |
| `analysis.py --write` | H1–H5 all `SUPPORTED`; 0 unresolved cross-run disagreements |
| `make_manifest.py --check` | PASS, 29 files |

No timeout, GPU error, device loss, host wedge, or recovery event occurred in either
official run. Wall time for each official run was under 2 seconds (16 fresh-process
cases against 32x32 targets).

## 7. Disclosed process notes (not hardware facts, kept per CODEX "do not quietly drop
what was tried")

- Three harness bugs (unsafe SIGUSR1 fallback; `NSNull` treated as truthy; `replaceRegion`/
  `getBytes` called on a live multisample texture) were found and fixed during an informal
  pre-capture diagnostic phase, before any `raw/` artifact existed — see `PROGRESS.md`.
- A methodological finding (a client `MTLBuffer` render target aliased the fixed VA this
  experiment's own interposer treats as `mrt-attachment-descriptors`, silently substituting
  rendered-pixel bytes for descriptor content) was caught and fixed at the root (no
  client-buffer render targets anywhere in the frozen harness) — see `PROGRESS.md` M4 and
  `PRE_REGISTRATION.md` section 2 finding 4. This is the same class of VA-coincidence risk
  `EXP-0048`'s own `raw/preflight_failures.md` already documented for a different
  configuration; it is disclosed here as a second independent instance of the same
  class of hazard, worth keeping in mind for any future harness built on a client-buffer
  render-target pattern.
- A harness-reliability issue (a bounded `mach_vm_read_overwrite` retry budget inherited
  from EXP-0108 was occasionally insufficient even for the simplest case, specifically in
  a rapid back-to-back subprocess loop) was mitigated by widening the retry budget; the
  officially gated capture still needed its one explicitly tolerated flake-budget
  allowance once (section 6), consistent with this being a real, only-partially-
  understood reliability margin, not a fully eliminated phenomenon.
- **Self-disclosed operational incident:** three `verify.py` gate re-runs during this
  experiment's own review were briefly redirected to `/tmp/x1`/`x2`/`x3` (shell output
  redirection, not raw/analysis evidence) instead of staying inside this experiment's
  own `work/` — a violation of the absolute "never leave this directory" rule. The files
  contained only this experiment's own gate PASS/FAIL console output (already reproduced
  verbatim in section 6 above), no raw capture bytes, no Apple or external data, and were
  deleted immediately upon being noticed, confirmed removed. See `PROGRESS.md` for the
  full disclosure. All gate output used in this document was independently re-verified
  afterward with output kept inline (no file redirection).

## Clean-room provenance

```text
Clean-room provenance: HW-PROBE / DATA-TRACE / OWN-SHADER
Inputs inspected: complete authored MSL generated per case from harness/probe.m; authored
  render-pass config JSON; IOKit call/resource-map metadata for every BO the process
  registers; capped content for a pre-registered, bounded set of small structured
  control/descriptor regions (PRE_REGISTRATION.md section 7); structural (offset/byte-
  pattern) hex analysis of descriptor-class content only
Apple binary introspection: NONE
Apple auxiliary/helper program bytes committed: NONE (hash-only outside the bounded
  named-role set; the 4GiB-aligned code window is excluded from content capture entirely,
  by construction in harness/wtrace.c, unchanged from EXP-0108)
Pointer following: NONE (region identification is either a fixed named VA or per-case
  JSON metadata from our own probe; the one address-reconstruction formula in use,
  EXP-0048/EXP-M4-08's low40<<4, is applied only to already-established descriptor
  k-records, never to select or follow into another region's content)
Reproduction: see README.md
Evidence: raw/m4-20260828-run01/, raw/m4-20260828-run02/, analysis.json,
  analysis/report.txt, manifest.json
```
