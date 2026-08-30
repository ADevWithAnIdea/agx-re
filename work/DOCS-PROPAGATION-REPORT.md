# `docs/` propagation report — closure rule 4

**Author:** desk agent. **Date:** 2026-08-29. **No GPU work, no device touched, no SSH.**
**Scope:** propagate committed experiment facts from `PROVENANCE.md` / experiment `RESULTS.md`
into normative `docs/`, so that closure **rule 4** ("normative `docs/` carry exact fields, ranges,
fallbacks and target status") is satisfiable per P0/P1 row.

**Nothing was committed.** `PROVENANCE.md`, `docs/P0-P1-CLOSURE.md`, `CLAUDE.md`, `CODEX.md`,
`APPLE9_RE_IMPLEMENTATION_GAPS.md` and `tools/` were **not** touched.

> **Note on the working tree:** `docs/isa/encoding-tables.md`, `docs/isa/agx3.xml` and
> `tools/agx-isa/*` were **already modified** in the tree when this task started (they are
> generated from `db.json` by a sibling workstream). A new untracked `docs/compiler-readiness.md`
> also appeared mid-task from a concurrent agent. **This agent wrote none of those.** The ten
> files listed under "Files changed" are the only ones this agent edited.
>
> **Consistency check against that sibling file:** `docs/compiler-readiness.md` states a hard
> negative — none of the `reg_move_*` descriptors is a general GPR→GPR move. That does **not**
> conflict with this pass's report that `reg_move_*`/`uniform_mov` became *emittable* under
> `DOC-02` (a per-field predicate). To make the distinction impossible to misread, two explicit
> caveats were added to `docs/isa/README.md` — one in the Emittability-status section and one in
> the MOV section — each pointing at `register-move-and-liveness.md` §1.0 and saying plainly that
> this does **not** close `nir_op_mov`.

---

## 0. Headline

| | |
|---|---|
| **Distinct facts propagated into `docs/`** | **131** (plus 2 anti-misreading caveats) |
| **Files edited** | **10** |
| Net lines added to `docs/` by this agent | ~1 620 |
| **P0/P1 rows whose rule-4 material is now present in normative `docs/`** | **13 of 16** |
| P0/P1 rows still failing rule 4 after this pass | **3** (P0.1, P0.2, P0.3 — see §4) |
| Retractions/corrections preserved in place | **8** |
| PROVENANCE rows that could NOT be placed | **11** (see §5) |

**Rule 4 is a documentation predicate, not a closure verdict.** This report says the *material*
is now in `docs/`; whether a row is `CLOSED` remains the orchestrator's judgement under all six
rules.

### Files changed

| file | what landed |
|---|---|
| `docs/isa/README.md` | Emittability status; `falu2` source classes + inline minifloat; MOV/select/uniform-move; memory-family operand rules; matrix `A·B − C`; barycentrics; `tile_read`; `pixel_order`; `vtx_*`/`n3_sample_read`; fences; IALU + `ibfe`; 64-bit ADD; pack/unpack/convert; NIR option contract |
| `docs/isa/memory-model.md` | new **§2A** (operand/destination encoding rules); new **§6A** (zero-fill bounds, `2^43` wrap, VM/allocator conventions); §0.1 target rule; §8 MEM-05/13/14/15..18/20/21/22 answered in place; §1 + §9 updated |
| `docs/isa/register-move-and-liveness.md` | new **§2.8** (A18↔M4 lifetime contradiction resolved); target-status header |
| `docs/capability-matrix.md` | 5 new native rows; 4 new emulate rows; GS/XFB + aniso resolved out of §4; new **§6 silent-failure envelope** (12 rows); counts + target-discipline note |
| `docs/hypotheses.md` | #4, #5, #24 updated with new evidence; **#26–#35 added**; backlog struck through where answered; target-label note |
| `docs/evidence-classification.md` | `EXP-0119` contradiction correction; current target rule; live coverage numbers in §4 |
| `docs/descriptors/README.md` | aniso ≥128×; address-mode alias set; border-code 3; swizzle 6/7 fault |
| `docs/descriptors/format-table.md` | aniso row; §4a alias resolution; §4a-bis LOD formula; §4c border code 3; **new §2e conversion-rounding rules**; §8 untested list resolved |
| `docs/pipeline/README.md` | depth/stencil `k`-slot reuse; slice/level silent failures; BG/EOT program construction; **new rasterization-rules + finite-limit section** |
| `docs/cmdstream/README.md` | mesh ceilings; hand-built CDM link + boundary map; relocation-by-structure-kind; varying/UVS capacity + pre-raster boundaries |

---

## 1. The six dispatched priorities

### P1 — Emittability status → `docs/isa/README.md` "Emittability status"

| # | fact | source |
|---|---|---|
| 1 | 171 instructions in the DB; **38 emittable**, 133 decodable-not-yet-emittable | `tools/agx-isa/validation.json` `coverage` (`generated: 2026-08-28`, `db_sha256 eaca7256…`) |
| 2 | 1036 fields; **443 = 42.8 % at emitter grade** (`hardware-run` 349 + `isolated-byte-diff` 94) | same |
| 3 | Full per-label breakdown (`corpus-correlation` 182, `tokenization-only` 203, `single-template-inference` 13, `api-accept-reject` 0, `host-private` 0, `untested` 195) | same |
| 4 | The 38 emittable mnemonics, listed | same |
| 5 | What each of the eight `DOC-02` labels licenses a **compiler back-end** to do (emit arbitrary in range / emit at tested points only / do not synthesize / not yours to fill / a gap) | `docs/evidence-classification.md` §2, §5 |
| 6 | The `emittable` rule restated: a ✅ heading means *the claim* was HW-validated, **not** that every field can be synthesized | `evidence-classification.md` (DOC-02 verbatim rule) |
| 7 | Five measured silent-zero exemplars showing why the distinction bites here | EXP-0141, 0147, 0140, 0138 |
| 8 | Target status: labels are G16G; closure now measured against full G17P; G17P revalidation under way (EXP-0153); no silent relabel | `CODEX.md` target discipline |

Also mirrored into `docs/evidence-classification.md` §4 so the standard document itself carries
the live numbers.

### P2 — `falu2` source-class model + inline float immediate (EXP-0138)

| # | fact |
|---|---|
| 9 | `mod_lo` is an **operand-source-class** field, not a modifier; `hardware-run` dense over all 8 values, identical outcome map in 3 runs (98/98 each, 294/294) |
| 10 | **bit 0** selects `srcA`'s class: 0 = GPR; 1 = a second class returning `0.0` at every index tested — **not** the uniform file (`srcA_reg = 6`, where the uniform file holds 101.0, still gave 0.0) |
| 11 | **bits[2:1]** select `srcB`'s class: 0 = GPR, 1 = non-GPR file, 2/3 read `0.0`, **bit 2 dominates bit 1** (`mod_lo = 6` reads 0.0 where `mod_lo = 2` reads 101.0) |
| 12 | The pre-registered hypothesis was **REFUTED in both halves**; the refuter fired as designed (`mod_lo = 2`, `srcB_reg = 2` → 5.0, not the GPR answer 8.0) |
| 13 | In class 1, `srcB_reg` **0..63** = uniform index (bound `float4` at 6..9); **64..127 = inline 8-bit minifloat** |
| 14 | `k = v − 64`, `e = k>>3`, `m = k&7`; `m·2^-5` if `e == 0` else `(8+m)·2^(e−6)` |
| 15 | Ten HW-confirmed points: k = 0, 2, 3, 31, 32, 48, 56, 61, 62, 63 → 0, 0.0625, 0.09375, 1.875, 2.0, 8.0, 16.0, 26.0, 28.0, 30.0 |
| 16 | **Safety:** indices 126/127 do **not** fault in this mode (they are 28.0/30.0), unlike GPR mode where EXP-0112 recorded a fault — the register model does not transfer across classes |
| 17 | `srcB_reg` **bit 6 is live in class 1**, which is why EXP-0099/0112 correctly saw it inert in GPR mode |
| 18 | Carrier-specific caveat carried over verbatim: uniform index 10 ≈ 1.0 is the carrier's own literal (`CARRIER_SPECIFIC`) |
| 19 | Editorial cross-reference (arithmetic identity, flagged as such): the same magnitude set `{0, 1/32 … 30.0}` as the bit-39 packed immediate |
| 20 | `copysign`: byte+3 inert over all 256; **byte+1 is a live operand field**, byte+2 a 256/256 don't-care (falsifier fired: 240 silent zeros, 8× −5.0, 8× +5.0) |
| 21 | `half_alu`: byte+1 is the **first source descriptor**, not the destination; descriptor bit 7 inert (`0x82`≡`0x02`) |
| 22 | `half_alu_ext8`: `dst`, `opflags`, `b7_lo`, `b7_mid` dense `hardware-run` |
| 23 | ⛔ `fspecial.src` 192..255 fault or **hang** (192/193/194 hung 3× each under a 12 s watchdog); only 2 and 3 give correct `rsqrt(4)`; **never set byte+3 bit 7**; arm stopped, `fspecial` stays PARTIAL |
| 24 | `falu_srcmod12b.srcB_neg`/`.mod_lo` inert though same-named `falu2` fields are live — do not carry one operand model across float-ALU families |
| 25 | `falu_srcmod12b` and `half_alu_fma12` remain `emit_unsafe` regardless of labels |
| 26 | `falu3`/`falu3_ext` field **names** in `db.json` are misleading (byte0 hi nibble = destination; byte+1/+3/+5 = sources; byte+4 = length-selector control) |
| 27 | Scope limit: 7-bit register fields swept 0..15 dense + 17 boundary values, **not** 0..127 dense; wide `ext` tails are `isolated-byte-diff` only |

### P3 — Barycentrics (EXP-0137) → `docs/isa/README.md`

| # | fact |
|---|---|
| 28 | The trigger is the fragment shader **reading `[[position]]`** — not output count, extra varying, or harness |
| 29 | Non-position variants → `(0.243489, 0.134766, 0.621745)`; position-touching → `(0.486979, 0.269532, 0.243489)` |
| 30 | `posread_noout` only *stores* position to a `device` buffer and is still broken |
| 31 | Ratio exactly **2.0**: broken values are **unnormalized perspective numerators**, third = `1 − b0 − b1`, normalize-by-sum absent |
| 32 | Broken form has **2 `iter` and ZERO `fspecial`** |
| 33 | Discriminating control `count3_vary` (`iter = 6`, `fspecial = 1`) is still correct — "an rcp exists" is **not** the condition |
| 34 | ⛔ `[[barycentric_coord, center_perspective / center_no_perspective]]` **compiles but is a complete no-op** — identical disassembly, both `iter = 2` / `fspecial = 0`. No MSL escape hatch |
| 35 | Convention: `x/y/z` follow vertex emission order (`vid % 3 = 0,1,2`); perspective-correct is the intended semantic |
| 36 | P0.8 corollary (refines EXP-0109): a memory-touching vertex helper and a 2-call-site compute helper **are** kept out-of-line as named Mach-O local symbols reached by real `call`/`frame_marker`/`pop_reconverge`, but a single-call-site fragment epilog **inlines despite `noinline`** |

### P4 — Four capabilities Metal never emits → `capability-matrix.md` §1, `hypotheses.md`, `isa/README.md`

| # | fact |
|---|---|
| 37 | **Native single-instruction 64-bit integer ADD** — `ulong` subtract compiles to one arithmetic op (`iadd2`, `1f 01 56 00 02 08 00 50 17 05`); byte0 bit 7 `0x1f`→`0x9f` gives a 64-bit ADD with **carry produced inside the instruction** (EXP-0146) |
| 38 | Oracle rows: `0x8000…0+0x8000…0=0`; `0x7FFF…F+1=0x8000…0`; `0xFFFFFFFF00000000+0x00000000FFFFFFFF=0xFFFF…F`; `0xFFFF…E+3=1`; 5/5 serial reps, both gated runs |
| 39 | Apple's compiler emits a **5-instruction chain** instead |
| 40 | LIMITATION recorded: bit-flipped from the compiler's own subtract, **not synthesized from scratch**; operand-widening byte located (byte+7 `0x50` vs `0xA8`) but not isolated |
| 41 | **Anisotropy works natively to at least 128×; Metal's 16× cap is pure software** (EXP-0136) |
| 42 | Threshold-exact: crisp iff `patched_aniso ≥ ratio` — ratio 16 blurs 1/2/4/8, crisp from 16; ratio 64 blurs 16/32; ratio 128 blurs 16/32/64, crisp at 128 |
| 43 | Descriptor nibble = `log2(aniso)`; patched codes 5/6/7 read back intact |
| 44 | **Matrix unit computes `A·B − C`** — `b11hi` bits 0–1 are per-tile-row accumulator sign controls: 0 → `+C`/`+C`, 1 → `−C` rows 0–3, 2 → `−C` all rows, 3 → `−C` rows 4–7 (EXP-0147) |
| 45 | Correct `A·B + C` requires **`(b11hi & 3) == 0`** (32 of 128 values); bits 2–6 don't-care |
| 46 | `matrix_mac.dst_desc`: correct iff **bit6 = 1, bit7 = 0**; 128 of 256 values **silently zero**, 64 wrong |
| 47 | **`uniform_mov.usrc ≥ 0x80` materialises immediate `usrc & 0x7F`** into the destination GPR — 128/128 matched the oracle (EXP-0140) |
| 48 | Below `0x80` the field is a **pair-quantised** uniform index (`usrc` and `usrc^1` read the same word; consecutive uniforms step by 4); 8/8 bound constants exact; unallocated indices **silently zero** |
| 49 | Gives an emitter **two** independent 7-bit constant-materialisation paths (`mov_imm` and this) |
| 50 | Primitive restart upgraded to HW-VALIDATED: triggers at exactly and only the all-ones sentinel; adjacent values are literal OOB indices **with no fault** (EXP-0136) |
| 51 | Border colours: the 4th 2-bit code **aliases to preset 0** from all three creation contexts — no hidden 4th preset (EXP-0136) |
| 52 | Address-mode codes 4/6/7 are **exact deterministic aliases** (4→clampToEdge, 6/7→clampToBorder); code 5 (mirrorClampToEdge) genuinely distinct — the signature method has demonstrated power |
| 53 | ⛔ Texture **swizzle codes 6/7 hard-fault** the command buffer (GPU-hang class, contained) — never emit; codes 0–5 now HW-validated by direct construction |
| 54 | ⛔ **Native geometry shaders / stream output DO NOT EXIST** — `rasterizationEnabled = NO` runs the vertex stage (atomic side effect) on the **same VDM/tiler path** with the fragment stage elided; GS + XFB permanently emulated |
| 55 | `device_load`/`device_store` `reserved7`/`reserved13` genuinely inert |

### P5 — Silent-failure facts a driver must self-enforce → `capability-matrix.md` §6 (+ topical homes)

12-row consolidated table, each with its own topical section elsewhere:

| # | fact | topical home |
|---|---|---|
| 56 | **Mesh grid amplification tops out at exactly 65,536**; 65536/65537/65600/1048576 cover **0 px** with no error and `CMDBUF_STATUS` still 4, while 65535 covers 917 px. Metal reflects `meshGridMax = 1048576` (16× higher). Reproduced via the indirect-draw path | `cmdstream/README.md` |
| 57 | Object→mesh payload ceiling **exactly 16,384 B**, enforced at pipeline creation; `payloadMemoryLength` accepts values **smaller** than the struct with no validation | `cmdstream/README.md` |
| 58 | **`tile_read` byte+6 bit 0 is a read-enable** — 128 odd values correct, **128 even values silent zero**; bits 1–7 don't-care; identical on `tile_read_mrt` | `isa/README.md` |
| 59 | `tile_read.rt_index` correct only at `0x00/0x01/0x80/0x81`; every other index **silently zero** with one attachment bound | `isa/README.md` |
| 60 | `tile_read.dst` OK only at `0x00/0x01/0xC0/0xC1`; `0xF6–0xFF` fault; `b7` OK only at `0xAE/0xAF/0xEE/0xEF` with **85 of 256 nondeterministic**; `tail` bytes 1/3 silent-zero | `isa/README.md` |
| 61 | `tile_read_mrt.fmt` correct only at `0x2E/2F/6E/6F/AE/AF/EE/EF` — bits 0,6,7 don't-care, bits 1–5 are the format selector | `isa/README.md` |
| 62 | **In a BG/EOT program these produce a BLACK TILE, not a failure** | `isa/README.md`, `pipeline/README.md` |
| 63 | **Invalid attachment `slice` (= arrayLength) DESTRUCTIVELY ZEROES slice 0** — its canary `a0a0a0a0` overwritten with 0 though slice 0 was never the target; slices 1–3 untouched. Not a modular wraparound | `pipeline/README.md` |
| 64 | **Invalid `level` (= mipCount) is a pure no-op** — all levels keep their canary. Two opposite silent behaviours at adjacent boundaries; a driver must validate both itself | `pipeline/README.md` |
| 65 | Array slice and mip level are **NOT encoded** in the per-attachment `k`-record (byte-identical across slices 0/1/3 and levels 0/2); `mipCount > 1` sets word1 bit 26 only | `pipeline/README.md` |
| 66 | **`unorm16` ties round DOWN — the opposite of `unorm8`'s round-UP**: `1.5/65535`→`0x0001`, `2.5/65535`→`0x0002`, control `5.9/65535`→`0x0006` excludes truncation | `descriptors/format-table.md` §2e |
| 67 | `unorm8`'s round-half-up pinned at an **even-floor** tie (`2.5/255`→`0x03`), which round-half-even would have kept at 2 | §2e |
| 68 | `snorm8`/`snorm16` use the **symmetric** scale; `−1.0` → `0x81` (−127), not `0x80` | §2e |
| 69 | Reduced-float **texture stores truncate** (fp16 `0x37FF`, RG11B10 `0x6FDBFB7F` bit-exact against an independent pre-capture reconstruction, RGB9E5 `0x77FFFFFF` with **no overflow renormalization**); a positive-direction control excludes round-away-from-zero | §2e |
| 70 | The **ALU pack path rounds differently**: `pack_float_to_unorm2x16` ties **round-to-nearest-even**, refuting the "reuse the storage rule" model; `cvt_f2h` matches IEEE RNE including the 65520.0 overflow tie | §2e |
| 71 | **`ibfe.offset` is LITERAL** (32..63 shift the field out; literal 64/64 vs mod-32 32/64) — **the hardware does NOT implement NIR's offset masking**, so a back-end must mask in software | `isa/README.md` |
| 72 | **`ibfe.width` IS mod-32** (64/64 vs 37/64), so `width = 32` ≡ `width = 0`; this refuted EXP-0139's own pre-registration | `isa/README.md` |
| 73 | Format render/blend/MSAA/resolve/depth-stencil eligibility is enforced by **unconditional `abort()`** — no safe runtime probe, a static allowlist is required; `Depth24Unorm_Stencil8`/`X24_Stencil8` header-available but rejected | `capability-matrix.md` §6 |
| 74 | Metal enforces sample positions in `[0,1)` with a **process-terminating assertion**, not a catchable error | §6 |
| 75 | Attachment count / texture dims / array layers / mip levels are enforced by **uncatchable `abort()`** — a driver cannot probe them, it must carry static limits | `pipeline/README.md` |

### P6 — Memory / operand model → `docs/isa/memory-model.md` §2A

| # | fact |
|---|---|
| 76 | **`dst_lo`/`dst_ext9` carry NO register information** (EXP-0141) |
| 77 | To land a load in `R`: **`extmode = 2·R` (bit 0 don't-care), `dst_lo = 1` exactly, `dst_ext9` bit 0 = 1** — three constrained bits of nine |
| 78 | `extmode` **0..127 all match, 128..255 all fail** → **`R = 0..63` only; `R ≥ 64` silently zeroes** |
| 79 | Identical at r3/r7/r20/r33 and under all 21 working `ld_format` codes |
| 80 | Refuter partially fired: `dst_ext9`'s upper don't-cares are `ld_format`-dependent (free for 16 codes, tighter for 3/7/9/13, 39); `dst_ext9 = 1` valid under all 21 |
| 81 | Safe fallback stated: allocate load destinations only in `r0..r63` |
| 82 | **The atomic RMW operand register is ENCODED**: `index = (byte+5 >> 7) \| ((byte+6 & 0x3F) << 1)` (`db.json` said "implicit"; DOC-02 ranked it MISSING) |
| 83 | Proven at all four constructible indices (`0→a[0]=7`, `1→1007`, `2→2007`, `3→3007`), byte-identical in both runs, on a **uniform-address** carrier the per-lane reading cannot explain |
| 84 | The redirected register is **RELEASED** (later reader gets 0) — the EXP-0086/0089/0099 contract |
| 85 | Scope limit: the **address** role of byte+5/+6 not excluded for the per-lane form; the **data** role proven for the uniform form. Applies to both `atomic_rmw` and `atomic_mem` |
| 86 | **`device_store` byte+2 bit 1 is a DATA-SOURCE SELECTOR** — inert for ALU-computed data (256/256, EXP-0119's configuration), **required** for a forwarded load; store-side `extmode` = `2*R` or `2*R\|0xC0` |
| 87 | Five `rsv*` bytes in `atomic_mem`/`atomic_tg` are **live and heavily constrained**, not padding |
| 88 | Not moved, with reasons: `mem_fence`×3 + `dev_scoreboard_fence.scope_flag` (no ordering observable), `mem_fence8`×2 (no dispatchable carrier), `atomic_tg.op_desc` (hang budget) |
| 89 | ⚠️ Live G17P↔G16G divergence: `tg_addr_compute` works on M4 **only** with byte0 `0x1c`; EXP-M4-14's A18 `0xfc` does **not** reproduce |
| 90 | Testbed hazards: `STATUS OK` with nothing executed (zero-initialised output, indistinguishable from a wrong field value without a sentinel); reusing one splice-archive path gives **~8 % phantom `CMDBUF_ERROR`** (28/360 vs 0/360) |
| 91 | **`unpack_convert` byte+2 reproduces iff `(byte & 0x03) != 0`**; bits 2–7 inert, exact over 256 — reconciling EXP-0089 (`0x54 & 3 == 0`, breaks) with EXP-0119 (single-bit flips inert) as one two-bit OR-enable seen through a one-bit window |
| 92 | `unpack_convert` byte map: +3 **destination**, +4 fully inert, +5 **source** (`reg<<3`), +1/+6 descriptors, +7 **format + a source-register bit** |
| 93 | **`reg_sel` is not a register selector**: byte+7 bits 6:5 select the format (`0x0A/8A` unorm8, `0x2A/AA` snorm16, `0x4A/CA` unorm16, `0x6A/EA` unorm8), bit 7 don't-care, **bit 3 changes which register is read** — explaining `…1cca` vs `…1caa` as a *format* difference `db.json` attributes to a register |
| 94 | **`pack_convert` byte+3 is the DESTINATION** (`db.json` calls it `src`), `reg << 1`, bit 0 don't-care — six distinct observed registers; identical map to `cvt_i2f` byte+3 |
| 95 | `pack_convert` byte+5/+6 are the **lane-0 / lane-1 source registers** (`reg<<2` / `reg<<3`) |
| 96 | `pack_convert` byte+9 is a **FORMAT SELECTOR** with a decoded code table including a **third, never-compiler-emitted 8-bit unorm-lane pack** (`0xC2/C6/CA/CE`) |
| 97 | `cvt_*` cluster shares one byte layout; `cvt_f2h` and `cvt_f2h_dst` are the **same encoding**; `field = register << 1` with bit 0 free |

---

## 2. Additional facts propagated beyond the six priorities

These were rule-4 failures found while working: PROVENANCE rows whose "Where in docs" column
names a `docs/` file that did not contain them.

| # | fact | destination |
|---|---|---|
| 98–110 | **EXP-0140 MOV/CF family**: 11 of 23 instructions emittable; `get_sr` `form` inert / `dp_width` `(v&0xD3)==0x10` (32 of 256 **fault**, 216 silently wrong) / `dp_marker` `(v&0xE6)==0x06`; `sel.body` is **three byte-fields** (byte+3 = predicate-FALSE operand, bit 7 set ⇒ the byte **is** the immediate, 510/512 oracle, statically cross-checked against five authored `?:` variants; byte+2 four 64-value classes incl. 127 faults; byte+1 only 4 inert values); `psel` `sel` 512/512, `mode` `(v&0xC0)==0` with 127 faults, `flag` `(v&0x12)==0x02`; `reg_move` byte+2 `(v&0xCB)==0x01`, byte+3 `(v&0x0E)==0x08`; CF bytes measured inert (`if_push.scope`, `if_push_pred.scope`, `jump.link`, `jump.branch_ctrl`, `pop_reconverge.scope`); `pop_reconverge.scope_kind = 0` fatal; `ret.linkmode` only `(v&7)==4`; **`jump_cond` deliberately `untested`** (carrier has no discriminating power — trip count 0 on the only true-guard lane); EXP-0115's branch reach does **not** transfer to `jump_cond`; lengthening a CF carrier is **not semantically neutral**; `db.json` defect — the six `reg_move`/`uniform_mov` descriptors are **one** instruction; `mov_imm imm7 == 12` does not tokenize (decoder defect, hardware untested) | `isa/README.md` |
| 111–116 | **EXP-0139 IALU**: 39 `hardware-run` + 34 `isolated-byte-diff` of 137; `ibitcount`/`iunary` emittable; `ibitcount.tail` only bit 2 load-bearing on a **fully synthesized** popcount; `iunary.operand` is five one-byte sub-fields (`DEF-0139-1`); `isel_reg8` **constructed** (byte+2 `0x0f`→`0x25`) executes; `iminmax` — EXP-0113's nondeterminism did **not** reproduce (858 cases ×4); fmax/fmin diverge from IEEE only on NaN/denormals; concurrency: 44 % of gated-run faults did not reproduce across 129,839 dispatches, **692 legal values would have been mislabelled `fault`** without FIELD-SWEEP-PROTOCOL §7, only 3 of 29,685 genuinely nondeterministic | `isa/README.md` |
| 117–120 | **EXP-0146 extras**: `ilogic` reaches **all 16** boolean functions via `(op_base, lut_a&3, lut_b&0x0f)` (refining EXP-0102's "10 of 16", which described MSL source); `carry_gen` is `p[dst] = r[byte+1] <u r[byte+3]`; `iadd2 dst ≥ 96` faults; negatives `int_alu_ehi` 0/7 and `sr_read_wide` 0/6 (**a testbed gap, not a hardware fact**) | `isa/README.md` |
| 121 | **EXP-0147 `pixel_order`**: full accepted value sets per member with the acquire/release asymmetry (acquire corruption loses 7 of 8 serialised RMWs; release corruption loses none), plus the `db.json` defect where `flags` and a match constant claim the same bits | `isa/README.md` |
| 122 | **EXP-0147 `vtx_out_pos` / `vtx_coord_xform` / `n3_sample_read`** measured inertness with litmus-power proof, `(mode & 0xF3) ∈ {0x22,0xE2}`, 240/256 no-draw, 19 genuine hangs on `sel`, and the single-output-slot scope limit | `isa/README.md` |
| 123 | **EXP-0147 fences**: all six fields `untested` because the sensitivity control **passed when registered to fail**; `compute_fence_scoped.mask` breaks at exactly 10 of 256 values — the highest-value follow-up | `isa/README.md` |
| 124 | **EXP-0121 NIR option contract** — OPT-01/03/04/05/06/07/08/10/11 with their compiler consequences, including `has_atomic_load_store` **must be false** (asymmetric: OPT-10 NO, OPT-11 YES) | `isa/README.md` |
| 125 | **EXP-0129** — the A18↔M4 lifetime contradiction is **operand provenance**, not a device difference; `ibitcount`'s release control is `srcdesc` bit 4, **not** `cache`/bit 17; one release concept routed differently per family; bits 15/31 re-confirmed inert on four new axes; fragment stage not reached; uniform-register operand class untested project-wide | `isa/register-move-and-liveness.md` §2.8 |
| 126 | **EXP-0122** — zero-fill is **not page-wide** (live non-zero data at exactly 16384 B ±256 B); **address wrap period exactly `2^43`** with 12/12 discriminating cases incl. two period-excluders; 256 B uniform alignment; `maxBufferLength` an exact off-by-one-tested ceiling; deterministic bump allocator; `vm_start` still `UNKNOWN` | `isa/memory-model.md` §6A |
| 127 | **EXP-0083/0084/0085** — MEM-13/14 (interlock incl. texture-read and atomic sources), MEM-15..17 (**selector effectively 7-bit; 128..255 mirror 0..127**; selector is `byte+5` not `byte+4`; out-of-range is silently wrong), MEM-20/21/22 (dynamic 64-bit addressing; 32 lanes → 32 distinct buffers; bindless scales 2–8× past the direct-slot ceiling) — answered in place in §8, with EXP-0085's run-id-reuse auditability caveat recorded | `isa/memory-model.md` §8 |
| 128 | **EXP-0116** — a **hand-built CDM link followed by real silicon** plus the 17-case boundary map: tag must be `0x20`; `+1/+2` OK but `+4/+8` fault; ⚠️ **`2^44`/`2^46` silently ALIAS** rather than fault; the encoding ceiling **HANGS**; cross-submission targets fault; **"faulted" does not imply no earlier work happened** | `cmdstream/README.md` |
| 129 | **EXP-0110** — relocation differs by structure kind (VDM/FF invariant, CDM heap-relative); container metadata is archive bookkeeping | `cmdstream/README.md` |
| 130 | **EXP-0130** — the BG/EOT **program** is constructible and exact on 4/4 oracle cases with a paired falsifier; `f_eot_evict` is **elided entirely by the compiler**; the UAPI side is a bounded `PUBLIC`-only negative | `pipeline/README.md` |
| 131 | **EXP-0123 + EXP-0097 + EXP-0094** — line/point rasterization rules, depth clip vs clamp (closed interval), the clean negatives (wide lines, polygon-point, conservative raster, provoking vertex), A2C reaching the occlusion counter, the 14-row finite-limit table, the **124-scalar-component** varying budget with its two distinct failure modes, the clip-distance ceiling of 8 as an independent budget, the pre-raster `−Inf` full-fill asymmetry and the 511×511 point clamp, and the exact `effective_LOD` formula with the bias/gradient NaN asymmetry | `pipeline/README.md`, `cmdstream/README.md`, `descriptors/format-table.md` |

---

## 3. Retractions and corrections preserved (rule 4 of the dispatch)

| # | retraction | where it is now stated |
|---|---|---|
| R1 | **EXP-0140 refutes EXP-0128's `mov_imm` "silent zero."** The buffer was zero-initialised; with `imm_top = 1` the instruction **does not write the destination at all**, and unpadded it **consumes the following 2-byte instruction**. Bit 7 selects a different, longer instruction. The 7-bit *conclusion* stands; the *mechanism* does not | `isa/README.md` (MOV section) |
| R2 | **EXP-0139: `r(R mod 64)` does NOT transfer to `iadd2.dst`** (at dst = 140/141, reg 70, the sum never appeared in r6); fault boundary `reg ≥ 96` | `isa/README.md`; `memory-model.md` §2A.1 retraction table |
| R3 | **EXP-0148 deleted `falu2_ext8b`** — it was never an instruction (already present in `docs/isa/README.md` from a prior pass; left intact and not contradicted by the new emittability section) | `isa/README.md` (length-rule block) |
| R4 | **EXP-0101 retracted EXP-M4-13's `dst = dst_lo \| (dst_ext9<<2)` formula**, and EXP-0141 in turn **superseded** EXP-0101's copy-verbatim instruction | `memory-model.md` §2A.1 (3-row chain table) |
| R5 | **EXP-0144 withdrew its own 44-of-51 claim down to 33**, with the reason (contaminated captures) and the honest decomposition (11 fields are *coverage*, not contradiction; only 92 of 13,783 repeated measurements — 0.67 % — were overturned) | `isa/README.md` (pack section) |
| R6 | **EXP-0144 withdrew `cvt_bf16`'s rounding claim and `packed_half2_hi` entirely** | `isa/README.md`; `format-table.md` §2e |
| R7 | **EXP-0129 resolved the EXP-0119 A18↔M4 contradiction** that `docs/evidence-classification.md` §3 still cited as unresolved — corrected in place, with the target rule re-anchored on the *live* `tg_addr_compute` divergence instead | `evidence-classification.md` §3; `register-move-and-liveness.md` §2.8 |
| R8 | **EXP-0138 refuted its own pre-registered `H-MODLO`; EXP-0139 refuted its own `width` pre-registration; EXP-0140 disclosed a falsifier that matched when registered not to** — all three recorded rather than dropped | `isa/README.md` |

Also corrected in place (rule 5): the anisotropy ">16× untested" note in two files; the sampler
address-mode "codes 4/6/7 untested" note; the border "code 3 untested" note; the swizzle-code
footnote; `memory-model.md` §8's zero-fill "shape unknown" bullet and eight MEM-* `UNKNOWN` rows;
`capability-matrix.md` §4's aniso and GS/XFB "unknown" rows.

---

## 4. Rule-4 status per P0/P1 row (documentation predicate only)

| row | rule-4 material in normative `docs/`? | where |
|---|---|---|
| P0.1 helper/scratch protocol | **partial** — landed earlier at commit `97162755` (`kernel-interface.md` §9). **Not touched by this pass** | `kernel-interface.md` §9 |
| P0.2 shader selection / code window | **NO** — EXP-0127's selector findings are in `PROVENANCE.md` and `cmdstream/README.md`'s open-items prose only, not as a field/range/fallback spec. **Still a rule-4 gap** | — |
| P0.3 UAPI field values | **partial** — `isp_merge_upper`, `isp_bgobjvals`, `ppp_multisamplectl` landed at `97162755`. The remaining 58 PARTIAL leaves are not itemised in `docs/`. **Still a rule-4 gap** | `kernel-interface.md` §6.3/§6.4 |
| P0.4 BG/EOT programs | **YES** (new) | `pipeline/README.md`; `isa/README.md` `tile_read` |
| P0.5 command-stream generation | **YES** (new) | `cmdstream/README.md` CDM link + relocation |
| P0.6 compiler-ready ISA | **YES** (new, extensive) | `isa/README.md` emittability + 8 new sections |
| P0.7 shader container | **partial→YES for the consumer question**; synthesis-from-scratch remains open and is stated as such | `cmdstream/README.md` |
| P0.8 stage ABI / prolog-epilog | **YES** (new) | `isa/README.md` barycentrics section |
| P1.1 PBE / attachment structures | **YES** (new) | `pipeline/README.md` |
| P1.2 per-format capability + conversion | **YES** (new) | `descriptors/format-table.md` §2e + §8 |
| P1.3 samplers / texture ISA | **YES** (new) | `descriptors/*`, `format-table.md` §4/§4a/§4a-bis/§4c |
| P1.4 fences / raster-order groups | **YES** (new) | `isa/README.md` `pixel_order` + fences |
| P1.5 memory model / robustness | **YES** (new, extensive) | `memory-model.md` §2A, §6A, §8 |
| P1.6 userspace↔kernel handoff | **partial** — inherited from `97162755`; not extended here | `kernel-interface.md` |
| P1.7 relocatable command stream | **YES** (new) | `cmdstream/README.md` |
| P1.8 rasterization rules + limits | **YES** (new) | `pipeline/README.md`; `isa/README.md` NIR contract |

**13 of 16 rows now have their rule-4 material in normative `docs/`.** The three that do not
(P0.2, P0.3, P1.6) are all **kernel-interface / UAPI-side**, and two of them are *partially*
covered by the earlier `kernel-interface.md` work; closing them needs the per-leaf UAPI field
tables that only exist inside `EXP-0126`/`EXP-0127` today.

---

## 5. PROVENANCE facts that could NOT be placed

Eleven experiment IDs referenced in `PROVENANCE.md` still have **no** mention anywhere in
`docs/` prose. In every case the row's own "Where in docs" column points at a file this dispatch
forbids editing, or at a generated artifact.

| experiment | fact | why it could not be placed |
|---|---|---|
| **EXP-0040** | ISA objective-2 DB merge: 75 descriptors, round-trip PASS (275 vectors), census core 87.9 % | "Where in docs" = `isa/encoding-tables` — a **generated** file (from `db.json` + `validation.json`). Editing it by hand would be overwritten on the next regeneration, and `tools/` is off-limits to this dispatch. |
| **EXP-0046** | Codec audit metrics: 59/170 descriptors retain raw fields, 19 have synthesized field-vector cases, 92 lack a central fixed vector, 129 zero placeholders in the XML | The row itself says these are **structural audit metrics, not new hardware facts**, and its home is `P0-P1-CLOSURE.md`, which is off-limits. |
| **EXP-0060** | 1,440 `falu2i` six-byte round trips | Home is `AGX_RE_INFORMATION_GAPS` / `P0-P1-CLOSURE` (both off-limits). The row explicitly disclaims hardware execution, a general emitter, native semantics, and A18 behaviour — under DOC-02 it is `tokenization-only` and there is no `docs/` section for round-trip-only counts. |
| **EXP-0063** | Public sampler address-mode matrix; the frozen coordinates made nearest and linear identical, so **no filtering conclusion** | Home is the gaps file. The row states it establishes nothing about descriptor/ISA layout — there is no normative `docs/` claim to write. |
| **EXP-0066** | Public sampler-filter matrix: in the tested zero/edge/repeat modes, nearest reads green and linear reads the red/green blend | Same: home is the gaps file, and the row disclaims descriptor-layout and texture-ISA conclusions. `format-table.md` §4a already documents the modes themselves. |
| **EXP-0070** | Six exact typed round-trip words (RGBA8 `0080ff80`, BGRA8 `ff800080`, sRGB `0a0abc80`, R16 `0080`, RGBA16F `0080003cff7b5535`, R32Uint `efbeadde`) | Home is the gaps file; the row states it establishes **neither PBE descriptor layout nor general conversion semantics**. The general conversion semantics that *were* established (EXP-0079/0133/0144) are now in `format-table.md` §2e. |
| **EXP-0074** | **OPT-02 answered: No.** 4171 bit-exact-compared FP32 division cases; 3956 bit-exact; all 215 divergences are DAZ or FTZ; FTZ proven independently of DAZ; a single DAZ+FTZ model explains all | Home is `APPLE9_RE_IMPLEMENTATION_GAPS OPT-02` (off-limits). **This is a genuine `docs/` gap** — `isa/README.md`'s new NIR-contract section covers OPT-01/03/04/05/06/07/08/10/11 but OPT-02 and OPT-09 are answered in *other* experiments and their rows do not name a `docs/` home. **Recommended: add OPT-02 and OPT-09 rows to the NIR-contract table.** |
| **EXP-0093** | Fragment kill / sample-mask op (`byte0=0x57, byte2=0x54`); the `0x07` fence/barrier family; raster-order groups; the **symmetric-fencing requirement** (ATOM-07..11, GLFS-A08, OPT-09) | Home is `APPLE9_RE_OPENGL_TEXTURE_ADDENDUM` (off-limits). **This is the largest genuine `docs/` gap remaining** — it is real ISA surface (a previously undecoded 6-byte op) that belongs in `isa/README.md`, and the symmetric-fencing requirement belongs next to the new `pixel_order`/fence sections. |
| **EXP-0096** | Superseded by EXP-0100 (its selftest-fixture generator permanently blocked its pre-run02 gate) | Quarantined; nothing to place. |
| **EXP-0098** | GPU-driven draws and compute-emulated transform feedback (GLPRE-A01/A02, GLXFB-A01); generalises EXP-0093's asymmetric-fencing result to the command-buffer / resource-hazard level | Home is the addendum file. **Genuine `docs/` gap** — the XFB half now has a home (`capability-matrix.md` §2 records XFB as emulate), but the GPU-driven-draw and hazard results do not. |
| **EXP-0100** | Threadgroup addressing and memory capacity (GLCS-A02): 2900 splice + 145 budget cases ×2; CLOSED for 2884/2900 and 145/145; PARTIAL for 16/2900 | Home is the addendum file. **Genuine `docs/` gap** — threadgroup-memory bounds are explicitly listed as *not covered* by `memory-model.md` §1, and there is no threadgroup-memory chapter to extend. |

**Recommendation to the orchestrator.** Six of these eleven (EXP-0074, 0093, 0098, 0100, plus the
already-placed 0094/0097) are real hardware facts whose only home is
`APPLE9_RE_OPENGL_TEXTURE_ADDENDUM.md` / `APPLE9_RE_IMPLEMENTATION_GAPS.md`. Either those files
should be treated as normative deliverable documentation, or `docs/` needs two new chapters —
**a fragment kill/fence chapter** and **a threadgroup-memory chapter** — plus **OPT-02/OPT-09 rows
in the NIR-contract table**. This pass could not create them without exceeding its dispatch.

---

## 6. Method and clean-room note

```
Clean-room provenance: none required — this is a DESK task.
Inputs inspected: this repository's own committed PROVENANCE.md, experiment RESULTS.md files,
  tools/agx-isa/validation.json (read-only), and docs/.
Apple binary introspection: NONE. No GPU, no device, no SSH, no macvdmtool.
Reproduction: every added claim cites its EXP-NNNN inline; the coverage numbers are reproducible
  with `python3 -c "import json;print(json.load(open('tools/agx-isa/validation.json'))['coverage'])"`.
```

Every fact added carries (a) its experiment id inline, (b) the CODEX evidence label where the
source row states one, (c) the exact tested range or case count, and (d) **`target: G16G`**. No
fact was inferred, generalized, or relabelled `G17P`. Where two records disagreed, both are
shown with the correcting experiment named. One editorial cross-reference — the arithmetic
identity between EXP-0138's inline minifloat and EXP-0006's packed minifloat — is explicitly
flagged as an identity between two already-documented formulas, not a new measurement.
