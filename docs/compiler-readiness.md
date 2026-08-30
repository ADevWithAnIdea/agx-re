# Compiler readiness — what an implementer can build from this repository today

**What this document is.** Every other measurement in this project counts *inputs*: fields swept,
instructions emittable, closure rows advanced. This one asks the *output* question that the
project's Definition of Done actually turns on:

> Hand this repository to a compiler engineer who has never seen the hardware and cannot run an
> experiment. What can they compile, and where exactly do they get stuck?

This is an assessment, not a specification. It cites; it does not establish. Every claim below
names the committed experiment that supports it, and where two committed experiments disagree the
disagreement is stated rather than resolved.

**Audience assumption.** Per `CLAUDE.md`'s bar for `docs/`, the reader has never seen an Apple GPU,
has no device, and cannot re-run anything. Field rules are therefore given as literal bit rules an
emitter can apply, not as prose descriptions of them.

---

## 0. The headline

> **UPDATE 2026-08-30 — read this before the section below.** Two results have moved the answer in
> opposite directions, and both post-date the assessment that follows.
>
> **Forward:** `EXP-0158` supersedes `EXP-0112` as the strongest positive result in this repository.
> EXP-0112's generator produced 100 DAGs, but **every one of them carried at least one verbatim
> token lifted from a compiled shader** — its zero-copied-field count was **0**. EXP-0158 generated
> **237 programs containing ZERO copied fields and 233 produced their exact host-computed oracle on
> G17P**, never producing a wrong value. That is the first direct evidence for Definition-of-Done
> rules 1 and 6: a value *generated*, not decoded from a captured Apple template. Caveats that
> travel with it: 60 of the 233 rest on prior-published rules the experiment did not itself measure;
> 4 genuinely fail (`iadd2` register mode at specific destinations); 24 still need a donor (12
> control-flow, since no rule exists for any operand field of `icmp_pred`/`jump_cond`/`isel10`, and
> 12 immediate-mode `iadd2`); and **its cross-run gate FAILS** under concurrent GPU load, with
> EXP-0167 re-running it under isolation.
>
> **Backward:** the emittability figure this document leans on was **withdrawn from 79/166 to
> 41/166** by `EXP-0164`, an adversarial audit that re-derived every emitter-grade field from
> committed `raw/`. It downgraded 81 `INERT-SINGLE` and 41 `UNSTABLE` fields, and found that
> **144 fields (21.7%) have no per-value raw record attributable to them at all** — including
> **13 of `falu2`'s 15**, the most-cited descriptor in the DB. Treat any field rule below that cites
> a pre-`EXP-0138` wave as *unaudited* until `EXP-0169`'s re-record pass lands.
>
> **The methodological rule both imply,** driven by the observation that encoding space is too
> expensive for Apple to waste: an apparently-inert field usually means our carrier could not
> express what it controls. `iter_at.loc` read inert on every arm of EXP-0155; EXP-0163 built the
> same MSL twice with identical compiled bytes differing only in `rasterSampleCount` and it **moves
> at 4 samples, is inert at 1** — at one sample centroid, sample point and pixel centre are the same
> point. **Two carriers identical in the dimension the field controls are one carrier.**


**No — not a general shader back end. Yes — a specific, provably correct class of straight-line
f32 compute kernel.**

The strongest positive result in the repository is `EXP-0112`: a generator built *only* from
documented per-family rules synthesized **100 independently generated dataflow DAGs** (2–35 nodes,
44 of 100 requiring genuine physical-register reuse, up to 13 pool registers simultaneously live)
and **every one matched its host oracle bit-exactly, with zero per-program hand-tuning**, across two
byte-identical gated runs. That is a real compiler-shaped capability, not a replay of a captured
template.

**The first thing that stops a general back end is `nir_op_mov`.** There is no validated
register-to-register move on this ISA. `validation.json`'s note on all five `reg_move_*`
descriptors, established by `EXP-0087` → `EXP-0090` → `EXP-0101` → `EXP-0113` and carried forward by
`EXP-0140`, is verbatim:

> RETRACTION / HARD NEGATIVE: the five `reg_move_*` descriptors are ONE instruction with a single
> 8-bit byte+2 field, and NONE of them is a general GPR-to-GPR move. The readback is independent of
> the producer's VALUE and of the producer's FAMILY, depends only on `src_reg`, is
> register-pair-quantized (`reg` and `reg^1` read identically) and varies with the kernel's buffer
> signature — the signature of a fixed per-kernel PRELOADED/UNIFORM-FILE slot. […] **AS OF
> 2026-08-28 NO VALIDATED GPR-TO-GPR MOVE EXISTS ON APPLE9.**

This is not an abstract gap. `docs/isa/register-move-and-liveness.md` records that this repository
already received exactly this report from an external compiler engineer building a NIR→Apple9 back
end: *"he could not get a basic register-to-register move to work."* Two experiments were run to
check our own claims and **both found our documentation wrong** in a way that would silently corrupt
generated code.

