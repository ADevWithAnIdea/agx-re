# EXP-0177 Results — P0.8 / DRV-ABI-01 evidence assembly

**Pure analysis. No device, no SSH, no GPU.** Three device experiments were live and none of
their files was touched; `tools/agx-isa/db.json` and `validation.json` are owned by EXP-0175
and were read only. Nothing is established here — every claim below is a citation.

**Target rule applied throughout:** closure is measured against **full G17P** (`CLAUDE.md`,
user directive 2026-08-28). An M4/G16G result is **supporting** evidence for this row, never
closure evidence, and is labelled that way in every entry.

---

## Verdict

**P0.8 is not "queued", and it is not close to closed.** Both halves of that sentence matter.

Twenty-two non-quarantined experiments bear on the row, four of them large and gated, and
between them they answer most of what the row asks *semantically*. But of the **28
instructions a VS/FS/CS stage ABI and its prolog/epilog linkage must emit**,
`tools/agx-isa/validation.json` marks **12 emittable (42.9%)** — and seven of those twelve
carry an `_instruction` label weaker than emitter-grade, which EXP-0173 §7.2 showed the
emittability rule never reads. **Five of 28 clear both bars: `frame_prologue`,
`link_save_restore`, `pixel_order`, `pop_reconverge`, `spill_frame_marker`.**

Not one of those five is an input, an output, a system value, an interpolation or a
tilebuffer instruction. They are all frame/ordering plumbing, and two are compromised in
their own right: `spill_frame_marker`'s exact role is UNRESOLVED (and EXP-0041 found its byte
pattern `60 00 00 00` occurred **zero times** in every captured main, including
proven-spilling CS/VS/FS programs), and EXP-0173 found three of `link_save_restore`'s six
fields have **zero free bits** — they are part of the match, not fields.

The one-line summary of this row: **the semantics are largely known, almost entirely on the
wrong target, and mostly not emittable.**

Two more findings are structural rather than technical and are the likeliest reason the cell
said "queued":

