# P0.8 / DRV-ABI-01 — what an implementer still cannot do

Ranked by how badly it blocks a **working** driver, not by how interesting it is. Each gap
names the instruction and field, not the topic, and names the experiment that would close it.

Sources: `analysis/isa_status.json` (from `tools/agx-isa/validation.json`, generated 2026-08-28
— note `db.json`/`validation.json` are owned by the live EXP-0175 and these are a snapshot),
`analysis/p08_evidence.json`, `analysis/provenance_check.json`.

**Target rule throughout:** closure is measured against **full G17P**. A gap marked
`M4-only` means the fact exists and is good, but on the wrong target for this row.

## The headline this list is derived from

Of the **28 instructions a VS/FS/CS stage ABI and its prolog/epilog linkage have to emit**,
`validation.json` marks **12 emittable (42.9%)**. Seven of those twelve carry an
`_instruction` label *weaker than emitter-grade* — and EXP-0173 §7.2 established that the
emittability rule **never reads the `_instruction` label**, so those seven pass the metric
without their own identity/semantics evidence. **Five of 28 clear both bars:**
`frame_prologue`, `link_save_restore`, `pixel_order`, `pop_reconverge`, `spill_frame_marker`.

Not one of those five is an input, an output, a system value, an interpolation or a
tilebuffer instruction. All five are frame/ordering plumbing — and two of them are
themselves compromised: `spill_frame_marker`'s **exact role is UNRESOLVED**
(`APPLE9_RE_IMPLEMENTATION_GAPS.md:2625`, and EXP-0041 found its byte pattern
`60 00 00 00` occurred **zero times** in every captured main including proven-spilling
CS/VS/FS programs), and EXP-0173 found `link_save_restore.b1`, `.marker` and `.scope` have
**zero free bits** — they are part of the match, not fields, so three of that instruction's
six emitter-grade labels assert a choice the implementer does not have.

---

## Tier 1 — nothing runs without these

### G1. `get_sr.sr_sel` is `untested` on G17P — no system value can be emitted at all
**Blocks:** every stage. `vertex_id`, `instance_id`, `base_vertex`, `base_instance`, thread
IDs, `threadgroups_per_grid`, fragment pixel X/Y, `front_facing`, helper status. Without an
emittable selector byte there is no vertex shader, no compute shader and no fragment shader.

`validation.json` → `get_sr`: `sr_sel` **`untested`**, `dp_width` **`untested`**,
`dp_marker` **`untested`**, all `target: G17P`, all from EXP-0169, each recorded as "0..255
dense (all 256 values) … **1 carriers**". Only `dst` and `dst_hi` are emitter-grade. The
instruction is **not emittable**.

This is the single sharpest inversion in the row: EXP-0092 swept `sr_sel` **exhaustively
0x00–0xFF over two gated runs on M4** and produced the strongest field characterization in
the repository (bit 7 is a structural discriminator; 0x00–0x7F materializes the selector
byte itself; no value anywhere in the range faults). That evidence is on the wrong target,
and the G17P sweep that exists has one carrier and was not promoted.

**Closes it:** a G17P re-run of EXP-0092's `srsweep` on **≥2 structurally different carriers**
(the EXP-0163 lesson: two carriers identical in the dimension the field controls are one
carrier — so at minimum one compute and one fragment carrier, since EXP-0031 established the
SR namespace is *stage-contextual*), two gated runs, with the liveness ladder EXP-0155 §3
introduced. Also re-establish `dp_width`/`dp_marker`, which no experiment has ever explained.

### G2. `call.b3`, `.b5`, `.b6`, `.tail` are `tokenization-only` — no call can be emitted
**Blocks:** every out-of-line helper; the entire split prolog/epilog strategy EXP-0137
specified; non-leaf frames; any variant-reduction scheme.

`validation.json` → `call`: four of five fields carry the label `tokenization-only` with the
range string *"framing only (round-trips; no value semantics established)"*, evidence
`EXP-0036`/`EXP-M4-12`/`EXP-M4-13`. Only `offset` is emitter-grade, at `isolated-byte-diff`
over **4 call distances** on A18 (EXP-0035). `ret.scoreboard` is `corpus-correlation`:
EXP-0172 swept 41 of 256 values on 1 arm in 1 run and **declined promotion in advance**. So
neither `call` nor `ret` is emittable.