Without a move you cannot lower a phi, cannot break a parallel copy at a control-flow join, cannot
coalesce or split live ranges, and cannot reload a spilled value into an arbitrary register.
`EXP-0112` succeeded precisely because it sidesteps all of that: single basic block, SSA-shaped,
each value assigned its own destination register, and `reg_move` **deliberately excluded from the
generator entirely** (`EXP-0112` §4, "correctly EXCLUDED […] using it would not be 'generating a
legal program'").

Immediately behind the move, in the order a NIR back end meets them:

| # | NIR construct | Status | Why |
|---|---|---|---|
| 1 | `nir_op_mov` (GPR→GPR) | **blocked** | no validated instruction (above) |
| 2 | `nir_op_iadd` / `isub` | **blocked, one field short** | `iadd2.srcB_ext` is `corpus-correlation` (§3.6) |
| 3 | `nir_op_ffma` | **blocked** | `falu3.op` / `.srcB` / `.srcC` are `untested` |
| 4 | `nir_op_ieq`/`ilt`/`bcsel` producer | **blocked** | `icmp_pred.srcA`/`.srcB` `untested`; 44 selector fields unresolved (`EXP-0139` §2) |
| 5 | `nir_loop` | **blocked** | `jump_cond` has **zero** emitter-grade fields (§3.1) |
| 6 | `nir_tex` | **blocked** | nothing in the sampling family is emittable (§3.2) |
| 7 | atomics | **blocked** | the op selector is `tokenization-only` (§3.3) |
| 8 | fragment `nir_store_output` | **blocked** | `frag_color_store` / `frag_color_pack` (§3.4) |

There is one **partial workaround for #1 in float code**, and it is worth stating because it is the
difference between "no compiler" and "a compiler for one shader class": `falu2` is emittable and
carries an **inline 8-bit float immediate** (`EXP-0138` §3), so `fadd rD, rS, 0.0` is a working
float copy. `EXP-0112` used exactly this — it routes a load-directly-to-store path "through a
trivial `+0.0` ALU finalizer" — and all 100 DAGs were bit-exact. **It is not a bit-preserving
copy**: under IEEE `−0.0 + 0.0 = +0.0`, and this hardware is measurably non-IEEE in at least one
neighbouring path (`EXP-0139` §1.5 found `iminmax` "flushes denormals to zero and suppresses NaN").
It is also unvalidated for integer bit patterns.

---

## 1. The emittable instruction set, as a usable list

### 1.1 What "emittable" means here, and the denominator

The bar is `docs/evidence-classification.md` §2, verbatim: *"a family may be described as
**emittable** only if every field an emitter must fill is `hardware-run` or `isolated-byte-diff`."*
`tools/agx-isa/db.json` round-tripping 302/302 proves decode and re-serialize; **it does not prove
synthesis**.

Committed state, `tools/agx-isa/validation.json` at commit `ff99bb52`
(`generated: 2026-08-28`, `db_sha256 eaca7256…`):

| | |
|---|---|
| Descriptors in the database | **171** |
| **Emittable** | **38** |
| Decodable, not yet emittable | **133** |
| Fields total | **1036** |
| Emitter grade (`hardware-run` 349 + `isolated-byte-diff` 94) | **443 = 42.8 %** |
| `corpus-correlation` / `tokenization-only` / `single-template-inference` / `untested` | 182 / 203 / 13 / 195 |

**The denominator 171 is wrong, and the correction is smaller than has been forecast.** Working from
`EXP-0148`'s committed classification of the 23 "decode scaffolding" descriptors plus the
zero-field descriptors in `validation.json`:

- **7 model no hardware instruction at all** (`EXP-0148` bucket (c)): `pad_operand`,
  `operand_word`, `operand_word_a2_01`, `operand_word_x2_h5`, `operand_word_x2_h6`,
  `operand_word_x2_h7`, `cubearray_coord_const`. (`cubearray_coord_const` "fires 0 times in 1080
  files" and cannot fire — its signature sits interior to a 12-byte `tex_addr_setup` token.)
- **6 descriptors have zero fields in `validation.json`** and so cannot be assessed field-wise at
  all: `rtq_pred`, `sfu_marker`, `n1_word`, `n3_word`, `n2_compact2` and `operand_word_a2_01` —
  five of them new here, since `operand_word_a2_01` is already in bucket (c). (`sfu_marker` is additionally
  *refuted* as a "byte-INVARIANT 2-byte token" by `EXP-0146` §3.5 — it carries live quadrant/sign
  control, so it is a real instruction whose fields are simply unmodelled.)
- **3 are continuation words of a longer parent** (`EXP-0148` bucket (a)): `frame_marker_compact`,
  `n2_compact2`, `b_alu14_prep2` — one of which (`n2_compact2`) is already counted above.

The arithmetic, stated so it can be checked against `validation.json` at
`db_sha256 eaca7256…`. The three sets overlap: `operand_word_a2_01` is both bucket (c) and
zero-field; `n2_compact2` is both bucket (a) and zero-field.

- bucket (c) ∪ zero-field = 7 + 6 − 1 = **12 removed** → **159 real descriptors**
- ∪ bucket (a) as well = 12 + 3 − 1 = **14 removed** → **157 real descriptors**

`work/UNATTENDED-RUN.md` forecasts "nearer **147** than 171", but **no committed experiment produces
147** — the triage that would (`work/dbtriage/`) is untracked. Use 157–159, or 171 with this
footnote; do not quote 147 as measured.

So the honest emittability fraction is **38 of 157–159**, or 24 %.

**A second correction, in the other direction: 38 is a floor, not a ceiling.** `EXP-0146` committed
`analysis/field_verdicts.json` containing **94 `hardware-run` field verdicts** across `carry_gen`,
`iadd2`, `ilogic`, `irotate`, `mov_zext16`, `n2_op10`, `n2_op6`, `n2_op8`, `n3_mov`, `sfu_marker`
and `shift_amt_move` — and **those verdicts were never merged into `validation.json`**, which
carries only three `EXP-0146` references (the `ilogic` LUT-selector split, at
`corpus-correlation`). Merging them mechanically would clear nine more descriptors, **`iadd2`
among them**. See §3.6 for why that merge is not automatic.

**Also note:** `tools/agx-isa/db.json` marks six instructions `emit_unsafe` regardless of their
field labels — `fspecial`, `vary_store`, `tg_addr_compute`, `half_alu_fma12`, `falu_srcmod12b`,
`op04_len8`. `tg_addr_compute` has **zero** blocking fields yet is still not emittable, because
`EXP-0141` H5 found that on M4 only one of 256 byte0 values (`0x1c`, the compiler's own) leaves the
tile dataflow correct, and neither byte0 nor byte+1 is modelled as a field at all.

### 1.2 The 38, grouped by what a back end would use them for

`copysign` · `cvt_f2h` · `cvt_f2i` · `cvt_i2f` · `cvt_i2f_src` · `device_load` · `device_store` ·
`falu2` · `frame_prologue` · `get_sr` · `half_alu` · `half_alu_ext8` · `ibitcount` · `if_push` ·
`iunary` · `link_save_restore` · `matrix_mac` · `mov_imm` · `n3_sample_read` · `pack_convert` ·
`pixel_order` · `psel` · `reg_move_c0` · `reg_move_c1` · `reg_move_c2var` · `reg_move_c9` ·
`reg_move_cb` · `sel` · `spill_frame_marker` · `stop` · `tex_addr_setup` · `threadgroup_barrier` ·
`tile_read` · `tile_read_mrt` · `uniform_mov` · `unpack_convert` · `vtx_coord_xform` · `vtx_out_pos`

Two entries on that list carry an asterisk before you use them:

- **The five `reg_move_*` entries are emittable but are not moves.** Their fields are
  `hardware-run`; the *instruction* is a read of a fixed per-kernel preloaded/uniform-file slot
  (§0). Emitting one is well-defined; it does not do what its name says.
- **`spill_frame_marker`'s "EXACT ROLE [is] UNRESOLVED"** (`validation.json`, from `EXP-M4-14`), and
  `EXP-0041` found this exact word **absent from all nine retained M4 own mains** including
  208–576 B declared scratch — "so it is NOT a universal spill marker."

### 1.3 Field rules, verbatim

Each rule below is the machine-derived exact mask from the cited experiment's own analysis, not a
paraphrase. Ranges are the parameter interval actually exercised; an implementer may not
extrapolate past them (`docs/evidence-classification.md` §3).

#### Memory — `device_load` (byte0 `0x67`), terminal scalar 32-bit indexed load — `EXP-0141` §0, §8

```
byte+1   space        v & 0x03 == 0x00      device space; bits 2..7 free   (256/256 swept)
byte+2   addr_mode    ANY                   inert on this shape (256/256)
byte+3   extmode      2*R,  R = 0..63       DESTINATION register; bit 0 is a don't-care
                                            R >= 64 SILENTLY ZEROES — it is not reachable here
byte+4   base_slot    slots 1..30 return their own bound buffer; slot 0 anomalous;
                      31..127 read 0x00000000 with NO fault; 128..255 mirror 0..127  (EXP-0083)
byte+5   index_reg    r0..r95 work; bit 7 IGNORED (128..255 mirror 0..127); r96..r127 FAULT
byte+6   access_desc  ANY                   inert (256/256)
byte+7   reserved7    ANY                   inert (256/256)
byte+8   ld_format    one of 21 accepted codes of 64  (not expressible as a mask rule)
         dst_lo       v & 0x03 == 0x01      MUST be 1
byte+9   dst_ext9     bit 0 MUST be 1  ->  WRITE 1
         idx_off      0..2047, unsigned 11-bit, no holes; the LOAD offset unit is a FIXED 4 BYTES,
                      independent of elem_size  (EXP-0082/EXP-0100)
byte+11  ldform_hi11  v & 0x07 == 0x00      bits 0..2 must be 0; bits 3..5 free
byte+12  elem_size    one of 48 accepted values of 256
byte+13  reserved13   ANY                   inert (256/256)
```

The `(dst_lo, dst_ext9)` pair was swept over its **full 512-value product** at four independent
target registers; exactly 64 of 512 work and they factorise as `{dst_lo == 1} × {dst_ext9 odd}`.
`dst_ext9 = 1` is valid under **every one of the 21 working `ld_format` codes**; how many of its
*upper* bits are additionally don't-cares is format-dependent (free for 16 codes, narrower for
`ld_format` 3/7/9/13, narrower again for 39) — so **just write 1**.

This is the single most important entry in this document. `work/DOC-02-LABELLING-REPORT.md` called
`device_load.dst_lo`/`dst_ext9` *the largest single synthesis blocker in the ISA*, because
`EXP-0112`'s generator could only produce correct DAGs by copying those two fields **verbatim from a
compiled shader**. It no longer needs to.

#### Memory — `device_store` (byte0 `0xE7`) — `EXP-0141` §4.2, §7 H10, §8

```
byte+1   space         v & 0x02 == 0x00     device space
byte+2   addr_mode     ALU-sourced data:  ANY (genuinely inert, 256/256)
                       LOAD-forwarded data: v & 0x02 == 0x02   REQUIRED
byte+3   extmode       2*R  or  (2*R)|0xC0   R = SOURCE register; bit 0 is LIVE here,
                                             unlike on the load side
byte+6   access_desc   ANY                   inert (256/256)
byte+7   reserved7     ANY                   inert (256/256)
byte+8   st_format     one of 84 accepted codes of 256
byte+9   st_format_ext v & 0x60 == 0x00      bits 5,6 must be 0
byte+11  st_desc_hi    v & 0x11 == 0x00      bits 0 and 4 must be 0; 1-3 and 5 free
byte+12  elem_size     one of 96 accepted values of 256
byte+13  reserved13    ANY                   inert (256/256)
         idx_off       the STORE offset unit is a FIXED 16 BYTES vs the LOAD's fixed 4
```

The `addr_mode` bit-1 rule is a **refinement of a prior claim, not a contradiction**: `EXP-0119`
recorded the bit inert, and it is — but only when the stored data is ALU-computed. With a live
`device_load` result as the source, exactly the 128 values with bit 1 set work and the other 128
**store 0**. A synthesized load-to-store forward with `addr_mode = 0x54` silently stores zero.

Store `base_slot`: probed at 0, 3, 31, 32, 63, 127, 128, 255 — **slot 128 writes are DISCARDED**;
the 128..255 mirror is load-only. Store `index_reg`: r0..r95 round-trip; 96, 97, 100, 111, 120, 127
uniformly FAULT; **r112 is genuinely nondeterministic** (fault or silent-all-zero across
byte-identical splices).

#### Float ALU — `falu2` (fadd / fmul) — `EXP-0138`, `EXP-0112`, `EXP-0099`, `EXP-0105`

```
dst            r0..r13 of 16 encodable nibble values, dense, incl. physical-register REUSE
srcA_reg       R = 0..63 dense. R in [64,112] SILENTLY ALIASES to r(R mod 64).
               R in {126,127} FAULTS the command buffer.
srcB_reg       same, in GPR mode
opsel          4 = fadd, 5 = fmul, validated on all 8 don't-care combinations.
               0b111 -> contained GPU hang. Instruction bit 17 is part of THIS field.
mod_lo         0..7 dense.  bit0 selects srcA's SOURCE CLASS (0 = GPR, 1 = a class that
               returned 0.0 at every index tested — NOT the uniform file).
               bits[2:1] select srcB's class: 0 = GPR, 1 = the non-GPR operand file,
               2 and 3 both read 0.0, and BIT 2 DOMINATES BIT 1.
opflags        bits 19..23: 19 = release srcA, 20 = release srcB, 21 = destination
               publication, 22/23 = silent corrupt-to-zero.
ctrl           bits 0/1 are the 0x09-group instruction-LENGTH selector (they corrupt when
               flipped in place); bits 2/3/4 inert; bits 5/6 silent corruptors.
srcA_reg_top   HW-tested INERT for both addressing and retention across six families.
srcB_reg_top   Role UNKNOWN. Never synthesize a meaning for either.
```

**The inline float immediate.** With `mod_lo` bits[2:1] = 1, `srcB_reg` is not a register index and
its bit 6 is live:

- `srcB_reg` **0..63** → uniform-register file index.
- `srcB_reg` **64..127** → an inline 8-bit minifloat immediate. With `k = srcB_reg − 64`,
  `e = k>>3`, `m = k&7`:

  ```
  value = m * 2^-5             (e == 0)
  value = (8 + m) * 2^(e-6)    (e  > 0)
  ```

  HW-confirmed at `k` = 0, 2, 3, 31, 32, 48, 56, 61, 62, 63 → 0, 0.0625, 0.09375, 1.875, 2.0, 8.0,
  16.0, 26.0, 28.0, 30.0. **In this mode indices 126/127 do NOT fault** (they are 28.0 and 30.0),
  unlike GPR mode. *The register model does not transfer across `mod_lo` classes.*

  Practical consequence: a large fraction of float constants need no `mov_imm` at all.

**One unresolved disagreement you must code around.** `validation.json`'s note on
`falu2.opflags` is explicit:

> DISAGREEMENT, UNRESOLVED: `EXP-0090` finding_1 established that a both-real `falu2` REQUIRES
> `opflags=3` and that `opflags=1` is a SILENT ZERO of the srcB read, falsified over 4 independent
> kernels. `EXP-0112` then swept all 4 raw values in TWO shapes — including a byte-for-byte
> re-creation of `EXP-0090`'s own falsifying construction — on a DIFFERENT carrier file and got the
> correct sum in all 8 runs, i.e. `opflags` had NO observable effect there. […] **Safe policy: emit
> `opflags=3` for a both-real `falu2` (correct under BOTH observations).**

#### Constants — `mov_imm` and `uniform_mov` — `EXP-0140` §1.1, §1.5, §4

```
mov_imm      dst      r0..r15 (4-bit).  16/16 dense; four 12-register aliasing scans confirm
                      no second register changes.
             imm7     0..127 ONLY.  See §4.1 and §4.2 — 128..255 and the value 12 are traps.
             imm_top  MUST be 0.

uniform_mov  dst      r0..r15.
             usrc     >= 0x80  ->  materialises the 7-bit immediate (usrc & 0x7F) into r_dst.
                                   128/128 matched a host-computed oracle exactly.
                      <  0x80  ->  uniform-register read, PAIR-QUANTISED (usrc and usrc^1 read the
                                   same 32-bit word; consecutive uniforms step by 4).
                                   Unallocated uniform indices return a SILENT ZERO.
             byte+2   v & 0xCB == 0x01      moves a value (8 of 256)
             byte+3   v & 0x0E == 0x08      moves a value (32 of 256)
```

So an emitter has **two independent ways to materialise a small constant into r0..r15**, plus
`falu2`'s inline minifloat for float operands.

#### Select — `sel` and `psel` — `EXP-0140` §1.3, §1.4

```
sel   byte+3   the predicate-FALSE operand. With bit 7 SET it is an 8-bit immediate WHOSE
               VALUE IS THE BYTE ITSELF (128..255). Matched a host oracle on 510 of 512 cases.
               Independently confirmed statically: (a>5)?130:250 compiles to `16 c2 a0 fa`
               (0xFA = 250); (a>5)?100:200 to `16 c2 a0 c8` (0xC8 = 200).
      byte+2   four 64-value classes: 128 inert / 128 wrong value / 128 silent zero / 127 FAULT
      byte+1   predicate/operand source selector: ONLY 194, 198, 202, 206 are inert.
               248 silently zero; 256 return a different value.

psel  byte+3 (sel)   512/512 matched the oracle — same immediate model as sel's byte+3
      byte+2 (mode)  inert exactly when v & 0xC0 == 0x00 (64 values); 127 values FAULT
      byte+1 (flag)  inert exactly when v & 0x12 == 0x02
```

⚠️ **You can emit the select but not its producer.** `icmp_pred.srcA`/`.srcB` are `untested`, and
`EXP-0146` `run05` P2 crossed `carry_gen.dst` 0..15 against a 32-point sweep of each `psel` body
byte — **1,536 combinations — and found no working pair other than the compiler's own `dst = 3`**.
`INT-13`'s standing advice applies: emit producer and consumer together. A branchless select is
therefore emittable only where the predicate is one the anchor already provides.

#### Barrier — `threadgroup_barrier` — `EXP-0141` §0 H4, §4.5

```
byte+1  sub        v & 0x06 == 0x04       (64 of 256)
byte+2             ANY                    inert (256/256) — a match-pinned byte db.json does
                                          not model as a field at all
byte+3  mem_scope  v & 0x01 == 0x01       bit 0 is the EXECUTION-CONVERGENCE enable.
                                          All 128 odd values pass; all 128 even values fail
                                          with the same 224 stale lanes.
byte+4  flags      ANY                    inert (256/256)
byte+5  b5         ANY                    inert (256/256)
```

This is a **real negative, not an insensitive carrier**: the same carrier's falsifier makes
**224 of 256 lanes** read stale zeros when the barrier is neutralised (224 = 256 − 32, exactly the
lanes outside the writer's own SIMD group). **But** the memory-fence *class* bits are don't-cares
here and the fence instructions themselves were deliberately **not** promoted — see §3.7.

#### Integer — `ibitcount` and `iunary` — `EXP-0139` §1.1, §1.2

Both became emittable on **fully synthesized** programs (16 `mov_imm` seeds → op → `device_store` →
`stop`; nothing copied from a compiler template).

```
ibitcount  byte+1 / byte0 bit7   the SUB-OP selector: (0x27,0x05) popcount,
                                 (0xa7,0x05) find_msb, (0xa7,0x04) reverse_bits.
                                 CORRECTION: it is NOT byte+4.
           byte+3  dst           reg << 1
           byte+4  op_enable     ONLY BIT 1 decides (128 work / 128 do not)
           byte+5  src           reg << 2
           byte+6  srcdesc       bit 6 MUST be set for the GPR source to be read.
                                 bit 4 is a real BIDIRECTIONAL RELEASE control.
                                 bit 0 and bit 3 also break the stored result.
           byte+7  tail          ONLY BIT 2 is load-bearing; the other 7 bits are free.
                                 128 values with bit2 set are correct; 128 without return a
                                 wrong, constant, NON-ZERO value.

iunary     reachable at byte+1 = 0x2d with byte+2 in {0x22,0x26,0x07,0x66,0x46,0x76}
           — a member the tighter ibitcount descriptor does not swallow.
           Its 40-bit `operand` raw field is FIVE one-byte sub-fields with exactly
           ibitcount's meanings (+3 dst, +4 op_enable, +5 src, +6 srcdesc, +7 tail).
```

`iunary` is an **extrapolate-and-test success**: no `iunary`-tokenizing instruction exists anywhere
in 30 authored MSL probe kernels; the encoding was found by searching the 8-byte `byte0 == 0x27`
space, and the hardware accepts and executes it.

#### Control flow — `if_push` and `stop` — `EXP-0140` §1.6, §3; `EXP-0003`/`EXP-0010`

```
if_push  scope       COMPLETELY INERT across all 256 values
         scope_kind  64 values inert, 178 wrong value, 1 hang — LOAD-BEARING

stop     the whole 24-bit body is HW-proven non-load-bearing padding. A driver emits 0x000000.
         The "end-of-program flags/scope" hypothesis is DISPROVEN, and corrupting the whole word
         is a no-op — the program still terminates correctly. `stop` is NOT a required terminator;
         true end-of-program is out of band (the metadata code length).
```

#### Tile buffer — `tile_read` / `tile_read_mrt` — `EXP-0147` §2.2

Liveness proven, not assumed: a `dst_alt` control changes only the clear colour and the pixel
follows its host oracle; a litmus-power probe forces the read to zero and the pixel collapses to
`src` alone.

```
tile_read      b2        fully inert (256/256)
               b4        fully inert (256/256)
               read_en   byte+6 BIT 0: all 128 ODD values correct, all 128 EVEN values give a
                         SILENT ZERO. Bits 1-7 don't-care. Identical rule on tile_read_mrt.
               rt_index  with ONE attachment bound, correct ONLY at 0x00,0x01,0x80,0x81
                         (bit0 and bit7 don't-care). Every other index SILENTLY RETURNS ZERO.
               dst       correct only at 0x00,0x01,0xc0,0xc1; 0x02-0x07 wrong; bulk silent zero;
                         0xf6-0xff fault or collateral. NOT a plain 8-bit GPR index.
               b7        correct only at 0xae,0xaf,0xee,0xef.
                         ⚠️ 85 of 256 values are NONDETERMINISTIC across replicates AND runs.
               tail      bytes 1 and 3 almost entirely SILENT ZERO off baseline; byte 0 is
                         nondeterminism-heavy (95 unstable).

tile_read_mrt  same shape shifted by this carrier's baseline: dst ok at 0x08,0x09,0xc8,0xc9;
               rt_index ok at 0x08,0x09,0x88,0x89.
               fmt       correct only at 0x2e,0x2f,0x6e,0x6f,0xae,0xaf,0xee,0xef
                         -> bits 1-5 are the FORMAT SELECTOR; bits 0, 6, 7 don't-care.
                         104 values give a silent zero.
```

#### Matrix unit — `matrix_mac` — `EXP-O2C`, `RT-10-isa-pass2`, `EXP-0147` §2.1

```
dtype       0x00 half, 0x02 float/bfloat
mode        0x56 standalone, 0x54 tiled. Splicing standalone -> tiled ZEROES the result
            (tiled sources its accumulator from the MPP tile context) — SEMANTIC, not a hint.
a_reg/b_reg operand identity unambiguous: matmul is non-commutative, and A*B / B*A / A*A / B*B
            were all distinguished by splice.
op_enable   0x24 enables the multiply. ⚠️ FP32-DATAPATH-SPECIFIC: the half datapath (dtype 0x00)
            uses byte+10 = 0x8c / byte+11 = 0x00 and its accumulate byte is UNCHARACTERIZED.
acc_en      0x01 -> a*b+c, 0x00 -> a*b. FP32 datapath only.
dst_desc    correct A*B+C IFF bit6 == 1 AND bit7 == 0 (0x40-0x7f, 64/64). Bits 0-5 don't-care.
            0x00-0x3f and 0x80-0xbf give a SILENT ZERO (128 values); 0xc0-0xff a wrong value.
b11hi       documented A*B+C IFF (b11hi & 3) == 0 (32 of 128); bits 2-6 don't-care.
            See §4.8 — the two low bits are accumulator SIGN controls.
```

#### Raster-order groups — `pixel_order` — `EXP-0147` §2.3

The acquire and release members have **different** legal sets; this is a result, not sloppiness.

```
                   ACQUIRE (07 14 54 50 06 00)          RELEASE (07 04 54 d0 06 00)
scope  (byte+3)    bit4 == 1 AND (bit6 XOR bit7) == 1   bit4 == 1 AND bit7 == 1
                   (64 of 256)                          (64 of 256)
flags  (byte+4)    bit0 == 0 AND (v & 0x0e) != 0        (v & 0x0f) >= 2
                   (112 of 256)                         (224 of 256)
b5     (byte+5)    fully inert, all 256                 fully inert, all 256
```

Detection strength, in numbers: corrupting the acquire member's byte+4 drops the read-back texel
from `8*src` to `1*src` — **7 of 8 serialised read-modify-writes lost**. The same corruption on the
release member loses **no** updates at all, which is why the release arm's sensitivity control did
not fail and that arm promotes nothing.

⚠️ **`db.json` cannot express what the hardware accepts here.** It declares a field `flags` at
bits[32:40] *and* a match constant pinning the same bits to `0x06`. Every legal encoding with
byte+4 ≠ `0x06` is therefore neither decodable nor emittable by the current tables. Fixing that
descriptor is a prerequisite to using the larger legal set.

#### Conversions and packing — `cvt_*`, `pack_convert`, `unpack_convert` — `EXP-0144`

All fields dense 0..255. **Read the provenance caveat before using them**: every one of these
labels rests on `EXP-0144`'s revalidation captures `rv01` **only**. The earlier `run01`–`run05`
captures back no label — they were taken across a window in which a GPU test destabilised
WindowServer and took `MTLCompilerService` down machine-wide. `EXP-0144` **withdrew its own
44-of-51 claim down to 33** on re-measurement; of the measurements that were repeated, 92 of 13,783
(0.67 %) were overturned, and each field's `note` records its own overturn rate (`cvt_f2h.op`, for
example, had 22 of 256 overturned = 8.59 %).

The load-bearing correction is structural, not numeric: **`db.json`'s operand model for
`pack_convert` and `unpack_convert` is wrong.** Both model several live operand bytes as one opaque
raw descriptor (`fmt_word`, `convert_desc`). Those bytes are in fact the destination register, the
two per-lane source registers, and an emittable **format selector** with a decoded code table:

```
pack_convert byte+9   0x42 0x46 0x4a 0x4e  ->  snorm2x16   (scale 32767)
                      0x82 0x86 0x8a 0x8e  ->  unorm2x16   (scale 65535)
                      0xc2 0xc6 0xca 0xce  ->  unorm 8-bit lanes (scale 255) into bits [7:0],[15:8]
unpack_convert        0x0a 0x8a -> unorm8   0x2a 0xaa -> snorm16
                      0x4a 0xca -> unorm16  0x6a 0xea -> unorm8
```

**An implementer following `db.json` today cannot emit either instruction; with this table they
can.**

#### Function frames — `frame_prologue`, `link_save_restore`, `spill_frame_marker` — `EXP-M4-14`

```
frame_prologue    subop       ONLY values with bits[1:0] == 0b11 run (0x03/0x0b/0x13/0x23/0x43).
                              0x00/0x01/0x02/0x04 FAULT.
                  frame_size  16-byte granular. Over-allocation is tolerated (0x20 -> 0x30) but
                              too small or misaligned FAULTS. ⚠️ NOT cleanly monotonic —
                              0x40 faults while 0x30 runs — so the sub-field layout is NOT
                              fully resolved.
                  marker      reserved/inert

link_save_restore scope       0x81/0x83 pass (bit7 AND bit0 both set). 0x00/0x80/0x01 CORRUPT
                              the SAVE and HANG the RESTORE. 0xff -> GPU page-fault.
                  dir_offset  16-bit (bytes +5/+6). CORRECTION: not the DB's former 24-bit field;
                              byte+7 is reserved and inert on both instances.
                  In a RACE-FREE frame the op is a no-op fence and every payload field is inert;
                  in a SPILLING frame (12 live temporaries) byte0 0x07 -> 0x00 corrupts the SAVE
                  and HANGS the RESTORE.

spill_frame_marker  byte+3 = 0xff FAULTS; every other swept byte is runtime-inert.
                    EXACT ROLE UNRESOLVED (see §1.2).
```

#### Special registers — `get_sr` — `EXP-0092`, `EXP-0140` §1.2

```
dst        R = 0..95 fully round-trip correct. 96,97,100,111,120,127 uniformly FAULT.
           R = 112 is NONDETERMINISTIC (fault in one run, silent-all-zero in the other;
           8 further informal repeats split 5/3).
           ** This is the ONLY validated write path to r64..r95 anywhere in the repository. **
           96 is the hard register-file ceiling.
sr_sel     0x00..0xFF EXHAUSTIVE, 256 values x 2 runs, zero faults, zero hangs.
           0x80-0xFF reaches the special-register file (16 named, ~106 aliasing, 4 unclassified
           constants, 2 period-4 structured). 0x00-0x7F is a distinct
           "selector materialized as an immediate" region, NOT an SR read.
form       0, 1 — both inert
dp_width   (v & 0xD3) == 0x10   bits 0,1,6,7 clear, bit 4 set; bits 2,3,5 don't-care.
           32 of 256 values FAULT; 216 silently return the wrong vector.
dp_marker  (v & 0xE6) == 0x06   bits 1,2 set, bits 5,6,7 clear; bits 0,3,4 don't-care.
```

⚠️ Two caveats an implementer will hit, recorded verbatim in `validation.json`: **`0xa8`/`0xa9`/
`0xaa` is NOT `threadgroups_per_grid`** — a bare `get_sr 0xa8` returns `threads_per_threadgroup`,
and the builtin is `get_sr` + a `device_load` + a divide (`RT-7`); and unclassified `0x80`–`0xFF`
values must not be treated as reserved-safe no-ops.

#### The rest, in brief

- **`copysign`** — byte+3 (`operands`) is INERT across all 256 values; byte+1 is a **live operand
  field** where 240 of 256 values silently zero and 8 flip the sign; byte+2 is a 256/256 don't-care.
  (`db.json` models byte+1 and byte+2 as fixed match constants — both wrong.) `EXP-0138` §4.
- **`half_alu`** — byte+1 is the **first source descriptor, not the destination** (H-HALF-LAYOUT
  confirmed); descriptor bit 7 is confirmed inert; `opflags` 0..7 behave as the anchor, 8..29 change
  the result, 10..31 silently zero. `src_modifier` byte+5: bits 6:7 are a **required operand-valid
  base** (clearing them yields 0), bit 3 is srcA-negate, bit 0 suppresses srcB, bits 1/2 suppress
  srcA. `EXP-0138` §4, `EXP-M4-14`.
- **`half_alu_ext8`** — adds `opsel` 6 = hfma; `saturate` at byte+7 bit 1 (`0x82` clamps
  `saturate(9)` to 1, `0x80` passes 9 unclamped); **every byte+7 value without bit 7 set nulls the
  op** — a required op-valid marker.
- **`n3_sample_read`** — `b1` and `b3` fully inert (256/256); `tail` bytes 1–5 fully inert, **but
  53 values of `tail` byte 0 fault with "Caused GPU Hang Error"**.
- **`vtx_out_pos`** — `dst` (16 values) and `slot` (256 values) **fully inert** in both runs, with a
  litmus-power probe that does move the pixel. **Scope limit stated by the experiment:** the carrier
  writes ONE varying slot, so this cannot distinguish "don't-care" from "only one legal slot
  exists". A multi-varying carrier is the named follow-up.
- **`vtx_coord_xform`** — `mode` correct exactly when `(mode & 0xf3) ∈ {0x22, 0xe2}` (8 of 256);
  **240 of 256 values SUPPRESS THE DRAW ENTIRELY**. `sel`: 91 correct, 143 no-draw, **19 genuine
  "Caused GPU Hang Error"**. `operand` bytes 0 and 4 fully inert; byte 3 fault-prone.
- **`tex_addr_setup`** — all 11 fields `hardware-run`, but **on A18/G17P** (`EXP-M4-14`), not M4.
  `form` 0x01 = coordinate projection, 0x05 = sample-address + explicit LOD/gradient, 0x07 = raw
  passthrough, 0x0d = alias of 0x05. `op_reg`: **only 0x06 tracks the LOD input**; every other value
  reads a zero register. `src_desc`: only 0xf0 and 0xff preserve the operand (hi-nibble `0xf` =
  "operand is a register"). See §3.2 — you can set up the address and not issue the sample.

---

## 2. What you can compile today

### 2.1 The proven envelope

`EXP-0112`'s generator establishes the outer edge of what is *provably* synthesizable, and it did so
against a pre-registered contract: 161 cases, **byte-identical raw results across two runs**,
140/140 `expect_match=True` passing and 21/21 `expect_match=False` behaving exactly as
pre-registered.

**CAN be generated (verbatim from `EXP-0112` §4):**

- arbitrary-shaped f32 `fadd`/`fmul` dataflow DAGs, 2–35 nodes, with genuine physical-register
  reuse under the documented liveness discipline (up to 13 of 14 pool registers simultaneously
  live);
- `device_load` → `falu2`/`falu2i` bridging for **any** register in 0..63, dense-swept;
- the `device_load` → `iadd2` → `device_store` anchor with independently varied addend K over its
  full effective 0..127 range including the K = 128 wraparound;
- the loop + if/else→select control-flow **skeleton**, parameterized by trip count, branch-selecting
  data, and `icmp_pred`'s `cond` field.

`EXP-0090` independently hand-built and validated three whole programs — an arithmetic dataflow
chain, a memory round trip, and real control flow — 24/24 cases matching an independent Python
oracle in two byte-identical runs. Its fourth program, a register-pressure/move test, **could not be
made to work and is reported as a first-class negative** — that is the move gap of §0.

### 2.2 A worked example

This is the shape `EXP-0139` §1.1 built and executed as a **fully synthesized** program with
nothing copied from a compiler template, extended with the float and select work that landed
alongside it. Each line names the rule it satisfies and the experiment that established it.

```
;  out[gid] = popcount(a) ;  and  y = (x * 2.0) + 8.0  ;  stored to out[1]
;
;  --- prologue: thread id -----------------------------------------------------
get_sr      r0 <- thread_position_in_grid.x
              sr_sel   in 0x80..0xFF, from the exhaustive 256-value census   [EXP-0092]
              dst      R = 0..95                                            [EXP-0092]
              dp_width  (v & 0xD3) == 0x10
              dp_marker (v & 0xE6) == 0x06                                  [EXP-0140 §1.2]
;
;  --- constants: two independent ways, no mov needed for float ---------------
mov_imm     r3 <- 91          imm7 in 0..127, NEVER 12, imm_top = 0         [EXP-0140 §4]
uniform_mov r4 <- 0x2A        usrc = 0x80|0x2A materialises the immediate    [EXP-0140 §1.5]
;
;  --- load ------------------------------------------------------------------
device_load r5 <- buf[idx]
              space    v & 0x03 == 0x00
              extmode  = 2*5  = 0x0A        (destination register, R = 0..63 ONLY)
              dst_lo   = 1                  (v & 0x03 == 0x01)
              dst_ext9 = 1                  (bit 0 must be 1 — just write 1)
              index_reg = r0                (r0..r95; r96+ FAULT)
              idx_off   in 0..2047, unit = 4 BYTES                          [EXP-0141, EXP-0082]
;
;  --- integer ---------------------------------------------------------------
ibitcount   r6 <- popcount(r3)
              byte0/byte+1 = (0x27,0x05)    popcount sub-op
              byte+3 dst   = 6<<1
              byte+4       bit 1 SET        (op_enable)
              byte+5 src   = 3<<2
              byte+6       bit 6 SET        (GPR source), bit 4 = release control
              byte+7       bit 2 SET        (the other seven bits are FREE)  [EXP-0139 §1.1]
;
;  --- float, using the inline minifloat immediate — no mov_imm ---------------
falu2       r7 <- r5 * 2.0
              opsel    = 5 (fmul)
              mod_lo   bits[2:1] = 1        (srcB is the non-GPR operand file)
              srcB_reg = 64 + 32 = 96       (k=32 -> e=4, m=0 -> (8+0)*2^(4-6) = 2.0;
                                             k=32 is one of the 10 HW-confirmed points)
              srcA_reg = 5                  (0..63; 64..112 SILENTLY ALIAS to r(R mod 64))
              opflags  = 3                  (the safe policy under BOTH observations)  [EXP-0138]
falu2       r8 <- r7 + 8.0
              opsel    = 4 (fadd), srcB_reg = 64 + 48 = 112   (k=48 -> e=6, m=0 -> 8.0,
                                                               HW-confirmed)
;
;  --- barrier (compute) -----------------------------------------------------
threadgroup_barrier
              sub       v & 0x06 == 0x04
              mem_scope bit 0 SET           (execution convergence; 224 stale lanes without it)
              flags, b5 ANY                                                 [EXP-0141 H4]
;
;  --- store -----------------------------------------------------------------
device_store buf2[idx] <- r6
              extmode   = 2*6 = 0x0C        (SOURCE register; bit 0 is LIVE here)
              addr_mode ANY (data is ALU-computed)  — but v & 0x02 == 0x02 IF the data is a
                                                      live device_load result
              st_format one of the 84 accepted codes
              idx_off   unit = 16 BYTES, not 4                              [EXP-0141]
;
stop          body = 0x000000, HW-proven non-load-bearing padding           [EXP-0003/0010]
```

### 2.3 Three disciplines a back end must implement, which are not obvious from the tables

1. **Operand release / producer-side writeback suppression.** This is a real liveness mechanism, and
   getting it wrong silently drops values. `EXP-0086` ran the decisive test: `v = 7.5`;
   `x1 = v + 10`; `x2 = v + 20`. Flipping the liveness bit on the **earlier** (producer) instruction
   gives `17.5, 20` — the later read got `v` as **zero**. Flipping it on the **later** instruction
   changes nothing. `EXP-0089` reached the literal bit 17 in two independent families and confirmed
   it, and its `discrim3` kernel supports **persistent producer-side writeback suppression** over a
   one-shot bypass-cache model: corruption reaches a *third*, independent later reader and never an
   earlier one. `EXP-0129` further showed the effect is **operand-provenance-dependent**: a
   `device_load`-sourced operand breaks already at grid = 1, an ALU-immediate-seeded one never
   breaks. A back end must emit the release bit only at true last use.

2. **The `ctrl`/`ctrl_lo` field is not padding.** `EXP-0089`: bits 2/4 safe in 13 of 14 compact-form
   contexts; bits 0/1/3/5/6 load-bearing (fault or silent corruption); the **12-byte extended form
   is 0 of 8 safe, including a genuine GPU hang**. On `falu2` specifically, `ctrl` bits 0/1 are the
   0x09-group instruction-**length** selector (`EXP-0119`) — flipping them in place re-lengths the
   instruction and corrupts the stream.

3. **Register-file geography.** r0..r63 are freely addressable by the ALU register fields; **r64..r95
   are only reachable as a `get_sr` destination** (`EXP-0092`/`EXP-0113`), and r96 is a hard
   ceiling confirmed independently by `iadd2.dst` faulting at reg ≥ 96 (`EXP-0139`) and by
   `EXP-0020`. Note the sharp inconsistency in what happens above the limit: `falu2` register fields
   **alias** `r(R mod 64)` for R in [64,112] and fault at 126/127; `device_load.extmode`
   **silently zeroes** above 63; `iadd2.dst` **faults** at reg ≥ 96 and **does not alias** — see §3.6.

---

## 3. What you cannot compile, and precisely why

### 3.1 Loops and general control flow — `jump_cond` has zero emitter-grade fields

`jump_cond`'s three fields are `cf_scope` (`corpus-correlation`), `offset` (`corpus-correlation`)
and `reserved` (`tokenization-only`). Nothing is emitter-grade.

**The reason it stayed blocked is carrier liveness, not inertness** — and this distinction is the
whole point. `EXP-0140` §5 swept every structured offset, *including targets that are not
instruction starts and targets outside the program*, plus all 256 values of `cf_scope` and
`reserved`. Every single one reproduced the baseline exactly. Verbatim:

> The reason is structural: `jump_cond` is the loop-entry guard, and **the only lane whose guard is
> true has trip count 0**, so both paths compute the same value. The sweep therefore has **no
> discriminating power** over this instruction, however clean it looks […] A successor needs a
> carrier whose conditional-branch target is observable.

An inert-looking result from a powerless carrier is not evidence of inertness, and the experiment
declined to promote on that basis. `EXP-0115`'s branch-reach measurement was made on `jump`, **and
does not transfer to `jump_cond`**.

**What this blocks at NIR level:** `nir_loop` entirely; any `nir_if` that lowers to real branch
machinery rather than predication. `EXP-0104` found reducible if/else has **two qualitatively
different lowerings** — pure predication vs. real branch machinery, selected by
return/break/continue presence — so a control-flow generator needs that distinction built in.
`EXP-0112` parameterizes **one fixed skeleton**; it is explicitly not a CF generator.

The rest of the family, with what blocks each:

| Instruction | Blocking fields |
|---|---|
| `jump` | `branch_ctrl` (`corpus-correlation`) — `offset` and `link` **are** emitter-grade |
| `if_push_pred` | `level` (`tokenization-only`); arm stopped after **2 GPU hangs** |
| `pop_reconverge` | `reserved` (`tokenization-only`). `scope_kind = 0` is the single fatal value found. |
| `ret` | `linkmode`, `scoreboard` (both `corpus-correlation`); `scoreboard` bit 2 "located, not spliced". Arm stopped after 2 hangs. |
| `ret_luse` | `linkmode` (`corpus-correlation`), `tail` (`tokenization-only`) |
| `mask_op` | the *instruction itself* is `tokenization-only`; `scope_kind` is `single-template-inference` (`0x19` in the whole corpus, no variation) |
| `call` | `b3`, `b5`, `b6`, `tail` all `tokenization-only` |
| `call_indirect` | **all four** fields `tokenization-only` — including `target_lo`, the indirect branch target itself |

**Four of these are one gated run short, not one hardware result short.** `EXP-0140` §5:
`jump.branch_ctrl` (256/256 executed in run02), `ret.linkmode` (256/256, exact rule `(v & 7) == 4`),
`pop_reconverge.reserved` and `ret.scoreboard`/`if_push_pred.level` all lack a second agreeing
capture. The experiment's own estimate: *"One more complete capture would very likely take `jump`,
`ret`, `pop_reconverge` and `if_push_pred` to emittable, i.e. 18 of 23."* That makes control flow
the **cheapest** large gap on this list.

### 3.2 Texture sampling — nothing in the family is emittable

`tex_sample`'s `_instruction` entry is `hardware-run` on `M4+A18` — *"sample / gather / read /
sample_compare / LOD-query executed; all 8 compare functions HW-validated"*. **The instruction runs;
its fields are not synthesizable.** This is the decode-vs-synthesis distinction in its purest form.

| Instruction | Blocking fields |
|---|---|
| **`tex_sample`** | **`untested`: `comp_flags`, `result_sel`, `tex_type`, `samp_extra`** (all `range: none`, `evidence: []`). `corpus-correlation`: `kind`, `chain`, `coord`, `extra_coord`, `lod_present`. Emitter-grade: `result_desc`, `variant`, `tex_slot`, `samp_slot_offset`, `mode`. |
| **`tex_write`** | **zero emitter-grade fields.** `untested` (8): `coord_pack`, `amode`, `coord_regs`, `rsv8`, `rsv10`, `rsv11`, `wop`, `rsv15`. `corpus-correlation` (5): `seq_idx`, `layer_reg`, `coord_dim`, `data_desc`, `data_desc_hi` — all from `EXP-M4-13`, which is **compile-only**. |
| **`tex_coord_setup`** | **zero emitter-grade.** `untested` (7): `dst_lo`, `b1`, `subop`, `b5`, `b6`, `b8`, `b9`. |
| `tex_deriv` | `b1`, `dstsrc`, `src_comp`, `tail` all `tokenization-only`; only `axis` emitter-grade |
| `n3_addr_prep`, `n3_mov` | `corpus-correlation` throughout |

**The top untested blockers, named exactly as the task requires:** `tex_sample.coord` (the
coordinate register — `corpus-correlation`, never executed with a synthesized value) and
`tex_sample.result_sel` / `result_desc` (the result registers). Without those two you cannot say
which registers carry the coordinate in and which carry the texel out.

**What this blocks at NIR level:** all of `nir_tex` — `nir_texop_tex`, `txl`, `txb`, `txd`, `txf`,
`tg4`, `lod`, `txs`. Also `nir_image_store` (`tex_write` has no emitter-grade field at all).
`tex_addr_setup` **is** emittable (§1.3), so an implementer can build the address and then has no
validated way to issue the fetch.

### 3.3 Atomics — 14 of 17 fields are `hardware-run` and the family is still blocked

This one is a **modelling** blocker, not an evidence blocker, and it is worth understanding because
the fix is cheap.

`EXP-0141` swept `atomic_mem` and `atomic_rmw` densely and closed 14 of 14 blocking fields on each,
including two results the tables did not have:

- **The RMW operand register is encoded in the instruction, not implicit.** `db.json` says *"the
  actual RMW operand register is implicit (supplied by the preceding op / amode)"* and `DOC-02`
  ranked this a missing field — *"the worst kind of gap for an emitter."* It is not implicit:
  `operand_register_index = (byte+5 >> 7) | ((byte+6 & 0x3F) << 1)`, **proven at indices 0, 1, 2 and
  3** (index 3 constructed for the first time in the addendum). The redirected register is
  **consumed** — its later reader gets 0 — independently corroborating the release contract.
- **`atomic_rmw` shares `atomic_mem`'s layout, confirmed byte-for-byte**: with byte+1 pinned to
  `0x11`, each of bytes +2..+13 swept densely yields an accepted set identical to the corresponding
  `atomic_mem` arm, all twelve bytes.
- Three bytes named "reserved" (`rsv10`, `rsv11`, `rsv6`, `rsv9`) are **live and heavily
  constrained**.
- byte+12 — carrying `op_lsb`, `op`, `per_lane` and `op_msb` — was swept over **all 256 values**,
  i.e. every combination of those four sub-fields, and `0x36` (op 27 = `sub`) yields `0xFFFFFFF9` =
  −7 exactly.

**And yet the family is not emittable**, because `validation.json` still carries `op_lsb` and
`op_msb` as `tokenization-only` and `per_lane` as `corpus-correlation`. The op *byte* was swept
exhaustively; the DB's *split of that byte into four sub-fields* is what has no established
semantics. An emitter cannot fill `op_lsb` from the tables even though it can fill the byte.

`atomic_tg` is separately blocked and separately hazardous:

- `op_desc` (byte+5) is **PARTIAL** — run 11 aborted the arm at case 129/257 after **two reproduced
  GPU hangs**, at exactly `0x7E` (HANG, HANG, HANG) and `0x7F`. Run 12 did not hang on those values
  but returned a reproduced `CMDBUF_ERROR` 3/3. Both encodings are reproducibly bad in both runs;
  their *severity* varies between a contained fault and a real hang.
  **DO NOT EMIT `atomic_tg` byte+5 in `0x7E..0x7F`.**
- `op` (the 5-bit enum at bits 86–91) is `corpus-correlation`, with the note: *"Enum values are
  HW-validated on the DEVICE atomic (EXP-0018/EXP-M4-10); their reuse at this bit position is a
  structural/corpus finding, not an independent splice."*
- `atomic_tg`'s `op` field straddles byte+10 and byte+11 and the sweep is one byte at a time, so the
  **joint** space is not covered.

**What this blocks at NIR level:** every `nir_intrinsic_*_atomic` and `*_atomic_swap`, on both
`global`/`ssbo` and `shared` address spaces.

### 3.4 Fragment colour output and varying interpolation

| Instruction | Blocking fields |
|---|---|
| **`frag_color_store`** | `store_mode` — **`single-template-inference`**: *"0x54 in 130/130 corpus stores — no variation observed."* Plus `flags`, `mask`, `fmt`, `slice_addr` (`corpus-correlation`). Only `src` and `rt_index` are emitter-grade. |
| **`frag_color_pack`** | `untested`: `src_desc`, `dst`, `mode`, `comp_off` (all `range: none`, `evidence: []`). `corpus-correlation`: `fmt_class`, `val`. |
| `frag_depth_store` | `b3`, `b4`, `b5` all `tokenization-only` |
| `frag_tile_setup` | `sel`, `access` `corpus-correlation`; `b1`, `b5` `single-template-inference` |
| **`iter`** (varying interpolation) | **`untested` (6): `grp`, `lead`, `coeff_sel`, `c7`, `loc`, `b9`**; `dst` `corpus-correlation` |
| **`iter_at`** | **`untested` (5): `grp`, `lead`, `dst`, `c4`, `b5`** |
| `iter_flat` | `b1`, `sel`, `b4`, `b5` all `tokenization-only` |
| **`vary_store`** (VS output) | `emit_unsafe` in `db.json`. `untested`: `hint1`, `hint6`, `b7`; `corpus-correlation`: `hint2`, `out_slot_hi`; `single-template-inference`: `b5_tag` |
| `vary_slot` | `sel`, `slot` both `corpus-correlation` |

`frag_color_store.store_mode` is the textbook case the whole labelling standard exists to catch: one
value observed 130 times is indistinguishable from a constant, a don't-care, and a load-bearing
field that nothing has yet varied.

One usefully concrete datum survives inside the blocked set: `frag_color_store.fmt` is
`corpus-correlation` but has a measured range — *"byte+7 tracks the ATTACHMENT format, proven by a
colour-format sweep with the shader return width held at float4: RGBA8Unorm/sRGB/BGRA8 = 0x4e,
RGBA16Float = 0x0e, RGBA32Float = 0x2e, R32Float = 0x22, R8Unorm = 0x42"* (`EXP-M4-13` + `EXP-0108`).

**What this blocks at NIR level:** `nir_store_output` in a fragment shader (colour and depth);
`nir_load_interpolated_input` and `nir_load_input` in a fragment shader — a driver **cannot emit a
varying interpolation at all**; `nir_store_output` in a vertex shader, except `[[position]] `via
`vtx_out_pos`, whose `slot` field was measured inert in a **single-slot carrier** and therefore says
nothing about a multi-varying program.

The tile-buffer side of the fragment pipeline *is* emittable (`tile_read`, `tile_read_mrt`,
`pixel_order`, `n3_sample_read`), which is why `EXP-0147` records it as advancing P0.4: a BG/EOT
program's tilebuffer **read** is now a specified encoding. The **write** is not.

### 3.5 Transcendentals — the arm was stopped for hangs

`fspecial` has 11 fields, all still at their prior labels, from **one gated run only**. `EXP-0138`
§6:

> **`fspecial.src` (byte+3) values 192..255 fault or hang the GPU.** `run01` (contended host): 60
> reproducible faults. `run05` (isolated host): values 192, 193, 194 each **HUNG the GPU three times
> in a row** under the 12 s watchdog. Only values 2 and 3 give the correct `rsqrt(4) = 0.5`; 188
> values silently return 0.0; values 6 and 7 leave the poison intact (the store never ran). **An
> emitter must never set byte+3 bit 7 of `fspecial`.**

Per `FIELD-SWEEP-PROTOCOL` §8 ("after two genuine hangs in one area, STOP that arm") the whole arm
was stopped. This is reported PARTIAL, not rounded up.

**What this blocks:** `nir_op_frcp`, `frsq`, `fexp2`, `flog2`, `fsin`, `fcos`, `fsqrt` — i.e. every
transcendental lowering. `fspecial_est` is separately blocked (`dst` `untested`).

`iunary`/`ibitcount` do cover `nir_op_bit_count`, `ufind_msb` and `bitfield_reverse` (§1.3), so the
bit-manipulation corner is open even though the float-special corner is not.

### 3.6 The integer core — `iadd2` is one field short, and the two experiments disagree

`iadd2` — the 32-bit integer add/subtract, and by frequency the instruction a back end needs
second-most after `falu2` — has **13 of 14 fields at emitter grade**. The one holdout in
`validation.json` is `srcB_ext`, at `corpus-correlation` ("part of the scattered srcB register
number").

Two committed experiments disagree about that field, and this document does not pick a winner:

- **`EXP-0139`** swept it in a **32-bit** carrier and declined: *"`srcB_ext` remains blocked: only
  values 0–3 work and **no ≤4-bit rule explains the partition**."* Under that experiment's own
  stated promotion rule (≤1-bit rule → `hardware-run`; 2–4-bit rule → `isolated-byte-diff`;
  everything else → `untested`), no promotion follows.
- **`EXP-0146`** swept it in a **64-bit** carrier (`k_u64sub`) and promoted it: *"128 values tested
  (full 7-bit dense); ok at `{0x0-0x3}`; exact rule `(value & 0x7C) == 0x00`, free bits `0x03`."*
  That verdict is committed in `experiments/EXP-0146-m4-emit-int-misc/analysis/field_verdicts.json`
  and is keyed `iadd2.srcB_ext@u64sub`.

They are not obviously in conflict — a 5-bit mask rule is exactly what `EXP-0139`'s "no ≤4-bit rule"
excludes — but they were measured on **different operand widths of the same instruction**, and
`EXP-0146` states plainly that the byte making the operands 64-bit wide was *located but not
isolated*. **An implementer must not treat `iadd2` as emittable in the 32-bit form on the strength
of a 64-bit-carrier verdict.**

The other `EXP-0139` correction that matters here: **`EXP-0112`'s `r(R mod 64)` aliasing rule does
NOT transfer to `iadd2.dst`.** `dst = 140/141` is reg 70, which would alias r6 under that rule; r6
kept its sentinel. The sweep tests aliasing at exactly one point, and at that point it is refuted.

The rest of the integer core, and what it blocks:

| Instruction | Blocking | Blocks |
|---|---|---|
| `falu3` / `falu3_ext` | `op`, `srcB`, `srcC` `untested` | **`nir_op_ffma`** — fused multiply-add must be lowered to two `falu2`s |
| `icmp_pred` | `srcA`, `srcB` `untested`; `opclass` `corpus-correlation` | every integer/float comparison |
| `isel8`/`isel10`/`isel10_c`/`isel_reg`/`isel_reg8`/`icmpsel` | `cmpA`, `cmpB`, `cmp_mode`, `selTrue`, `selFalse`, `cc`, `flags` | `nir_op_bcsel` in its native fused-compare-select form |
| `imad` | `dst`, `srcB`, `srcC_lo`, `srcC_desc`, `mulsel` | `nir_op_imul`, `imad`, 64-bit multiply (which lowers to three `imad`s) |
| `ishift` | `srcA`, `opB` `untested` | `ishl`/`ishr`/`ushr` — though `shamt = n << 2` is confirmed 32/32 on hardware |
| `ibfe` | `dst` `corpus-correlation`, `b5` `tokenization-only` | `ubfe`/`ibfe` — see §4.1 for the trap that survives even so |
| `ibfins` | `dst`, `mask_imm`, `b6hi`, `b7`, `srcdesc`, `b10` | `bitfield_insert` |
| `ilogic` | 11 of 11 in `validation.json` | logic ops — **but see below** |
| `carry_gen` | 5 of 5 in `validation.json` | carry chains — **but see below** |
| `simd_ballot` / `simd_shuffle` / `simd_reduce` | 6 / 7 / 8 fields | all subgroup intrinsics |

**`ilogic` and `carry_gen` are the merge gap, not an evidence gap.** `EXP-0146` §3.3 established that
`ilogic` reaches **all 16 two-input boolean functions** with a collision-free selector
`(op_base, lut_a & 3, lut_b & 0x0f)`, **zero collisions**, one hardware-validated encoding per
function (table at `analysis/ilogic_lut_table.md`), plus field rules: `lut_a` bits 2–4 don't-care,
bits 5–7 must be clear; `outmod` has exactly one load-bearing bit (bit 7 = publish; every value with
it clear silently zeroes); `z6`, `z8`, `z9` HW-tested inert over all 256 values each. And §3.2
closed `carry_gen`'s operand model: it is `p[dst] = (r[byte+1] <u r[byte+3])`, a **two-operand
unsigned compare**, not a marker plus a source — closing the half of `INT-14` that `EXP-0102`
deferred by design.

**None of that reached `validation.json`.** The 94 committed `EXP-0146` verdicts are unmerged (§1.1).
An implementer reading `validation.json` alone will conclude that logic ops are unavailable; an
implementer reading `EXP-0146`'s `RESULTS.md` will find a complete 16-function LUT table. Both are
committed evidence. That inconsistency is itself a finding.

### 3.7 Memory ordering — deliberately not promoted, and rightly so

Six fence fields across `mem_fence`, `dev_scoreboard_fence`, `scoreboard_fence` and
`compute_fence_scoped` were swept densely and **deliberately left `untested`**. `EXP-0141` §0 H6 and
`EXP-0147` §2.5 both give the same reason: **neither carrier has a memory-ORDERING observable**, so
the sweeps bound acceptance and dataflow-inertness only. `EXP-0147` is blunt about the falsifier:
the pre-registered sensitivity control (corrupt the fence's own byte 0) **passed when it was
registered to fail**.

Two facts from those arms are worth keeping:

- `dev_scoreboard_fence` was **synthesised from scratch** into a validated load→ALU→store program
  (no own-MSL kernel we could compile emits `80 02 00 xx`), and all 256 `scope_flag` values execute
  and leave the surrounding dataflow exact.
- `compute_fence_scoped.mask` **breaks the result at exactly 10 of 256 values**
  (`0x00,0x08,0x0c,0x10,0x18,0x80,0x88,0x8c,0x90,0x98`), reproducibly. That live signal is named as
  the single highest-value follow-up in `EXP-0147` and was still not promoted.

`mem_fence8` is **not dispatchable at all**: it is emitted only by `intersection_query` traversal
and `agxrun_persist` cannot bind an acceleration structure. One new corpus fact came out of it — our
own compiled ray-query kernel emits `mask = 0x11`, which `db.json` does not list.

**What this means for a driver:** you can emit a `threadgroup_barrier` and rely on its
**execution-convergence** semantics (proven by a 256-lane litmus with a working falsifier). You
cannot yet emit a memory fence with documented ordering semantics. `EXP-0141` §5 states the bound
exactly: *"'Inert' always means inert on this observable. A byte that does not change a scalar
load's value may still change scheduling, latency, or behaviour under contention."*

### 3.8 Threadgroup addressing — an open cross-target divergence

`tg_addr_compute` has **zero blocking fields** and is still not emittable, and this is the one place
in the repository where an A18 result and an M4 result directly contradict each other on the same
literal bytes. `EXP-0141` H5:

> `EXP-M4-14` (A18) found byte0's high nibble live, with `0x1c` **and `0xfc`** reproducing the
> baseline. On M4, of all 256 values **only `0x1c`** — the compiler's own — leaves the tile dataflow
> correct; `0xfc` does **not** reproduce.

Byte+1 is likewise live (32 of 256 accepted: `{v : v & 0x03 == 2 and v & 0x10 == 0}`); bytes +2..+5
are inert. **Neither byte0 nor byte+1 is modelled as a field**, so there is nothing for an emitter to
fill. The veto stands, and the experiment names it as a reason to treat cross-target transfer in
this family with suspicion rather than to assume it.

---

## 4. The traps that will silently produce wrong code

**Read this section before any other.** On Apple9 a wrong operand-field value overwhelmingly
produces a **silent zero, not a fault** — so every trap below fails quietly, at run time, far from
its cause, with `STATUS OK`.

The general principle is stated normatively in `docs/evidence-classification.md` §5 (*"on Apple9 a
wrong operand-field value usually produces a silent zero, not a fault, so a wrong guess here fails
quietly and far from its cause"*) and was originally derived in `docs/isa/register-move-and-liveness.md`
§1.2 from `EXP-0087`, whose raw data shows **26 distinct `byte+2` values that deterministically zero
the destination** — *"They do not fault. They do not warn. The destination simply becomes zero."*
`EXP-0090` is the sharpest single demonstration: an entire hand-built program silently computed the
wrong answer because one 5-bit `mod` field was 1 instead of 3.

There is a worse variant. `EXP-0141` §2 documents **`STATUS OK` with nothing executed**: under
sibling GPU load a command buffer can report success while the output buffer stays at its
zero-initialised contents. *"On this ISA an all-zero readback is the expected signature of a wrongly
encoded field, so the artifact forges a real-looking negative."* It corrupted `EXP-0141`'s
pre-registered baseline during smoke. **A driver's own test suite must therefore write a sentinel
through an independent path**, exactly as the experiments do — an all-zero result cannot distinguish
"wrong encoding" from "nothing ran".

### 4.1 `ibfe`: `offset` is LITERAL, `width` is MOD 32, and the hardware does not implement NIR's masking

`EXP-0139` §1.4, dense 0..63 on both fields, on a single-`ibfe` carrier (`o = extract_bits(a,4,8)`):

- **`offset` is LITERAL.** Values 0–31 shift normally; values **32–63 shift the field out entirely
  (result 0)**. The literal model fits **64/64** stable values; a mod-32 model fits only 32/64.
  **The hardware does not implement NIR's "mask offset mod 32."** A back end must mask in software.
- **`width` is TAKEN MOD 32** — and this **refuted the model the experiment itself
  pre-registered**. "Literal, clamp at 32" fits only **37/64**; `width mod 32` fits **64/64**.
  `width ≡ 0 (mod 32)` is the no-mask (extract-to-MSB) case, so `width = 32` behaves exactly like
  `width = 0`.

**Two opposite out-of-range rules on the same instruction.** An emitter that applies one convention
to both fields is wrong half the time, silently, in 32 of 64 offset cases.

Two caveats to carry: `EXP-0102` reached the same conclusion from Metal's *compiled sequence* and
additionally found a `cnt == 32` special case where the offset is **ignored entirely**; and
`validation.json`'s own note on both fields records that **the adversarial second carrier
(`IBFE_SH`, a different lowering) DIFFERS** — only `width_lo` agrees. The rule is
single-carrier-established.

### 4.2 Normalized-integer rounding is not uniform — there are three different rules

| Path | Rule | Evidence |
|---|---|---|
| `unorm8` **storage** | ties round **half-UP** — 2.5/255 → `0x03` | `EXP-0079` |
| `unorm16` **storage** | ties round **half-DOWN** — 1.5/65535 → `0x0001`, 2.5/65535 → `0x0002` | `EXP-0133` H2 |
| `pack_float_to_unorm2x16` (**ALU** pack) | ties round to **nearest-EVEN** | `EXP-0144` H5 |

`EXP-0133` H2 verbatim: *"unorm16 tie-breaking is round-half-DOWN, the OPPOSITE convention from
unorm8's round-half-up (EXP-0079). NEW finding, falsifies the extended-textbook H2 hypothesis
registered for this run. […] Both exact-tie probes round DOWN […] which **neither round-half-up nor
round-half-even predicts**."* A non-tie control (5.9/65535 → `0x0006`) refutes plain truncation, and
the result was cross-checked inside one 4-channel store.

`EXP-0144` H5 then found the **ALU pack path rounds differently again** — all 16 pack semantic
vectors matched a round-to-nearest-even oracle exactly, including three exact ties built with
`Fraction` arithmetic, and the competing "ties round down" model registered from `EXP-0133` was
**refuted for that instruction**. Verbatim from `EXP-0144`: *"The ALU pack path and the PBE store
path round differently."*

`snorm16` **does** follow `snorm8`'s symmetric `round(c × 32767)`. So: three distinct rules, and
**none may be reused for another**. Attribute the nearest-even claim to `EXP-0144`'s revalidated
`rv01` pair specifically, not to its original (retracted) runs.

### 4.3 Mesh grid amplification dies at exactly 65,536 while Metal advertises 1,048,576

`EXP-0135` §4.1, on a 64×64 target, `mesh_grid_properties::set_threadgroups_per_grid`:

| amplification | rendered |
|---|---|
| 1 / 2 / 4 | 15 / 30 / 60 px |
| 64 … 65,535 | 917 px (saturated) |
| **65,536** | **0 px** |
| 65,537 … 1,048,576 | 0 px |

Verbatim: *"The reflected ceiling (1,048,576) and the real behavioral ceiling (65,535) differ by a
factor of 16, and **the real ceiling fails SILENTLY** — no compile error, no pipeline error, no
command-buffer error; `STATUS OK` and `CMDBUF_STATUS 4` (Completed) every time, with zero rendered
output. […] a driver that trusts `maxTotalThreadgroupsPerMeshGrid`'s reflected value for validation
will pass through amplification counts that silently produce nothing on real hardware."*

Not a wraparound: 65,600 renders 0, not the 16 px that `65,600 mod 65,536 = 64` would give. It is a
hard cutoff. Independently reproduced on the **unrelated top-level indirect-draw mesh-grid
mechanism** (§6). 65,536 = 2^16 is *consistent with, but not proven to be*, a 16-bit internal count
field, and the experiment states honestly that a Metal-runtime software cap cannot be distinguished
from a silicon limit from userspace alone.

Same experiment, adjacent: the object→mesh payload ceiling is exactly **16,384 B**, enforced
**loudly** at pipeline creation (16384 builds, 16385 fails) — while `payloadMemoryLength` accepts
values *smaller* than the declared struct with **no validation at all**.

### 4.4 `tile_read`'s read-enable returns a black tile rather than faulting

`EXP-0147` §2.2, and `validation.json :: tile_read.read_en`:

> byte+6 bit0 is a READ-ENABLE — all 128 ODD values give the correct read and all 128 EVEN values
> give a SILENT ZERO (the pixel collapses to the no-read oracle); bits 1–7 are don't-care. Identical
> on `tile_read` and `tile_read_mrt`. The field was typed `raw` with no semantics; **in a BG/EOT
> program a wrong value surfaces as a BLACK TILE, not a loud failure.**

The same silent-zero behaviour applies to a wrong `rt_index` (only `0x00,0x01,0x80,0x81` work with
one attachment bound), a wrong `dst`, and a wrong `fmt` on the MRT variant (104 of 256 values give a
silent zero). `EXP-0147` §2.2: *"an emitter that gets `rt_index`, `dst`, `b6` or `fmt` wrong does not
get a fault — it gets a silent zero."*

### 4.5 An invalid attachment `slice` destructively zeroes slice 0

`EXP-0132` §2.3 (H3), case `l4-array-slice-invalid`, requested `slice = 4` against a valid range of
`[0,4)`:

> An out-of-range **slice** does not simply vanish or alias into the requested (invalid) index — it
> **zeroes slice 0's existing content** (destructive: the pre-render canary at slice 0 is
> overwritten with `0`, even though slice 0 was never the render target) […] a true
> `slice % arrayLength` wraparound would have produced the actual clear colour, not zero.

Canary `a0a0a0a0` at slice 0 → reads `00000000`; slices 1–3 untouched. `cb_status = 4` (Completed),
no error — *"the API neither rejects nor aborts."*

**An out-of-range `level`, by contrast, is a true no-op** with no observable effect in any valid
level (control `m3-mip-level-invalid`, `level = 3` against `mipCount = 3`). Two adjacent
out-of-range conditions, two completely different behaviours, neither of them a fault.

Companion negative from the same experiment: slice and mip are **not encoded in the per-attachment
descriptor record** (byte-exact negative), so the mechanism carrying slice selection is undecoded —
*"there is no descriptor-level explanation available."* A driver must range-check the slice itself,
because nothing downstream will.

### 4.6 `mov_imm` above 127 does not write at all — and eats the next instruction

**This is a preserved retraction.** `EXP-0128` reported immediates 128..255 as a "silent zero".
`EXP-0140` §4 refuted the mechanism while confirming the conclusion:

> **`mov_imm` with `imm_top = 1` does not write the destination at all.** EXP-0128 read immediates
> 128..255 as a "silent zero"; **that reading was made against a zero-initialised read-back
> buffer.** Against a **poisoned** buffer the paired control settles it: with 4 bytes of inert
> padding after it the destination keeps its previous value (7, not 0); **without padding the
> following 2-byte instruction is consumed** and the read-back store addresses the wrong word. An
> emitter must treat the immediate as **7 bits**; bit 7 selects a different, longer instruction
> rather than extending the immediate.

`EXP-0128`'s *conclusion* (the immediate is 7 bits) stands; its *mechanism* is wrong.
`PROVENANCE.md` carries the correction inline. Combined with `iadd2`'s N = 0 self-read, this
produced **two real GPU hangs** in `EXP-0128`'s pilot.

⚠️ **Do not cite `validation.json` for this row.** Its notes on `mov_imm.imm7` (*"Values 128..255
SILENTLY ZERO"*) and `mov_imm.imm_top` (*"it silently zeroes the whole move"*) still carry the
refuted `EXP-0128` mechanism and were never updated for `EXP-0140`. Cite `EXP-0140` or
`docs/isa/README.md`.

### 4.7 `mov_imm` with `imm7 == 12` does not tokenize

`EXP-0140` §4 item 4:

> `mov_imm` with `imm7 == 12` does not tokenize under the current length rule (byte+1 = `0x0C` makes
> the 2-byte pair look like the 4-byte `0x?c` preamble group). **It is the only immediate in 0..127
> with this property**, checked exhaustively over all 16 `dst` values. **This is a decoder defect;
> whether the hardware agrees was not tested.** Every immediate this experiment emits avoids 12.

The offending encoding is `6c 0c`. It is a `tools/agx-isa` length-rule defect, not a hardware claim,
and `EXP-0148` — which corrected the general length rules and lifted corpus tokenization from 803 to
832 clean files — **does not resolve it**. A back end that wants to keep its own disassembler honest
should route the constant 12 through `uniform_mov` instead.

### 4.8 `matrix_mac` computes `A·B − C` unless `(b11hi & 3) == 0`

`EXP-0147` §2.1, `b11hi` = byte+11 bits 1–7, all 128 values swept twice:

| `b11hi & 3` | rows 0–3 | rows 4–7 | operation |
|---|---|---|---|
| `0` | `+C` | `+C` | `A·B + C` — the only mode Metal emits |
| `1` | `−C` | `+C` | half-tile subtract |
| `2` | `−C` | `−C` | **`A·B − C`** |
| `3` | `+C` | `−C` | half-tile subtract, opposite half |

Only **32 of 128** values give the documented `A·B + C`; bits 2–6 are don't-care. Paired with
`dst_desc`, where **128 of 256 values silently zero**, this instruction has two independent ways to
be quietly wrong.

(Do not conflate with the M5 datum in `docs/hypotheses.md`: `m5_matrix_mac` byte+13 bit 6 gives
`−(A·B) + C` — a *different* bit, a *different* operand, and a different target. Neither transfers.)

### 4.9 The traps that are not about fields at all

- **A persistent render runner that builds its `MTLFunction` from source returns the baseline pixel
  for every splice**, because Metal memoizes native code per AIR identity. `EXP-0147` §4 verified
  this by contradiction — one-shot processes gave four different pixels where the persistent runner
  gave one — and warns: *"Any future fragment-stage sweep that skips this will silently conclude
  that every field is inert."*
- **Reusing one splice-archive filename across persistent-runner requests produced 28 of 360
  spurious `CMDBUF_ERROR`** on byte-identical, known-good archives; a unique path per request gave
  0 of 360 (`EXP-0141` §2).
- **A GPU fault poisons subsequent command buffers** with
  `kIOGPUCommandBufferCallbackErrorInnocentVictim`. Restarting the child process first makes the
  fresh child's first request the next victim — `EXP-0147` §4 produced **138 consecutive false
  `invalid_run`s** that way. Retry in place.
- **Patching a descriptor between two dispatches silently reverts.** `EXP-0136` §0: *"the descriptor
  pool entry is not stable, externally-patchable memory across re-encodes of the same object —
  Metal re-materializes it on every bind."*

---

## 5. Capabilities Metal never emits, that a driver could exploit

These are the payoff of the extrapolate-and-test method. Each is a hardware capability found by
perturbing a field the database called opaque, and each is unreachable through Metal.

### 5.1 A native single-instruction 64-bit integer ADD — `EXP-0146` §3.1

`k_u64sub.metal` (`out[gid] = a[gid] - b[gid]` on `ulong`) compiles to
`get_sr, device_load, device_load, iadd2, device_store, stop` — **one** arithmetic instruction, bytes
`1f 01 56 00 02 08 00 50 17 05`. Changing **only byte0 bit 7** (`0x1f` → `0x9f`, the add/subtract
selector) produced `(a + b) mod 2^64` **exactly, on every row, in both gated runs**, and again on an
independently chosen boundary set in 5/5 repetitions:

| a | b | observed |
|---|---|---|
| `0xFFFFFFFFFFFFFFFF` | `0x1` | `0x0` (full 64-bit wrap) |
| `0x8000000000000000` | `0x8000000000000000` | `0x0` (carry out of bit 63) |
| `0xFFFFFFFF00000000` | `0x00000000FFFFFFFF` | `0xFFFFFFFFFFFFFFFF` |
| `0x0123456789ABCDEF` | `0x00000000FEDCBA98` | `0x0123456888888887` (**lo→hi carry propagated**) |

The kernel contains exactly one arithmetic instruction, so the carry across the 32-bit word boundary
is produced **inside that instruction**. **Apple's compiler emits a 5-instruction chain instead.**

Emitter rules for the 64-bit form (`EXP-0146` §3.4): `dst` (byte+3) `{0x00,0x01}` ok, **`0xBE..0xFF`
(reg ≥ 95) FAULT**; `srcA` (byte+7) `{0x50,0x54}`, **every `v & 3 == 3` FAULTS** (64 values);
`opmode` (byte+4) `(v & 0x02) == 0x02`; `opc_tail` `(v & 0x11) == 0x11`; `opc_tail2`
`(v & 0x05) == 0x05`; `srcB_imm` `(v & 0xFC) == 0x08`; `lenbit` 1 = 10-byte form, 0 **faults**;
`store_en` 1 = publish, 0 silently zeroes.

**Limitation the experiment states and this document keeps:** it was validated in one carrier shape
— the compiler's own 64-bit subtract with one bit flipped — **not synthesized from scratch**. The
byte that makes the operands 64-bit wide was *located* (byte+7 is `0x50` here vs `0xA8` in the
byte-identical-otherwise 32-bit form) but **not isolated**, because changing it also changes which
register is read. `EXP-0146`'s own top follow-up is to synthesize it from scratch.

Adjacent answers from the same experiment (`analysis/I64_answers.md`): **I64-02 YES** (one
instruction, borrow included); **I64-04 YES** (single `imad`, one byte apart signed vs unsigned);
**I64-05 YES** (no native 64×64→low64 — three `imad`s); **I64-06 YES** (compare / shift / min-max /
bit-scan / select are all compound, with the measured sequences). All nineteen 64-bit kernels were
functionally exact against host oracles.

### 5.2 Sampler anisotropy to 128× against Metal's 16× cap — `EXP-0136`

The sampler descriptor's **byte2 bits[4:6]** are a **3-bit log2 field**: `nibble = log2(aniso)`,
codes 0–7 = 1× … 128×. Metal exposes only codes 0–4.

Measured `pixel[0]` red channel, 16/16 cases, byte-identical across both gated runs (0.498 ≈ 127/255
= fully blurred/mip-averaged; 1.000 = fully resolved):

| dPdx:dPdy ratio | aniso16 | patched 32 | patched 64 | patched 128 |
|---:|---:|---:|---:|---:|
| 16 | **1.000** | 1.000 | 1.000 | 1.000 |
| 64 | 0.498 | 0.498 | **1.000** | 1.000 |
| 128 | 0.498 | 0.498 | 0.498 | **1.000** |

Sharpness flips crisp exactly when `patched_aniso ≥ ratio`. Verbatim: *"This is not 'doesn't fault'
— it is a measured, monotonic, threshold-exact quality effect […] **AGX9 sampler hardware natively
supports anisotropic filtering up to at least 128× (the full range of the 3-bit log2 field). Metal's
16× cap is a pure software/API ceiling with zero hardware backing.**"*

Tested range: ratios 16 / 64 / 128 only — finer-grained sweeps (20:1, 48:1) were not run.

### 5.3 The matrix unit's subtract-accumulate — `EXP-0147` §2.1

See §4.8 for the table. The same two bits that are a trap for `A·B + C` are a **capability** for
anything that wants `A·B − C` or a half-tile sign split: *"the matrix unit performs `A*B - C`
(matrix multiply-subtract), and a half-tile variant, neither of which
`simdgroup_multiply_accumulate` ever emits."*

### 5.4 `uniform_mov` materialising 7-bit immediates — `EXP-0140` §1.5

`usrc >= 0x80` materialises the immediate `usrc & 0x7F` into the destination GPR — a 7-bit immediate
move, **not** a uniform read. 128/128 immediate-region values matched a host-computed oracle
exactly. The instruction was documented as a uniform-register read only. It gives a back end a
**second** independent constant-materialisation path alongside `mov_imm`, on a different opcode
group — useful for scheduling and, concretely, for routing around the `imm7 == 12` tokenizer defect
of §4.7.

### 5.5 The rest of the "hardware can, Metal doesn't" register

From `docs/hypotheses.md` and `docs/capability-matrix.md` §1 (20 native capabilities, 5 added
2026-08-28, **all five `target: G16G`**):

- **`falu2`'s inline 8-bit float immediate** (`EXP-0138`) — §1.3. The single largest of the set,
  because `falu2` is the most-used instruction in the ISA.
- **`ilogic` is a full 16-function two-input LUT** (`EXP-0013`, refined by `EXP-0146` §3.3 to all 16
  with a collision-free selector and one HW-validated encoding per function). **Every Vulkan/GL
  logic op is one native instruction.**
- **`pack_convert` byte+9 reaches a pack format the compiler never emits** (`EXP-0144`):
  `0xC2/C6/CA/CE` is an 8-bit unorm-lane pack (scale 255) *"that the compiler never emitted here"*.
- **A find-MSB primitive Metal does not name** (`EXP-0033`): `a7 05 56`; clz/ctz lower from it.
- **Float round modes** as a field (`EXP-0013`): `0x2f`/`0xaf` byte+8 — 0 = nearest, 2 = floor,
  4 = ceil, 6 = trunc.
- **Programmable MSAA sample positions are userspace-emittable** (`RT-4`, correcting `EXP-0021`):
  client BO at +0x40, N `(x,y)` f32 pairs on a 1/16 grid.
- **Primitive restart** fires *"at exactly and only the all-ones sentinel; adjacent values are used
  as literal out-of-bounds indices with no fault"* (`EXP-0136`). A *custom* restart index remains
  Metal-unreachable.

**And the high-value negatives, which are equally deliverable:**

- **Geometry shaders and transform feedback do not exist** (`EXP-0136`, `target: G16G`):
  *"`rasterizationEnabled = NO` runs the vertex stage on the same VDM/tiler path with the fragment
  stage merely elided. GL/Vulkan GS and transform feedback must be **permanently emulated**."*
- **There is no fourth sampler border colour** (`EXP-0136`): the unused 2-bit code aliases to preset
  0 from every creation context. Arbitrary RGBA border colours must be emulated.
- **MSL `[[barycentric_coord, center_perspective]]` is a NO-OP** (`EXP-0137`): both qualified
  spellings produce identical disassembly. *"There is no MSL-level escape hatch"* — a driver must
  normalize the numerators itself.

---

## 6. The honest gap list, ranked by how much it blocks

| # | Gap | Blocks | Class | Cheapest close |
|---|---|---|---|---|
| 1 | **No validated GPR-to-GPR move** | `nir_op_mov`, phi lowering, parallel copy, RA coalescing, spill reload | EVIDENCE — the `reg_move` family is *not* the instruction; the real one has not been found | A dedicated search for a GPR→GPR move, the way `EXP-0139` found `iunary` by searching the `0x27` encoding space. `EXP-0087` §1.5 already shows why the corpus won't hand it over: of four authored contexts, **two emit zero instances**, and only a genuine loop-carried phi produced real ones — neither a textbook plain-GPR-source move. |
| 2 | **Control flow: `jump_cond` carrier liveness** | `nir_loop`, real-branch `nir_if`, `nir_jump_break`/`continue` | EVIDENCE, and **cheap** | A carrier whose conditional-branch target is observable. `EXP-0140` estimates one more complete capture would also take `jump`, `ret`, `pop_reconverge`, `if_push_pred` to emittable (18 of 23 in that family). |
| 3 | **Texture sampling operands** | all of `nir_tex`, `nir_image_*` | EVIDENCE | Seeded-register carriers for `tex_sample.coord` / `result_sel` / `result_desc` and for `tex_write`'s eight `untested` fields. `tex_addr_setup` is already emittable, so the setup half is done. |
| 4 | **Fragment colour output + varying interpolation** | fragment `nir_store_output`, `nir_load_interpolated_input`, VS `nir_store_output` | EVIDENCE | `frag_color_store.store_mode` needs one carrier that varies it (130/130 corpus instances show `0x54`); `iter`/`iter_at` need a fragment carrier at all. |
| 5 | **44 operand- and condition-selector fields** across `isel*`/`icmpsel`/`imad`/`iminmax`/`ishift`/`icmp_pred` | integer compare, select, multiply, shift | EVIDENCE — `EXP-0139` §2 diagnoses it precisely: a single-carrier splice sweep can prove a field is live and enumerate which values keep the program correct, *"but it cannot establish the value → register-number mapping, because every wrong value points at a register the carrier never seeded"* | A **seeded-register carrier per family**, the way `EXP-0139`'s own `iadd2` and `ibitcount` arms were built. `EXP-0139` names this "the single highest-value follow-up". |
| 6 | **`EXP-0146`'s 94 committed field verdicts are not in `validation.json`** | `ilogic` (all 16 logic ops), `carry_gen`, `iadd2`, `irotate`, `mov_zext16`, `n2_op6/8/10`, `n3_mov`, `shift_amt_move` | **BOOKKEEPING** — the evidence exists and is committed | A merge pass, with a ruling on the 32-bit vs 64-bit carrier question for `iadd2.srcB_ext` (§3.6). This is desk work and it moves nine descriptors. |
| 7 | **Atomic op-selector field model** | every `nir_intrinsic_*_atomic` | **MODELLING** — the op *byte* was swept 256/256 with `0x36` = `sub` verified by value; the DB's split into `op_lsb`/`op`/`per_lane`/`op_msb` is what has no semantics | A `db.json` field-model fix plus a sweep that varies the sub-fields independently rather than the byte. |
| 8 | **`falu3` (FMA) operands** | `nir_op_ffma`; every fused-multiply lowering | EVIDENCE — blocked by a *measurement artefact*: `EXP-0138` §9 shows the sweeps were destroyed by their own success, since reading a GPR as a 32-bit source through these slots **zeroes that register afterwards** (release-on-read), tripping the integrity sentinel | Re-run the six sweeps *"with the sentinel routed through a register no descriptor value can name"* — `EXP-0138`'s own prescription. |
| 9 | **Transcendentals (`fspecial`)** | `frcp`, `frsq`, `fexp2`, `flog2`, `fsin`, `fcos`, `fsqrt` | EVIDENCE, but **hazardous** — arm stopped after 3 reproduced GPU hangs | A carrier that can reach the fields without byte+3 bit 7, under a hang budget. Low priority against #1–#5. |
| 10 | **Memory-ordering observables** | documented fence semantics | **EVIDENCE-BY-DESIGN** — six fields swept densely and deliberately not promoted, because neither carrier has an ordering observable | A real ordering litmus (message-passing / store-buffer). `compute_fence_scoped.mask` already shows a live signal at 10 of 256 values. |
| 11 | **Subgroup ops** (`simd_ballot`/`shuffle`/`reduce`) | all subgroup intrinsics | EVIDENCE | Not yet attempted in the emitter wave. |
| 12 | **`tg_addr_compute` model + G16G↔G17P divergence** | threadgroup-memory addressing | **MODEL DEFECT + open divergence** (§3.8) | Model byte0/byte+1 as fields first; a sweep is meaningless until then. |
| 13 | **`op04_len8` length rule** | tokenizer correctness; `emit_unsafe` stands | OPEN — `EXP-0148` demonstrated the over-consumption and eliminated **six** candidate rules, all measuring *worse* than the status quo | `EXP-0148` §7 hands over two designed-but-undone hardware probes (`HW-LEN-1`, `HW-PREP2`) with exact splice points and predicted outputs. |
| 14 | **Scratch / helper-program ABI (P0.1)** | any shader that spills beyond the register file | **PLATFORM** — three methodologically different probes returned the same negative | `work/P0-P1-GAP-ANALYSIS.md` P0.1: not closable by more probing from macOS userspace. What *is* known and usable: a HW-validated **stage-uniform compile-time ceiling of 261,740 B declared scratch** (bisected to 4-byte resolution, identical for CS/VS/FS), a clean `nil` rejection above it, and silent numerical corruption above `n_queues ≈ 8` with a session-variable onset (`n_queues ≤ 4` tested clean, 12/12, both runs). |
| 15 | **Provenance chain holes** | auditability, not code | BOOKKEEPING | `EXP-0138`, `EXP-0144` and `EXP-0147` have committed `RESULTS.md` but **no `PROVENANCE.md` row** — including `matrix_mac`, `tile_read` and the `falu2` minifloat immediate, three of the most load-bearing results in this document. `work/P0-P1-GAP-ANALYSIS.md` §0.3(b) lists seven more. |

**Two stale artefacts an implementer will trip over, both listed here so nobody propagates them:**

- `validation.json`'s `mov_imm.imm7` / `imm_top` notes still carry `EXP-0128`'s **refuted** "silently
  zero" mechanism (§4.6).
- `docs/isa/agx3.xml` still models `matrix_mac`'s `b11hi` as *"inferred / not yet bit-decoded"* at
  bits 90:95; it has not been regenerated since `EXP-0147` decoded it (§4.8).
- `docs/P0-P1-CLOSURE.md`'s P0.6 row quotes **"345/1036 fields = 33.3 %; 28 of 171 instructions
  emittable"**, which predates the emitter wave. `validation.json` is the current authority.

---

## 7. Target status — which silicon each section is actually about

**Read this before transferring anything.**

### 7.1 The measured split

Of the **443 emitter-grade fields** in the committed `validation.json`:

| `target` | fields | share |
|---|---|---|
| `M4` (G16G) | 350 | 79 % |
| `A18` (G17P) | 84 | 19 % |
| `M4+A18` | 9 | 2 % |

So the common shorthand "all current evidence is M4/G16G" is **not literally true**, and the
exception matters: **five of the 38 emittable instructions are measured entirely on A18/G17P and
never on M4** — `frame_prologue`, `link_save_restore`, `spill_frame_marker`, `stop`,
`tex_addr_setup` (from `EXP-M4-14`, `EXP-0003`, `EXP-0010`, `EXP-0035`, `EXP-0038`, `EXP-0041`).
`matrix_mac` is 10 A18 fields to 2 M4. Everything in §1.3's memory, integer, mov/select, tile-buffer,
barrier and conversion rules is **M4/G16G**.

### 7.2 Per-section target

| Section | Target of the evidence |
|---|---|
| §1.3 `device_load` / `device_store` / atomics / barrier | **M4 / G16G** (`EXP-0141`, `EXP-0082`, `EXP-0083`, `EXP-0092`) |
| §1.3 `falu2` | **mixed** — `mod_lo`, `srcA_reg`, `srcB_reg`, `ctrl`, `opflags`, `mod_hi`, the reg-top bits: M4. `opsel`, `srcA_size`, `srcB_size`, `srcB_imm`: **A18** |
| §1.3 `mov_imm` / `uniform_mov` / `sel` / `psel` / `if_push` / `reg_move_*` | **M4 / G16G** (`EXP-0140`) |
| §1.3 `ibitcount` / `iunary` | **mixed** M4 (`EXP-0139`) + A18 (`EXP-M4-14`) |
| §1.3 `tile_read` / `tile_read_mrt` / `pixel_order` / `vtx_*` / `n3_sample_read` | **M4 / G16G** (`EXP-0147`) |
| §1.3 `matrix_mac` | **A18** for 10 fields (`EXP-O2C`, `RT-10`), **M4** for `dst_desc` and `b11hi` (`EXP-0147`) |
| §1.3 `cvt_*` / `pack_convert` / `unpack_convert` | **M4 / G16G** (`EXP-0144` rv01 only) |
| §1.3 frames, `stop`, `tex_addr_setup` | **A18 / G17P** (`EXP-M4-14` and the EXP-0001–0046 wave) |
| §2 the compilable envelope | **M4 / G16G** (`EXP-0112`, `EXP-0090`) |
| §3 all blockers | label state is target-agnostic; the underlying sweeps are as above |
| §4 all traps | **M4 / G16G** — items 4.1–4.8 without exception |
| §5.1 64-bit add | **M4 / G16G** (`EXP-0146`); the `RT-1a-FIX` add/subtract polarity it builds on is A18 |
| §5.2 anisotropy 128× | **M4 / G16G** (`EXP-0136`) |
| §5.3 matrix subtract | **M4 / G16G** (`EXP-0147`) |
| §5.4 `uniform_mov` immediates | **M4 / G16G** (`EXP-0140`) |

**Nothing in this document is promoted across targets.** `CODEX.md`'s target discipline requires a
recorded validation or an explicit `INFERRED` label; a silent relabel is a defect.

### 7.3 The pivot, and what is in flight

The test target has moved to the **A18 Pro / G17P** (`experiments/NEO-TARGET-BRIEF.md`, 2026-08-28;
`Mac17,5`, `AGXAcceleratorG17P`, arch `applegpu_g17p`, 5 GPU cores, macOS 26.6, Metal family Apple9,
full Xcode). The brief states the evidence consequence directly: *"A result measured here is
**direct**, not `INFERRED` […] Committed M4/G16G results stay valid on their own target but **no
longer satisfy a closure row by themselves**."* It also reports that the DB transfers — a compiled
`a[i]*2+1` kernel on G17P gives `get_sr · device_load · falu3 · device_store · stop` with **0
leftover bytes** — *"so the port is a change of target, not a restart."*

**`EXP-0153-g17p-revalidation` is IN FLIGHT and entirely uncommitted** (`git status`: untracked;
`git log` for that path returns nothing). Its frozen `PRE_REGISTRATION.md` covers 7 arms, 1,958
cases per run and 15 numbered hypotheses, each with a refuter — including `device_load`'s
`dst_lo`/`dst_ext9`/`extmode` rules, `falu2.mod_lo` and the minifloat immediate, the `iadd2` 64-bit
add, the register-aliasing boundaries, `ibfe`'s two out-of-range rules, `mov_imm`'s 7-bit immediate,
and the `EXP-0148` length rules against a G17P-compiled corpus rebuild. Its `raw/`, `analysis/` and
`work/` directories are empty: **zero gated captures exist.**

Its smoke run reports early signals consistent with the M4 model — the `k_u64sub` anchor tokenizes
to `EXP-0146`'s exact M4 bytes `1f015600020800501705`; `dst_lo`/`dst_ext9` 0 fails and 1 works;
`falu2 mod_lo = 1` gives 3.0 as the M4 model predicts; `mov_imm imm_top = 1` padded leaves the
destination at its previous value 7. It also reproduces the `imm7 == 12` tokenizer defect with the
same `db.json`, confirming that hole is **tooling, not target**.

**None of that is evidence.** Do not cite `EXP-0153` for any G17P claim until it is gated and
committed.

### 7.4 Two live contradictions in the repository's own governance

Both are stated because an implementer reading `docs/` will meet them:

1. **`CLAUDE.md` and the newer artefacts disagree about the test target.** `CLAUDE.md` still records
   the A18 Pro as **HANDS-OFF** at `192.168.170.254` with the M4 as sole test target (user directive
   2026-08-27). `CODEX.md`, `NEO-TARGET-BRIEF.md`, `docs/P0-P1-CLOSURE.md`'s importance box and
   `EXP-0153`'s pre-registration all assert the opposite pivot (2026-08-28/30), with *"Local M4 GPU
   testing is RETIRED."* `CLAUDE.md` has not been updated to match.
2. **The `EXP-0119` A18↔M4 contradiction is cited as unresolved and has in fact been resolved.**
   `docs/evidence-classification.md` §3 and `validation.json`'s `_conventions.target` both say *"The
   `EXP-0119` A18↔M4 contradiction is unresolved, so silent generalization is a defect."*
   `EXP-0129` §3.2/§3.3 resolved it: **"RESOLVED as (iii), a context difference — specifically
   OPERAND PROVENANCE, not dispatch shape"**, with the conclusion that *"there is no evidence of a
   genuine G17P-vs-G16G microarchitectural difference or an error in either record."* (`EXP-0129`
   also corrected `ibitcount`'s real release control to `srcdesc` bit 4, not `cache`/bit 17.) The
   two documents are stale; the *policy* they justify — never transfer silently — is unaffected, and
   a genuinely open divergence does exist, in `tg_addr_compute` (§3.8).

### 7.5 Version pinning for this document

Everything above is read from the repository at commit **`ff99bb52`**, with
`tools/agx-isa/validation.json` at `db_sha256 eaca7256…` (`generated: 2026-08-28`, 171 instructions,
1036 fields, 38 emittable).

**An uncommitted revision of `tools/agx-isa/db.json` and `validation.json` exists in the working
tree** as this is written. It splits several fields the emitter wave decoded — `matrix_mac.b11hi` →
`dst_desc_lo`/`dst_en`/`c_neg_half`/`c_neg_all`/`b11_rsv`, `tile_read.b6` → `read_en`/`b6_hi` — and
raises the field count from **1036 to 1057** (`hardware-run` 349 → 368, emitter grade 443 → 462 =
43.7 %). **The emittable set is unchanged at the same 38 mnemonics.** Where this document names a
field, it gives the post-split name if the split is the clearer statement of the rule (e.g.
`read_en`), and says so.

---

## 8. Clean-room provenance

```
Clean-room provenance: DESK ANALYSIS over committed artifacts only
Inputs inspected: CLAUDE.md, CODEX.md, docs/evidence-classification.md,
  docs/P0-P1-CLOSURE.md, docs/isa/README.md, docs/isa/register-move-and-liveness.md,
  docs/capability-matrix.md, docs/hypotheses.md, PROVENANCE.md,
  tools/agx-isa/{db.json,validation.json}, work/{UNATTENDED-RUN.md,P0-P1-GAP-ANALYSIS.md,
  DOC-02-LABELLING-REPORT.md}, experiments/NEO-TARGET-BRIEF.md, and the committed
  README.md / RESULTS.md / analysis/*.json of EXP-0079, 0082, 0083, 0086, 0087, 0089,
  0090, 0092, 0101, 0102, 0104, 0112, 0113, 0115, 0119, 0128, 0129, 0132, 0133, 0135,
  0136, 0137, 0138, 0139, 0140, 0141, 0144, 0146, 0147, 0148, EXP-M4-13, EXP-M4-14,
  EXP-O2C, RT-1a-FIX, RT-4, RT-7, RT-10.
Apple binary introspection: NONE. No hardware was touched; no device was contacted;
  no experiment was run. This document establishes no new fact.
Reproduction: every claim carries its EXP-NNNN; the field tables are readable from
  tools/agx-isa/validation.json at db_sha256 eaca7256... .
Evidence: as cited inline. Where a claim rests on an uncommitted or in-flight
  experiment (EXP-0142/0143/0145/0149-0159, EXP-0153), it is labelled IN FLIGHT and
  is not used as evidence for anything.
```