- **The two experiments whose names are closest to this row produce no usable evidence.**
  `EXP-0050-fragment-output-abi` is QUARANTINED (its runner materialized bytes outside its own
  allowlist while attesting it read only the selected fragment `_agc.main` — "ALL VERDICTS AND
  CLAIMS BELOW ARE NON-EVIDENCE"). `EXP-0071-m4-vertex-fragment-abi-contract` is QUARANTINED
  pre-GPU with an underspecified frozen matrix and no capture ever run. Anyone searching the
  tree for "the P0.8 experiment" finds two dead ends first.
- **The two largest P0.8 experiments are outside the paper trail.** `EXP-0109` (57 cases × 2
  gated runs) and `EXP-0117` (148 cases × 2 gated runs) own **no `PROVENANCE.md` row**; their
  only appearances there are inside *other* experiments' rows. So do `EXP-0111` (56 cases × 2)
  and `EXP-0108` (40 cases × 6 gated runs). Closure rule 3 fails on the bulk of the evidence,
  and EXP-0173 recorded the symptom from the other end: "P0.8 cites no experiment at all".

Per-sub-area coverage, honestly counted:

| # | Sub-area | Semantics | Emittable on G17P | Verdict |
|---|---|---|---|---|
| 1 | Inputs (VS fetch / stage_in / entry) | good, M4 | no G17P gated capture at all | SUBSTANTIAL on M4, STRUCTURAL on G17P |
| 2 | Outputs (FS colour/MRT/dual-src/depth/stencil/mask, VS pre-raster) | very good, M4 | field maps on G17P; 4 of 5 instructions blocked | **strongest sub-area** |
| 3 | Sysvals | very good, M4 | **`get_sr` not emittable — `sr_sel` untested** | good on M4, blocked on G17P |
| 4 | Interpolation | very good, mixed | `iter` and `iter_at` each one field short | STRONG |
| 5 | Tilebuffer | moderate | `tile_read`/`tile_read_mrt` **M4-only** | target-lopsided; BG/EOT program side is a documented negative |
| 6 | Calls | good, mixed | **`call` not emittable — 4 of 5 fields tokenization-only** | semantics good, emission absent |
| 7 | Scratch | helper protocol EMPTY; ceiling exact | n/a | three-times-independent negative + two positives |
| 8 | Linking (prolog/main/epilog) | contract specified & constructed, M4 | rests on `call`, which is not emittable | widest know/emit gap |
| 9 | Sideband (USC / UVS / varying budget) | partial | n/a | one ungated G17P DATA-TRACE + one M4 capacity sweep |
| 10 | Epilogs (blend/logic/conversion) | **complete for the tested surface**, M4 | nothing on G17P | best-covered, worst-attached |

Machine-readable form: `analysis/p08_evidence.json`. Ranked gap list:
`analysis/p08_gaps.md`. Drafted (not applied) closure cell:
`analysis/p08_closure_cell_draft.md`.

---

## 1. Inputs — VS fetch / `stage_in` / stage entry

**Established.** VS attribute fetch is **in-shader software fetch**: there is no
fixed-function attribute-fetch descriptor. Stride, offset and format live in the compiled
shader; the command-stream attribute table at `gpu_va 0x10000100000` supplies only the base
pointer, preloaded into a uniform slot selected by `device_load` byte+4 `base_slot = 0x03`
(EXP-0031, **G17P**, `OWN-SHADER-DIFF`, five layout knobs each moving exactly the predicted
bytes — stride 32→64 flips the `imad` immediate `80 00`→`00 01`, perVertex→perInstance flips
the `get_sr` selector `0c dd`→`0c d8`; **no run count, no cross-run gate**).

On M4, EXP-0109 measured the same shape under a gate: seven `MTLVertexFormat` categories
produce mutually distinct compiled bytes from the same slot; four layout knobs each move the
bytes independently; a nonzero instance step rate is **not free** (rate 1→2 costs +26 bytes,
consistent with a real compiled division). And the robustness result a driver actually needs:
**out-of-range fetch reads exactly zero with no fault**, and the fetch address is computed
from `vertex_id` — already base-inclusive — not from the raw index, so a `baseVertex` of
1,000,000 puts every fetch far outside the buffer and every one reads zero. `HW-VALIDATED`,
4/4 cases, both runs byte-identical. EXP-0137 extends the same policy across a genuine CALL
boundary.

The **entry contract** is a clean negative: nothing is preloaded into a GPR in any stage.
Compute must emit `get_sr` for thread IDs, vertex must emit `get_sr` for
`vertex_id`/`instance_id`, and fragment receives varyings only through the interpolation
datapath. Only the **uniform** register file is preloaded — buffer base pointers and scalar
constant uniforms — populated by the constant/uniform program (EXP-0031, **G17P**).

**Not established.** Any G17P *gated* capture of vertex fetch, format lowering, layout knobs
or OOB behaviour: the G17P side of this sub-area rests entirely on one ungated 2026-07-07
byte-diff. Nor the bit-level encoding of each format's load/shift/normalize sequence
(EXP-0109 establishes *that* the code differs and by how much, not the encoding), packed or
integer-typed varyings, or an FS `stage_in` requesting a varying the VS never wrote.

## 2. Outputs — FS colour/MRT/dual-source/depth/stencil/sample-mask, VS pre-raster

This is the strongest sub-area, and it is the only one where the **field-level** map exists on
G17P for the whole path.

**On G17P (EXP-0155, 99,526 swept cases over two gated runs).** The fragment output path
`frag_tile_setup` → `frag_color_pack` → `frag_color_store` / `imageblock_store`, plus
`frag_depth_store`, has an exact legal-value rule per field, with the **silent-zero traps
named**: `frag_color_store.mask` bit 0 clear gives a silent zero; `frag_color_pack.src_desc`
off `mod 8 ∈ {4,6}` silently zeroes; `imageblock_store.b6` bit 0 clear silently zeroes;
`frag_depth_store.b4` is correct **only at 0** and silently zeroes at every other residue
mod 32. Separately, `frag_tile_setup` has only **one** live field — `sel`, `access` and `b5`
are inert over 256 values on eight arms (EXP-0163).

Two G17P findings here are load-bearing for a driver and easy to miss:

- **The `0x57` collision is resolved.** EXP-0091 (M4) first reported that the fragment
  kill/target-mask op shares byte0 `0x57` with the vertex varying store and is mis-tokenized
  through the `vary_store` descriptor. EXP-0155 §4.1 resolved it **on G17P** from two
  independent code paths that produce the identical rule: `byte+1 & 7 == 6` preserves the
  8-byte vertex varying store, `== 4` or `== 5` preserves the 6-byte fragment kill op,
  `== 3` or `== 7` **faults**, `== 0,1,2` **silently zero** — and `byte+2` is a **don't-care
  across all 256 values on four independent programs**, so the `byte+2 == 0x54` the current
  descriptor leans on selects nothing. The recommended split has not been applied.
- **A fragment colour-store variant `db.json` does not decode.** EXP-0163 §4b found a store
  with `byte+1 == 0x86`, matching neither `frag_color_store` (`0x06`) nor `imageblock_store`
  (`0x16`), falling through to a **14-byte compute `device_store`** in a fragment program that
  has no writable device buffer. Consequence: **every occurrence census ever run against that
  descriptor is unquantified over this form.** The proposed nibble-split fix is explicitly
  `INFERRED` — byte+1 was never swept.

**On M4 (EXP-0029 supplies the G17P encoding, EXP-0109/0117/0091/0111/0097 the semantics).**
`frag_color_store` is `e7 06 54 <src> 00 <rt> 01 4e …`, 12 bytes, with byte+5 the render-target
index as `(rt<<1)` — splice-proven on G17P. MRT scales cleanly 1..8 with independently correct
per-target values and a **hard ceiling of exactly 8** (index 8 raises a *fatal, uncatchable*
process abort the instant the array is indexed, with no shader involved). Dual-source blend is
native and the naive model is wrong: `Source1Color`/`Source1Alpha` are **factor choices**, so
the confirmed equation is `result = src0 * factor(src1) + dst * dstFactor`; at the ISA level
dual source is "just an extra output register + one store". Explicit depth output overrides
the interpolated depth for all three qualifiers and is **late**, not early. `[[stencil]]` is
real and **truncates `& 0xFF`** rather than clamping — proven by the 256→0 and 257→1 cases,
which no clamp model can produce. Output ordering has no hazard: source-statement order
compiles byte-identically, and a depth-test failure driven by the shader's own depth output
suppresses colour *and* stencil, with the correct configured stencil op firing in both
assignment directions.

The kill path is a genuine instruction, not a folded flag: a 6-byte submission op
`57 <B1> 54 <B3> <B4> <B5>` plus a 6-byte companion `07 02 54 01 …`, emitted iff the shader
calls `discard_fragment()` or writes `[[sample_mask]]`, with **byte+4 bits[4:0] a
splice-proven source-register select** (0x00 reads the real mask; 0x01/02/04/08/10 read an
always-zero register and kill colour, depth and occlusion together). Discard has **SPIR-V
demote** semantics, and suppression is complete across **five** channels — colour, depth,
device store, atomic and `[[sample_mask]]`. `[[sample_mask]]`'s width is exactly
`rasterSampleCount`, with every bit at position ≥N silently inert even at `0xFFFFFFFF`.

VS pre-raster outputs: NaN in any position component discards; `+Inf` x or y discards while
`−Inf` produces a full fill; `[[point_size]]` is exact for 4..511 and **clamps** 512, 1000,
1e8, NaN and +Inf to the identical 511×511 footprint; `[[render_target_array_index]]` and
`[[viewport_array_index]]` **clamp every out-of-range value to index 0** — not to N−1, not
modulo, not discard. Provoking vertex is fixed to the **first-fetched vertex of each assembled
primitive**, with no Metal control, so GL's last-vertex convention must be emulated.

**Not established.** Any G17P *behavioural* evidence for MRT count, dual-source, depth,
stencil, sample-mask width, discard/demote or output ordering — all of it is M4. The role of
byte+1 bit 7 (the `0x86` variant). `frag_color_pack.dst`, `untested` on G17P and the single
field blocking that instruction. The encoding behind divergent RT routing: EXP-0111 FS-11 and
EXP-0121 OPT-08 show correct hardware routing to 2 and 3 targets from a program containing
**one** `frag_color_store` with `rt_index = 0` as an immediate and **two** `frag_tile_setup`
brackets with selectors `0x0`/`0xc`, which does not match the static-MRT table — flagged as a
possible new capability lead. Stencil suppression from a demoted lane (INFERRED by analogy;
no MSL surface exists). Per-sample mask-driven suppression of depth/stencil for a *specific*
excluded sample (proven for colour only).

## 3. Sysvals

**Established.** The `get_sr` SR number is **byte1**, correcting EXP-0010's claim that byte0's
high nibble was the selector — that nibble is the destination GPR (EXP-0031, **G17P**,
splice-validated on six SR values). `sr_sel` bit 7 is a structural discriminator over the full
256-value space: `0x80–0xFF` reads the special-register file, `0x00–0x7F` materializes the
selector byte *itself* into the destination at a single fixed slot, and **no value anywhere in
the range faults** (EXP-0092, M4, exhaustive, two gated runs). The GPR file's hard ceiling is
**exactly 96** along the get_sr-dst / device_store-index_reg path, with register 112 genuinely
nondeterministic; EXP-0155 independently reproduced the same boundary **on G17P across seven
different fields**, where crossing it **hangs** rather than zeroing. SR `0x88`/`0x8a` =
`base_vertex`/`base_instance`, upgraded from `(inferred)` to `HW-VALIDATED` on M4 with
nonzero, negative and boundary draws. Fragment selectors: `0xa0`/`0xa1` = integer pixel X/Y
(INFERRED on G17P by byte-diff, HW-splice-validated on M4 by a clean mutual swap), `0xc5` =
`front_facing` (HW-validated on **G17P**, both windings), `0x84` = helper status.
`barycentric_coord` and `point_coord` are **interpolated**, not `get_sr`; `primitive_id` is a
flat tiler-output load. System values are **not** preloaded into uniform registers — reading
`vertex_id` changes only the shader code and leaves the USC preamble byte-identical
(EXP-G1a, **G17P**, DATA-TRACE).

**Not established — and this is the sharpest gap in the whole row.** `get_sr.sr_sel` is
**`untested` on G17P** (EXP-0169, 256 dense values but **one carrier**), as are `dp_width` and
`dp_marker`. `get_sr` is therefore **not emittable**, so **no system value can be emitted on
the documentation target at all**. The exhaustive characterization exists — on M4.
Also open: `sample_id` has **no SR number** (a `0x97` path that folds to 0 at one sample; the
compute-stage read of `0x97` returns a constant 32, which is *consistent with* but not proof
of fragment-only semantics); draw-ID is UNKNOWN with no Metal surface to test it, so
`load_draw_id` must be a userspace-supplied per-draw uniform; `get_sr 0x84`'s raw bit pattern
is unvalidated because MSL canonicalizes it through a bool.

## 4. Interpolation

**Established.** Perspective correction is a **multi-instruction lowering, not a mode bit**:
linear is four `iter` with byte+6 `0x00`; perspective adds a W-denominator `iter`
(byte+6 `0x04`), an `0xaf` reciprocal and a per-component multiply. `iter` is 10 bytes with
byte+5 the source varying slot as `(slot<<1)` — splice-proven on **G17P** by switching the
output from `color.x`'s x-gradient to `color.y`'s y-gradient. `iter_flat` is 6 bytes and loads
the provoking-vertex attribute with no interpolation. The pull model is **not** a separate
instruction: `interpolate_at_center/centroid/sample` compile byte-identically to the matching
qualifier (EXP-0029, G17P; independently byte-diffed on M4 in EXP-0109).

`iter_at.loc` is **bit 1 alone** — 0 = centroid, 1 = per-sample, two equivalence classes of
128 with bits 0 and 2–7 free — strictly better than `db.json`'s `{1: centroid, 3: sample}`
enum, and it is live only at ≥2 samples because at one sample centroid and sample are the same
point (EXP-0163, **G17P**, `hardware-run`, 256 values × 10 arms; **PROVISIONAL — one gated
run**). Behaviourally, centroid and sample were directly discriminated on M4: within one
partially covered pixel at N=4 the two live invocations report *identical* centroid values and
*measurably different* sample values, each matching its own sub-pixel position.

Two driver-safety facts here are the kind that silently produce wrong pixels:

- **`interpolate_at_offset` does not follow the MSL spec.** Every measured value matches the
  plane evaluated at an *absolute* window-space pixel-local coordinate equal to `(dx,dy)`
  directly — origin at the pixel's top-left, y downward — with no clamping up to `|offset| =
  2.0`. A driver must transform `(dx,dy) → (dx+0.5, 0.5−dy)`. The internal control is decisive:
  `interpolate_at_center()` and `center_perspective` both read `0.0` in the same shader where
  `interpolate_at_offset(float2(0,0))` reads `−1.0` (EXP-0111, M4).
- **`barycentric_coord`'s lowering is incomplete unless the shader consumes `[[position]]`.**
  Without a position read the compiler emits 2 `iter` and **zero** `fspecial` — raw
  perspective *numerators* with the third derived as `1−b0−b1` and the normalize-by-sum step
  absent. Consuming `[[position]]` in any form, even only storing it to a device buffer,
  restores the standard perspective-correct value. MSL's own
  `[[barycentric_coord, center_perspective]]` qualifier is a **complete no-op** — byte-for-byte
  identical to the unqualified form — so there is no MSL-level escape hatch. A clean-room
  backend must **always** emit the full W-denominator + reciprocal + normalize sequence. The
  convention is settled: `.x/.y/.z` follow the primitive's vertices in **emission order**
  (`vid%3 == 0,1,2`), the same convention independently established for `primitive_id`
  (EXP-0137, M4, 7-variant factorial × two independent geometries).

`primitive_id` tracks primitive **assembly order** post-index-resolution and **resets to 0 per
instance**. Derivatives are quad-local, proven decisively by splitting a step within versus
between quad column-pairs. Dynamically indexed fragment inputs have **no register-sourced slot
path**: `iter`/`iter_flat`'s slot is a compile-time immediate in every observed instance, and
an 8-way dynamic index lowers as "materialize every candidate statically, select via ALU".

**Not established.** `iter_at.grp` is `untested` on G17P (EXP-0168's render arm recorded it
**LADDER-FAILED, 0 eligible arms**) and is the only field blocking `iter_at`; `iter.b9` is
`single-template-inference` and is the only field blocking `iter`. So a driver can emit flat
varyings and nothing else. `iter_flat` *is* marked emittable but its `_instruction` label is
`corpus-correlation` — an unearned pass under the EXP-0173 §7.2 defect. Also open: the full
bit-decode of `iter` byte+8 and the W-coefficient addressing; the instruction supplying the
`+0.5` pixel-centre offset; and the `0x92`/`0x90` derivative axis-byte anomaly (every
dfdx-only kernel, 5/5, compiled to `0x90`, contradicting `docs/isa/encoding-tables.md`).
Finally: MSAA interpolation was never characterized **on G17P** — EXP-0031's own top
recommended-next was an MSAA pipeline for `sample_id`, and that work happened on M4.

## 5. Tilebuffer

**Established.** `tile_read` is the `ld_tile` analogue — byte0 `0x67`, byte+1 `0x0e`, 12 bytes
— and programmable blending is proven in-shader on **G17P**: a `[[color(n)]]` fragment *input*
compiles to it, and `src*src.a + dst*(1−src.a)` reproduces exactly over three different clear
colours (EXP-0029).

On M4, EXP-0147 gave both `tile_read` and `tile_read_mrt` a complete legal-value map over
25,064 cases and two gated runs, and the driver-relevant finding is the failure *mode*:
**byte+6 bit 0 is a read-enable whose even values give a silent zero**, `rt_index` is correct
only at `0x00,0x01,0x80,0x81` with one attachment bound and silently zeroes otherwise, and
`tile_read_mrt.fmt` is correct only at `{0x2e,0x2f,0x6e,0x6f,0xae,0xaf,0xee,0xef}` — bits 0, 6
and 7 don't-care, bits 1–5 the format selector. In a BG/EOT program a wrong value here is a
**black tile, not a loud failure**.

EXP-0130 **constructed** a real tilebuffer-read / attachment-write program from our own MSL:
`f_eot_combine` (`dst*2.0 + src`) is behaviourally exact against a host oracle on 4/4 boundary
cases and its 120 extracted bytes contain both `tile_read` and `frag_color_store`, with a
paired falsifier proving tile-independence. Its negative is a genuine driver trap: a **pure
passthrough** shape (`return dst;`) is **elided entirely** — 16 bytes, neither opcode — so an
identity shader cannot be used to exercise or validate the tilebuffer path. That
independently reproduces EXP-0117's blend-side elision from a different code path.

EXP-0108's 40-case, 11-axis, six-gated-run matrix found **no BG/EOT program record, pointer or
tag** at the userspace↔kernel boundary for any tested configuration, and states the
consequence plainly: *"there is no register file, calling convention, or instruction-level
tilebuffer-load/store ABI to characterize from this experiment's evidence."* Two hypotheses
remain undistinguished — a fixed canonical routine whose address never changes, or genuinely
fixed-function silicon/firmware — and it explicitly does not refute a program existing outside
the matrix.

**Not established.** Any **G17P** field-level evidence for `tile_read`/`tile_read_mrt` — every
field's target is M4, and neither instruction is emittable. `imageblock_load` was NOT
ATTEMPTED because **no carrier we can compile emits it**: the explicit-layout fragment
imageblock still does not compile, the programmable-blending route compiles to `tile_read`
instead, and a plain colour output compiles to `frag_color_store` or `imageblock_store`. Also
unexplained: why the choice of texture-sample form changes the store encoding at all (an
implicit-LOD sample carrier's RGBA32Float output encodes as `imageblock_store`, while the
byte-for-byte equivalent explicit-LOD program emits `frag_color_store`). `n3_sample_read` —
the fragment sample-id / sample-position read — has `b1` and `b3` `untested` on M4.
The `usc` low-bit tag and `rsrc_spec`'s Apple9 bit layout are PUBLIC-only inference from
Mesa's M1/M2-class genxml and are explicitly not asserted as Apple9 facts.

## 6. Calls

**Established.** G17P has a real CALL/RETURN in the control-flow family (byte0 low nibble
`0xf`), not a dedicated opcode group. CALL is `0f 05 54 1a 8f 00 56 <off40> 00`, 14 bytes, and
the target is exactly `(call_addr + 4) + off40` — verified at four distinct distances. RETURN
is `8f <linkmode> 54 00`, 4 bytes, with **no target field**: the return address comes from a
hardware link register / control-flow stack. Every out-of-line call is preceded by the 4-byte
frame marker `43 00 00 01` (which corrects EXP-0030's claim that `0x43` was mesh-unique) and
followed by the 6-byte reconverge `0f 06 04 02 00 00`; the call reuses the `0f 05`/`0f 06`
execution-mask push/pop machinery, so a call is a masked branch that saves the return context
(EXP-0035, **G17P** — but with **no run count and no cross-run gate**).

The calling convention: arguments in consecutive 32-bit GPRs from **r10**, `half` args in the
low 16 bits, return value in **r10**, no separate argument stack for the counts tested.
**The stack frame is the per-thread scratch**: a callee exceeding the 96-GPR file spills
there, and a non-leaf callee saves its link register there around inner calls. EXP-0137
extended the argument side on M4 to five scalars landing in raw destination registers
`0xa..0xe` (r10..r14). Recursion is lowered to **iteration** — a backward jump, no self-call —
so unbounded recursion is not representable and call depth is statically bounded at compile
time.

EXP-0117 resolved the `byte+6` `0x54`-vs-`0x56` discrepancy on M4: it is **uniformly `0x54`**
across six constructed topologies and an `off40` range of −84 to −154, refuting both a
call-site-count and a leaf-vs-nonleaf explanation (a toolchain-version difference is the
leading candidate and is explicitly INFERRED). Call **nesting depth 1..128** is exact with zero
faults; beyond 128 is UNTESTED, not "unlimited".

**Not established — and this blocks sub-area 8 entirely.** `call` is **not emittable**:
`b3`, `b5`, `b6` and `tail` are all `tokenization-only`, with the range string *"framing only
(round-trips; no value semantics established)"*, and only `offset` is emitter-grade at
`isolated-byte-diff` over four distances. `ret.scoreboard` is `corpus-correlation` — EXP-0172
swept 41 of 256 values on one arm in one run and **declined promotion in advance** — so `ret`
is not emittable either. The non-leaf frame (`0x6f` prologue + the `0x07` link save/restore
pair + `8f 12` ret) is explicitly *"byte-diff (NOT HW-isolated) … structure clear; fields not
splice-isolated"* in EXP-0035's own evidence table, and the indirect call (`0f 80` plus the
`0x4b` marshalling run) has behaviour HW-validated but operand fields TBD. No G17P replication
exists for any of the M4 call facts.

Note also that `frame_prologue`, `link_save_restore` and `spill_frame_marker` — three of the
five instructions that clear both bars — carry a caveat each: EXP-0173 found
`link_save_restore.b1`, `.marker` and `.scope` have **zero free bits** (part of the match, not
fields; its real payload is the 16-bit `dir_offset`), and `spill_frame_marker`'s exact role is
recorded UNRESOLVED, with EXP-0041 having found its byte pattern `60 00 00 00` **zero times**
in every captured main including proven-spilling ones.

## 7. Scratch

**Established — as a negative, three times independently.** (1) EXP-0041, narrow BO allowlist
at 208–576 B declared scratch: no scratch-correlated helper record, launch word, FS state word
or allocation change. (2) EXP-0107, wide-content dispatch-time sweep at **454× that pressure**:
`bo_count` (27) and `bo_total_bytes` (2,428,032) identical across every successful level in
both runs; multiplying declared scratch by 32–42× at fixed grid changes nothing — the
registered-BO footprint tracks **grid size only**. (3) EXP-0125, init-time lifecycle trace:
the full address-free BO inventory is **byte-identical** between a process that never spills
and one that spills 98,320 B/thread, at **all six checkpoints** from `DEVICE_CREATED` to
post-dispatch, and selector-5 ("shared pages") was never observed to be called at all.

Two positives came out of the same work. The declared per-thread scratch **ceiling is exact
and stage-uniform**: last success K=65,431 = **261,740 bytes**, first failure K=65,432 =
261,744 bytes — a 4-byte resolution, identical for CS, VS and FS, and a **compile-time**
property (a clean `nil` with "Compute function exceeds available stack space", no fault, no
hang, no silent wrong answer). Measured against Mesa's own byte→dword formula the ratio is
2.0032×, i.e. Mesa's `AGX_MAX_SCRATCH_BLOCK_LOG4 = 6` is too high by very close to a factor of
two on this hardware. And a real failure mode exists under concurrency: above `n_queues = 4`
the dominant signature is **checksum mismatch — silent numerical corruption**, not a clean
rejection, with an onset threshold that is *not* constant across sessions.

**Not established.** Everything the helper protocol needs, in EXP-0107's own words: helper
`binary`/`cfg`/`data` tags and every `cfg` bit; helper `data` input special registers and
NEXT/ACK/NACK doorbell encodings; scratch header, per-core block list, block descriptor,
alignment/address shift, bucket rules, maximum active subgroups, block size/count;
topology/core-mask to helper-core mapping; reset/growth/concurrency semantics; and proof that
G16/G17 consume the existing `drm_asahi_helper_program` fields at all. The trace vector's own
blind spot is named: the interposer covers only `IOServiceOpen`/`IOConnectCallMethod` and logs
only the *presence* of the firmware-shared submission-ring pages, so a doorbell protocol
living there could not have been found. No G17P replication of any of it.

## 8. Linking — prolog / main / epilog

**Established.** There is **no native fixed-function or separately-loaded prolog/epilog unit**.
Metal's own compiler never produces a separately-addressed prolog object for attribute fetch or
an epilog object for fragment output: every pipeline reports exactly
`[_agc.main.constant_program, _agc.main]` (EXP-0109, 10 spot-checked cases spanning both
stages). A Mesa-style prolog/epilog key-based variant split is therefore a **software**
organization choice, not a hardware requirement.

EXP-0137 **refines** that rather than reversing it: given the right shape, Metal's own
toolchain *does* emit a real out-of-line object. A vertex helper performing a genuine memory
load and a 2-call-site compute helper each produce **three** Mach-O regions with a real named
local symbol and real `call` / `frame_marker` / `pop_reconverge` instructions, while a
single-call-site fragment epilog is inlined despite `[[clang::noinline]]` (confirmed
independent of attribute spelling). EXP-0109's ten cases all happened to land in the inlining
regime.

The seam contract is **constructed and numerically validated**: an epilog seam forwarding a
branching blend computation across a real call boundary matches the standard blend arithmetic
exactly in both branch modes (so an out-of-line epilog may use ordinary conditional branches,
not just straight-line code); a prolog seam calling a fetch helper is exact in range and
exactly zero out of range; and a five-argument, `float4`-returning callee called from two sites
is exact for every input.

**Resource merging is not a real problem**, and the reason is a proven negative: an entry-only
MSL attribute (`[[color(0)]]`) on a **non-entry** helper parameter is syntactically accepted
and **semantically inert** — the parameter simply receives whatever the caller forwarded. So a
genuinely out-of-line callee cannot and must not declare its own resource or stage-IO
bindings; a driver must fix a single pipeline-wide binding table **before** generating any
segment, and no runtime relocation happens at the call boundary. (This refuted EXP-0137's own
pre-registered H2d, which expected rejection or unsafe garbage.)

**Not established.** The entire contract rests on the CALL/RETURN ABI, and **`call` is not
emittable** (§6) — a driver following this contract cannot currently generate the instruction
it prescribes. The exact physical register numbering of a multi-component CALL return is the
one hole EXP-0137 could not pin down (a `float4` result is retrieved by four post-call ops of a
*different* move class from the argument path). No G17P evidence exists for the seam, the
region count or the inert-attribute negative. And no experiment has attempted the thing
closure rule 6 actually asks for: a split prolog/epilog pair generated end-to-end by **our
own emitter** rather than by Apple's compiler from our MSL.

## 9. Sideband

**Established.** There is **no G13-style single tagged "USC control-word list"**. Binding is
split across three structures: textures and samplers into a Tier-2 argument buffer whose
2-pointer header `[texture-array VA][sampler-array VA]` *is* the count/split field
(`num_textures = (samp_ptr − tex_ptr)/0x20`); buffers into a table of 8-byte LE GPU VAs in
binding-index order; and uniform preload into a per-stage USC preamble program led by tagged
8-byte words (`0x0088_00XX` register/shader-config with `XX = stage × 0x0c`, `0x0042_XXXX`
uniform-data pointer, `0x0020_00XX` uniform-slot count). VS→FS UVS linkage is **positional and
cross-stage-compacted**: `[[position]]` occupies slots 0–3, user varyings start at slot 4 with
one slot per scalar component in declaration order, and only varyings the FS consumes are
emitted — HW-validated by reorder, where an identical FS reading the middle slot rendered
0.200 versus 0.302 depending only on which value the VS wrote there (EXP-G1a, **G17P**, 34
draws, **ungated**).

The capacity side is exact on M4: the varying budget is **124 user scalar components**, counted
**per scalar** — independent of declared vector width *and* of bit width — and on **post-link
liveness**, never on the raw declared struct size (declared 500 / used 10 passes; declared 200
/ used 200 fails). N ≥ 127 crashes Metal's out-of-process compiler service outright. Clip
distance is an **independent** budget of exactly 8 that is never shared with the varying
budget, and `cull_distance` is not a recognized MSL attribute at all (EXP-0097, 140 cases × 2
gated runs).

**Not established.** The generalized byte field `0x58000+0x2c = 4 + total_user_varying_scalar_components`
(ceiling 128) is explicitly **INFERRED** — EXP-G1a HW-validated it only for `nvary` 0..8 and
EXP-0097 did not re-capture the byte at the 124-scalar boundary. The mismatch between Metal's
124-component validator limit and the hardware field is unresolved: EXP-0097 notes EXP-G1a's
`0x57` varying-store slot field **structurally reaches 511**, and bypassing the validator via
hand-assembled UVS stores was declared out of scope. Packed and integer-typed varyings were
never swept, nor the inverse linkage direction. Neither the USC grammar nor the UVS linkage has
a gated (two-run) capture. And `docs/mesa-userspace-requirements.md:181` — the P0.8 doc row —
still lists the state-baking split as pending: *"vertex-input formats, polygon stipple,
sample-mask, cull-distance, color-format conv"*.

## 10. Epilogs — independently generated blend / logic / conversion

By volume this is the best-covered piece of P0.8. By attachment it is the worst: it is
entirely M4/G16G, it has **no `PROVENANCE.md` row**, and **none of it is in `docs/`**.

**Established (EXP-0117, 148 cases × 2 gated runs, M4).** All **19** advertised
`MTLBlendFactor` values match the standard formula table exactly in both the source and
destination roles — including `SourceAlphaSaturated`'s RGB-role `min(srcA, 1−dstA)` correctly
diverging from its alpha-role pin at 1.0 — and all **5** `MTLBlendOperation` values match, with
RGB and alpha ops independently selectable. None requires emulation. The write mask is a
genuine per-channel gate whose layout is **`A=0x1, B=0x2, G=0x4, R=0x8`** — *not* the naive
`R=0x1` ordering — with out-of-range bits silently inert. The blend constant is **not clamped**
to `[0,1]`. sRGB attachments **blend in linear space**, so an epilog generator must decode on
load, blend linear, and re-encode on store. Blending on an integer format is a **fatal
process-aborting assertion** with no fallback path, as are `MTLBlendFactor = 20` and
`MTLBlendOperation = 6`. Alpha-to-coverage's derived fraction equals the shader's alpha
**exactly** at quarter-sample granularity, with the shader's alpha still written to the passing
samples. NaN and Infinity propagate through Add **bit-exactly, payload preserved**, with no
flush-to-zero and no canonicalization.

**The synthesis rule an epilog generator must implement** was read off Metal's own compiler:
classify the configured `(sourceFactor, destinationFactor, op)` triple at pipeline-build time
and emit `tile_read` **only if** the destination's true numeric value is needed. It is proven
structurally, not inferred: blending disabled and blending enabled with `src=One, dst=Zero`
compile to **literally the same 56 bytes**; a `src=Zero, dst=One` dst-identity compiles to a
**16-byte stub** with only a `frag_tile_setup` and a fence; and only a genuinely
data-dependent configuration is longer and contains `tile_read` — all from the *same* MSL
source under pipeline-descriptor variation alone.

And the row's headline construction: **logic ops** — a `VK_LOGIC_OP_*`-class capability the
fixed-function-shaped Metal blend descriptor **cannot express at all** — were independently
constructed as a programmable epilog and are **bit-exact 8/8**, including the all-zero and
all-one boundaries. The working template is exactly three steps: declare the output attachment
**also** as a `[[color(n)]]` fragment *input* (which forces `tile_read`), compute with ordinary
bitwise ALU against the read-back destination, and return it as the ordinary `[[color(n)]]`
output (which emits `frag_color_store`). No special hardware mode, descriptor field or
fixed-function unit exists or is required — logic ops are, and must be, entirely in-shader.

**Not established.** Any of it on **G17P**. Exhaustiveness — not every `(factor, factor, op)`
triple was constructed, only isolating single-factor and single-op cases plus a handful of
combined ones. **Format conversion across advertised formats**, which the row explicitly asks
for: spot-checked at RGBA16Float, RGBA8Unorm and sRGB only. (P1.2's 138-format × 11-axis matrix
and EXP-0079's rounding rules are the adjacent evidence, but they belong to a different row and
were not run as epilog conversion.) MSAA-vs-blend timing — whether the equation applies pre- or
post-resolve — was not attempted. Metal 4's `MTL4BlendStateUnspecialized` deferred-specialization
workflow is a flagged lead, read from public headers only.

Above all: **no epilog has been generated by our emitter.** Every epilog in EXP-0117 and
EXP-0137 is Apple's compiler compiling our MSL, so closure rules 1 and 6 are both unmet for
the sub-area the row names most explicitly.

---

## Closure-rule status for the row

| Rule | Status |
|---|---|
| 1 — value/behaviour **generated**, not merely decoded | **NOT MET.** No P0.8 object has been generated by our own emitter. Field sweeps splice our own compiled bytes, which establishes semantics but is not whole-object generation. |
| 2 — complete probe / commands / raw / failures / analysis committed | **PARTIALLY MET.** Thirteen experiments carry pre-registration + capture contract + two gated runs + manifest. The four carrying G17P *semantics* (EXP-0029, EXP-0031, EXP-0035, EXP-G1a) predate that regime: no run count, no cross-run gate, no pre-registration. Two more (EXP-0050, EXP-0071) are quarantined. |
| 3 — evidence chain in `PROVENANCE.md` | **NOT MET** for the bulk. EXP-0109, EXP-0117, EXP-0111 and EXP-0108 own no row. |
| 4 — normative docs carry exact fields, ranges, fallbacks, target status | **NOT MET.** EXP-0117's entire body is absent from `docs/`; `docs/mesa-userspace-requirements.md:181` still reads "partial"; the named destination `docs/abi/` does not exist. |
| 5 — adversarial reproduction or second method | **MIXED.** Strong for interpolation (a factorial across two independent geometries plus a structural mechanism), for the `0x57` collision (two independent code paths, two targets) and for scratch (three independent methods). Weak for calls, sideband and epilogs — each single-method, and two of the three single-target. |
| 6 — object independently generated and consumed without a captured Apple template | **NOT MET.** Same wall EXP-0173 recorded for the row set. |

## Boundaries — out of scope, not gaps

Recorded as EXP-0134 did for the compression codec and SFU-04. Full table with quotes:
`analysis/p08_gaps.md` and `analysis/p08_evidence.json` → `clean_room_boundaries`.

1. **Apple's own BG/EOT/partial programs.** Apple-authored precompiled shaders; forbidden to
   inspect or commit. EXP-0108 searched for a program *record* at the data boundary — lawful
   DATA-TRACE — across 40 cases and six gated runs and found none, and must not read the bytes.
   The driver constructs its own instead, as EXP-0130 demonstrated.
2. **The scratch/helper `binary`/`cfg`/`data` fields.** A host-observability boundary that
   behaves like a clean-room one: three independent lawful methods all reach the same negative,
   and going further means reading Apple's kernel or firmware code. EXP-0125's conclusion is
   that these must be *"constructed from first principles against the hardware's actual
   behavior … not decoded from a macOS capture"*.
3. **A second interpolation/derivative/blend mode Metal never emits.** EXP-0111 FS-05 states
   the general form exactly: no MSL-level probe can distinguish "only one mode exists" from "a
   second mode exists that Metal never emits", because there is no compiler-reachable starting
   point to perturb. Extrapolate-and-test still applies wherever a *motivated* hypothesis
   exists — EXP-0147 found matrix multiply-subtract that way — but it needs a hypothesis, not a
   sweep.
4. **Apple's inlining heuristic.** Out of scope by EXP-0137's own pre-registration: not a
   hardware fact, and a driver controls its own out-of-lining regardless.
5. **The fused `store_block_agx`-class EOT eviction op.** NOT REACHED / UNKNOWN; the only byte
   value available to compare against is Mesa's M1/M2-class encoding, read as PUBLIC
   cross-generation context and explicitly not asserted as an Apple9 fact.

## Non-evidence — must not be cited under this row

`EXP-0050-fragment-output-abi` (QUARANTINED — false clean-room attestation),
`EXP-0071-m4-vertex-fragment-abi-contract` (QUARANTINED pre-GPU, no capture ever run),
`EXP-0057-m4-scratch-pressure-envelope` (QUARANTINED — read a compiled pipeline container
beyond its registered boundary), and `EXP-0118-a18-pro-partial-render-workload` (5-line
RESULTS.md, no target line, no evidence label, no run count, no pre-registration, no committed
raw; committed as "append-only process history", and the only file in the tree claiming a G17P
partial-render result).

## Limitations of this assembly

1. **No hardware.** Nothing here re-observes any claim. Where an experiment's own RESULTS.md
   is wrong, this assembly reproduces the error.
2. **`validation.json` is a moving target.** EXP-0175 owns `db.json`. The 12/28 and 5/28
   figures are a snapshot of the 2026-08-28 generation and will drift.
3. **Provenance ownership is detected by a heuristic** (`analysis/provenance_check.py`): a row
   is "owned" if its evidence cell *starts with* the experiment id. Older rows use a different
   citation style, and the script was checked by hand against lines 47, 48, 51, 95 and 117
   before the result was relied on.
4. **Sub-area assignment is a judgement call.** The row's own scope line reads "linking and
   sideband" as one phrase; this assembly splits them for precision. `analysis/isa_status.py`'s
   `SUBAREA_INSTRUCTIONS` table is the explicit, editable statement of which instruction
   belongs to which sub-area.
5. **Nothing was applied.** `docs/`, `PROVENANCE.md`, `db.json` and `validation.json` are
   untouched. The closure-cell replacement is a draft in
   `analysis/p08_closure_cell_draft.md`.

## Clean-room provenance

```text
Clean-room provenance: PUBLIC (this repository's own committed clean-room artifacts, read only)
Inputs inspected: experiments/*/{RESULTS.md,README.md,QUARANTINE.md,manifest.json},
  PROVENANCE.md, tools/agx-isa/validation.json, docs/**,
  APPLE9_RE_IMPLEMENTATION_GAPS.md, CODEX.md, CLAUDE.md. All authored by this project.
Apple binary introspection: NONE. No disassembler, decompiler or binary-inspection tool was
  run on anything. No Apple binary, framework, kext, firmware, precompiled shader or system
  shader cache was read, and none is quoted or paraphrased anywhere in this experiment's
  output. No shader was compiled; no byte was spliced; no device was contacted.
Reproduction: python3 experiments/EXP-0177-p08-abi-assembly/analysis/isa_status.py
              python3 experiments/EXP-0177-p08-abi-assembly/analysis/provenance_check.py
Evidence: analysis/isa_status.json, analysis/provenance_check.json, analysis/p08_evidence.json,
          analysis/p08_gaps.md, analysis/p08_closure_cell_draft.md
```

## STOPs

No `BLOCKED` state. No device contact, no `macvdmtool`, no excursion outside
`/Users/user/asahi_re/public/agx-re`. Three live device experiments were running throughout and
none of their files was read for write or modified.