The semantic layer is fine — EXP-0035 established the target formula
`target = call_addr + 4 + off40` exactly at four distances, args in consecutive GPRs from
`r10`, return in `r10`, the `43 00 00 01` frame marker and the `0f 06 04 02 00 00`
reconverge; EXP-0117 pinned `byte+6` to `0x54` across six topologies and ran call depth
1..128 clean. None of that makes `b3`/`b5`/`b6`/`tail` emittable.

**Closes it:** a G17P field sweep of `call.{b3,b5,b6,tail}` and `ret.scoreboard` on ≥2
carriers with a real host oracle (a callee that returns a distinguishable value, so a wrong
`tail` shows as a wrong result rather than a silent success), two gated runs. EXP-0156's
`ret.linkmode` sweep (0..255 dense, `hardware-run`, G17P) is the model.

### G3. `vary_store.hint1` and `.b5_tag` are `untested`; the descriptor is known-wrong
**Blocks:** every vertex shader. Without an emittable varying store there is no VS→FS
linkage, no `[[position]]` output and no user varying.

`validation.json` → `vary_store`: `hint1` **`untested`** (G17P, EXP-0155, 0..255 dense),
`b5_tag` **`untested`** (G17P, EXP-0155, 0..127 dense), `hint2` and `b7`
`single-template-inference`. The `_instruction` entry itself carries a
**MIS-TOKENIZATION FLAG**.

The descriptor defect is *solved* and *not applied*: EXP-0155 §4.1 resolved the `0x57`
collision on G17P from two independent code paths that produce the identical rule —
`byte+1 & 7 == 6` preserves the 8-byte vertex varying store; `== 4` or `== 5` preserves the
6-byte **fragment kill / target-mask** op; `== 3` or `== 7` **faults**; `== 0,1,2` **silently
zero**; and `byte+2` is a **don't-care across all 256 values on four independent programs**,
so the `byte+2 == 0x54` the current descriptor leans on selects nothing. The recommended
change (match on `byte0 == 0x57 AND (byte+1 & 7) == 6`, length 8, plus a **separate 6-byte
descriptor** for `(byte+1 & 7) ∈ {4,5}`) has not been made.

Two driver-safety facts sit inside this instruction and must not be lost:
`vary_store.hint6` **bit 4 set makes the ENTIRE fragment output read 0.0** — the whole
varying block is lost, not one component (EXP-0163, `hardware-run`, 128/256 on 7 arms across
5 carriers, the compiler-chosen values 0x48–0x4d all have it clear); and
`vary_store.out_slot` is the slot an emitter must get right, **not** `vary_slot.slot`
(EXP-0155 §2.4, confirmed on hardware by EXP-0172 §2.3: `vary_slot.slot` is exactly bit 2,
live on one of four arms, and **not the bit the compiler varies**).

**Closes it:** apply the EXP-0155 §4.1 descriptor split (orchestrator/EXP-0175 owns
`db.json`), then sweep `hint1` and `b5_tag` on G17P against the corrected descriptor on ≥2
carriers, two gated runs.

---

## Tier 2 — the driver runs but cannot draw

### G4. `iter.b9` and `iter_at.grp` block all interpolation
`iter.b9` is `single-template-inference` (G17P, EXP-0163, 256 values × 6 arms) and is the
**only** field blocking `iter`. `iter_at.grp` is **`untested`** (G17P, EXP-0155) and is the
only field blocking `iter_at`; EXP-0168's render arm recorded it **LADDER-FAILED — 0 eligible
arms**. So a driver can emit `iter_flat` but neither `iter` nor `iter_at` — i.e. flat
varyings only, no smooth interpolation, no centroid, no per-sample.

That is a particularly sharp loss because the *semantics* of `iter_at` are the best-measured
thing in the sub-area: `iter_at.loc` is **bit 1 alone**, 0 = centroid, 1 = per-sample, two
equivalence classes of 128 with bits 0 and 2–7 free (EXP-0163, `hardware-run`, 256 × 10 arms,
0/256 live at 1 sample and 128/256 at 4).

**Closes it:** a G17P sweep of `iter_at.grp` on a carrier whose ladder can pass (EXP-0168's
failure was a carrier problem, not a hardware one) and of `iter.b9` on ≥2 carriers that
differ in the dimension `b9` might control — EXP-0163 already showed 7 of 20 "inert" fields
are live once the carrier can see them.

### G5. `frag_color_store.store_mode`, `frag_color_pack.dst`, `frag_tile_setup.{sel,access,b5}`
block the fragment output path
Each is one or three fields away. `frag_color_store.store_mode` is
`single-template-inference` (G17P, EXP-0163, 256 × 8 arms) — the value `0x54` appears in
130/130 of the corpus. `frag_color_pack.dst` is **`untested`** (G17P, EXP-0155). All three
of `frag_tile_setup`'s non-`b1` fields are `single-template-inference` (G17P, EXP-0163,
256 × 8 arms) — measured inert across five structurally different carriers, and *deliberately*
labelled below emitter-grade because the emitter guidance for them is "emit the
compiler-observed value", which is exactly the captured-template dependency closure rule 1
forbids.

The rest of the path is done and precise, including the silent-zero traps a driver must
avoid: `frag_color_store.mask` bit 0 clear → silent zero; `frag_color_pack.src_desc` off
`mod 8 ∈ {4,6}` → silent zero; `imageblock_store.b6` bit 0 clear → silent zero;
`frag_depth_store.b4` correct **only at 0** and silently zeroing at every other residue
mod 32 (all EXP-0155, G17P, 99,526 cases over two gated runs).

**Closes it:** a G17P sweep of `frag_color_pack.dst` (which EXP-0155 already dispatched over
0..255 but could not promote), and a carrier hunt for `frag_tile_setup.{sel,access,b5}` and
`frag_color_store.store_mode` following the EXP-0163 method — build the program that would
*notice* what the field does, rather than sweeping it on a carrier that cannot.

### G6. `tile_read` and `tile_read_mrt` are **M4-only** — the programmable-blend/BG/EOT read
is not measured on the documentation target
Every field of both instructions carries `target: M4` in `validation.json`. `tile_read` has
five blocking fields (`b2`, `b4`, `b7`, `tail`, `b6_hi`), `tile_read_mrt` three (`b4`,
`tail`, `b6_hi`). Neither is emittable.

The M4 evidence (EXP-0147, 25,064 cases over two gated runs) is exactly what a driver needs
and is exactly what must be re-run: `byte+6` bit 0 is a **read-enable** whose even values
give a **silent zero** — in a BG/EOT program that is a **black tile, not a loud failure**;
`rt_index` is correct only at `0x00,0x01,0x80,0x81` with one attachment bound, everything
else silently zeroing; `tile_read_mrt.fmt` is correct only at
`{0x2e,0x2f,0x6e,0x6f,0xae,0xaf,0xee,0xef}` — bits 0, 6, 7 don't-care, bits 1–5 the format
selector.

**Closes it:** re-run EXP-0147's `tile_read`/`tile_read_mrt` arms on G17P, two gated runs.
This is the cheapest large win in the row: the harness, the carriers, the oracle and the
liveness probe all exist and only the target changes.

### G7. `vtx_out_pos.dst` and `.slot` are `untested`, M4-only — the position output cannot be emitted
Both fields carry `target: M4`, evidence EXP-0147, and both are `untested`. EXP-0147 found
them **fully inert** in a single-varying carrier and named the follow-up itself
(*"`vtx_out_pos.slot` in a multi-varying carrier"*). EXP-0168's render arm answered it
properly on G17P — `slot` is **INERT-ROBUST across three distinct carrier dimensions**
including a **mixed-width discriminator** (`half/half2/float/float2/float4`), which exists
precisely because with uniform-width varyings an ordinal and a byte offset are
indistinguishable at every value — and `dst` moved on **1 of 16** in the degenerate
single-varying carrier and **0 of 16** in both rich ones.

But **EXP-0168's render arm is one gated run and its second run is BLOCKED**, so nothing was
promoted and `validation.json` still reads `untested`. A further constraint EXP-0168 recorded:
`vtx_out_pos` **is emitted only by vertex carriers that do not write a device buffer**, so the
second independent observation path those carriers were built for is unavailable.

**Closes it:** unblock and run EXP-0168's second render-arm gated run. The carriers and the
mixed-width discriminator already exist.

---

## Tier 3 — features an application will hit

### G8. `imageblock_load` — five `untested` fields and **no compilable carrier**
`dst` `untested` with **no evidence at all**; `b4`, `b6`, `tail` `tokenization-only`; `fmt`
`corpus-correlation` at two observed values. EXP-0155 pre-registered it as NOT ATTEMPTED and
recorded all three carrier attempts: the explicit-layout fragment imageblock **still does not
compile** (EXP-0142 saw the same failure on macOS 26.6.2 and it reproduces on the neo); the
programmable-blending route compiles to **`tile_read`** instead; a plain colour output
compiles to `frag_color_store` or `imageblock_store`, never a load.
**Closes it:** a tile shader dispatched with `dispatchThreadsPerTile` — the named next
carrier, needing harness support EXP-0155 did not build.

### G9. `n3_sample_read.b1` and `.b3` are `untested`, M4-only — no `sample_id`/sample-position read
This is the fragment sample-id / sample-position read, and the sub-area is a triple gap: the
instruction is not emittable; `sample_id` has **no `get_sr` selector at all** (EXP-0031: it
goes through a `0x97` path and *folds to 0* on a 1-sample target, which is why EXP-0031's own
top recommended-next was "MSAA pipeline to characterize `sample_id`"); and EXP-0092's
selector `0x97` on a **compute** dispatch reads a constant 32 (`threadExecutionWidth`), which
is "consistent with sample-ID being fragment-stage-only … **not proof of its fragment-stage
semantics**". The addendum tracks it as GLIO-A04.
**Closes it:** a G17P MSAA fragment carrier that reads `[[sample_id]]` and `[[sample_position]]`,
with `n3_sample_read.{b1,b3}` swept against a per-sample readback oracle, two gated runs.

### G10. `frag_color_store` byte+1 bit 7 (the `0x86` variant) is undecoded
EXP-0163 §4b: a fragment colour store whose byte+1 is `0x86` matches neither
`frag_color_store` (`== 0x06`) nor `imageblock_store` (`== 0x16`), so the decoder falls
through to a **14-byte compute `device_store`** in a fragment program that has *no writable
device buffer*. The first twelve bytes are identical to a plain colour store except byte+1;
the `fmt` byte is `0x2e`, the RGBA32Float **attachment** format descriptor.
Consequence: every occurrence census ever run against the `frag_color_store` descriptor is
**unquantified over this form**. The proposed nibble-split match fix is explicitly `INFERRED`
— **byte+1 was never swept**.
**Closes it:** sweep `frag_color_store` byte+1 on G17P on the `k_texcube`-shaped carrier and
a plain-store carrier, then apply or reject the nibble split.

### G11. The multi-component CALL return register numbering is unresolved
EXP-0137 §2.2: the argument side is confirmed exactly — five scalar arguments land in raw
destination registers `0xa..0xe` (r10..r14), a direct extension of EXP-0035's "consecutive
from r10". The **return** side is not: a `float4` result is retrieved by **four** post-call
ops of a *different* move class (`reg_move_c9`/`rtq_state_move`) from the argument path's
`falu2i`/`reg_move_c1`, and the physical numbering "is NOT independently re-derived here …
flagged `STRUCTURAL`, open for DRV-ISA-01".
This matters less than it looks — a driver generating its own bytes defines its own
convention — but it is the one hole in an otherwise complete seam contract.
**Closes it:** a splice sweep of the post-call retrieval registers against a callee returning
four distinguishable components.

### G12. Divergent render-target routing has an unexplained encoding
EXP-0111 FS-11 and EXP-0121 OPT-08: a per-fragment-divergent `[[color(n)]]` output routes
correctly to 2 and to 3 distinct targets (hardware readback exact), yet the compiled program
contains **one** `frag_color_store` with `rt_index = 0` as an *immediate*, preceded by
`icmp_pred`+`sel`, and **two** `frag_tile_setup` brackets with selector bytes `0x0` and
`0xc` — which does not match EXP-0029's `0x0`/`0x4`/`0x8` fixed-RT table for static MRT.
EXP-0111 flags it "a possible new hardware-capability lead worth a dedicated splice
follow-up". An array-typed fragment-output struct is rejected at compile time, so a driver
must currently lower dynamic outputs as a branch/select chain.
**Closes it:** splice `frag_tile_setup.sel` and `frag_color_store.rt_index` in the divergent
program with a per-target readback oracle.

### G13. `mesh_out_src.sel` is `tokenization-only` — mesh output cannot be emitted
Single field, "framing only (round-trips; no value semantics established)". EXP-0147
pre-registered it as **not attempted** — it "needs a mesh-pipeline harness".
**Closes it:** a G17P mesh-pipeline carrier.

### G14. draw-ID has no hardware surface
UNKNOWN, and honestly so: Metal exposes no multidraw primitive with a per-draw index visible
to a vertex function, so EXP-0092 could not test it at all. A driver's `load_draw_id` must be
synthesized as a **per-draw userspace-supplied uniform**.
**Closes it:** only a command-stream-level experiment that builds VDM/CDM machinery directly
(P0.5 territory), or the acceptance that emulation is the answer.

---

## Tier 4 — the row cannot close even if every gap above closes

These are not implementer gaps; they are closure-rule failures on evidence that already
exists. They are listed here because P0.8 cannot be marked `CLOSED` while they stand.

### G15. Closure rule 1 and rule 6 are unmet for the whole row
**No P0.8 object has ever been generated by our own emitter.** Every "constructed" epilog,
prolog and BG/EOT program in EXP-0117, EXP-0130 and EXP-0137 is *Apple's compiler compiling
our MSL*. The field sweeps (EXP-0155/0163/0168/0172) splice our own compiled bytes, which
establishes field semantics but is not whole-object generation. EXP-0173 recorded the same
wall for the row set: rule 6 is "MET for the ISA object only, and only over 6 families".
**Closes it:** a hand-built fragment program — `frag_tile_setup` → `iter` → ALU →
`frag_color_pack` → `frag_color_store` — assembled from `tools/agx-isa` with **zero copied
fields**, run on G17P against a host oracle, in the shape EXP-0167 already proved works for
the memory/ALU families (233 of 237 generated programs produce their exact host oracle).

### G16. Rule 3 — the two largest P0.8 experiments have **no `PROVENANCE.md` row**
`analysis/provenance_check.json`: **EXP-0109** (57 cases × 2 runs), **EXP-0117** (148 cases
× 2 runs), **EXP-0111** (56 cases × 2 runs) and **EXP-0108** (40 cases × 6 gated runs) own no
provenance row. EXP-0109's and EXP-0117's only appearances in `PROVENANCE.md` are *inside
other experiments' rows*. That is the entire stage-ABI and epilog body of evidence outside
the paper trail.

### G17. Rule 4 — EXP-0117's whole body is absent from the normative docs
The 19-factor blend table, the 5 operations, the `A=0x1,B=0x2,G=0x4,R=0x8` write-mask layout,
the unclamped blend constant, the sRGB-blends-in-linear-space rule, the exact
alpha-to-coverage relation, the bit-exact NaN propagation, the `[[stencil]]` truncation rule,
the MRT ceiling of 8, the sample-mask width rule, call depth 1..128, and the epilog synthesis
rule itself — none of it is in `docs/`. `docs/mesa-userspace-requirements.md:181` is the
P0.8 doc row ("Fast-link prolog/epilog") and still reads **partial** with an open pending
list; its named destination `docs/abi/` does not exist. `EXP-0172` is cited nowhere in
`docs/` at all.

### G18. All of the G17P evidence in this row except the emit wave is **ungated**
EXP-0029 (fragment ISA), EXP-0031 (SR ABI), EXP-0035 (call ABI) and EXP-G1a (USC/UVS
sideband) are the only experiments carrying G17P evidence for inputs, outputs, sysvals,
interpolation, tilebuffer, calls and sideband semantics. All four date from 2026-07-07 and
**predate the two-run gate regime**: no run count, no cross-run byte-exact gate, no
`PRE_REGISTRATION.md`, no `CAPTURE_CONTRACT.json`. They are good evidence by the standard of
their time and they are not retracted, but they do not meet closure rule 2 or 5 as written
today.

### G19. The M4→G17P replication debt, stated as a list
Everything below is HW-VALIDATED on M4/G16G and has **no G17P counterpart at all**:
MRT count 1..8 and the 8-attachment ceiling; the dual-source blend equation; explicit depth
output; `[[stencil]]` existence and truncation; output ordering and depth-test suppression;
the kill op's `byte+4` register select; discard-is-demote; five-channel side-effect
suppression; sample-mask width; centroid-vs-sample differentiation; `interpolate_at_offset`'s
non-spec convention; the barycentric incomplete-lowering fact and the emission-order
convention; `primitive_id` assembly-order and per-instance reset; quad-local derivatives;
the 124-scalar varying budget and the independent 8-clip budget; the provoking-vertex
convention; `tile_read`/`tile_read_mrt` field maps; the constructed EOT core; the entire
blend/logic/write-mask/sRGB/alpha-to-coverage/NaN epilog body; the split prolog/epilog seam
contract; call `byte+6` invariance and depth 1..128; the scratch ceiling of 261,740 B and the
concurrent silent-corruption failure mode.

That list is the honest measure of the row: **the semantics are largely known, on the wrong
target, and mostly not emittable.**

---

## Boundaries — out of scope, not gaps

Recorded in the same spirit as EXP-0134's compression-codec and SFU-04 entries. These are
not work items.

| Question | Why it is a boundary | What the driver does instead |
|---|---|---|
| What Apple's own BG / EOT / partial-BG / partial-EOT programs contain | They are Apple-authored precompiled shaders; `CLAUDE.md` forbids inspecting or committing them. EXP-0108 searched for a program *record* at the data boundary — lawful DATA-TRACE — and found none across 40 cases and 6 gated runs; it must not and did not read any Apple program bytes. | Construct it. EXP-0130 shows the tilebuffer-read/ALU/attachment-write core built from our own MSL is behaviourally exact on 4/4 boundary cases. What remains open is the `usc`/`rsrc_spec` registration, which is P0.4/P0.5, not ABI. |
| The scratch / helper-program `binary` / `cfg` / `data` field values | A **host-observability** boundary that behaves like a clean-room one. Three independent lawful methods (EXP-0041, EXP-0107, EXP-0125) reach the same negative; EXP-0125's conclusion is that the mechanism "is not observable from userspace's own IOKit resource-map boundary on macOS". Going further means reading Apple's kernel or firmware code, which is forbidden outright. | EXP-0125: construct the helper program and scratch-pool layout "from first principles against the hardware's actual behavior … not decoded from a macOS capture". Until then EXP-0041's fallback stands: reject or avoid shaders and preambles requiring scratch. Guessing helper values, or declaring the fields kernel-owned, would not satisfy the unchanged UAPI. |
| Whether a second interpolation / derivative / blend mode exists that Metal never emits | EXP-0111 FS-05 states it exactly: "no MSL-level probe can distinguish 'the hardware has only one mode' from 'the hardware has a second mode Metal simply never emits' — there is no compiler-reachable starting point to perturb", and a blind bit sweep "would be closer to random fault-hunting than a falsifiable test". | A bounded `UNKNOWN`. Extrapolate-and-test still applies wherever a *motivated* hypothesis exists — EXP-0147 found matrix multiply-subtract exactly that way — but it needs a hypothesis. The inert-field sweeps (EXP-0163, EXP-0172) are the partial answer: they convert "the compiler always emits this value" into a measured don't-care envelope. |
| Apple's inlining heuristic — why a fragment epilog inlines while a vertex fetch helper stays out of line | EXP-0137 declared it out of scope in its own pre-registration: "it is not a hardware fact and a driver's own backend controls its own out-of-lining unconditionally regardless of what Apple's compiler happens to choose." Answering it would mean studying Apple's compiler. | Nothing. The driver picks its own out-of-lining policy. |
| Whether the fused `store_block_agx`-class EOT eviction op exists on Apple9 | EXP-0130 reached it as "NOT REACHED / UNKNOWN" — the byte value it could compare against is Mesa's **M1/M2-class** encoding, read as PUBLIC cross-generation context only and explicitly not asserted as an Apple9 fact. There is no Metal API surface known to provoke it. | Use the constructed `tile_read` + ALU + `frag_color_store` path, which is HW-validated. |

## Non-evidence — must not be cited under this row

| Experiment | Status |
|---|---|
| `EXP-0050-fragment-output-abi` | **QUARANTINED.** Its runner materialized bytes outside its own allowlist while attesting it read only the selected fragment `_agc.main`. The name is the closest in the tree to P0.8's fragment-output sub-area; none of its content may be cited. |
| `EXP-0071-m4-vertex-fragment-abi-contract` | **QUARANTINED pre-GPU.** Underspecified frozen matrix; no capture was ever run. |
| `EXP-0057-m4-scratch-pressure-envelope` | **QUARANTINED.** Read a compiled pipeline container beyond its registered metadata-only boundary. Its own quarantine redirects to EXP-0041. |
| `EXP-0118-a18-pro-partial-render-workload` | **Not usable.** RESULTS.md is 5 lines with no target line, no evidence label, no run count, no pre-registration, no capture contract, no manifest and no committed raw; its only G17P attribution is in README.md, and it was committed as "append-only process history". It is the only file in the tree claiming a G17P partial-render result and must not be read as one. |
