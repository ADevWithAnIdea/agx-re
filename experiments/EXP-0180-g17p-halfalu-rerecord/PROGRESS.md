# EXP-0180 — PROGRESS

Append-only. Timestamped per milestone. Written so a kill costs at most one milestone.

---

## M1 — 2026-08-30 — target set resolved, spans re-checked, db PINNED. No device touched.

**Pinned inputs (frozen before any build):**

| file | sha256 |
|---|---|
| `work/frozen/db.json` (copy of `tools/agx-isa/db.json`) | `a77f8cfa163fcf720c0c1093e4ddc5815ceb43c218bb64a87c86d3dcf975dc22` |
| `work/frozen/isadb.py` | `9cda47a1d4b3857c9f20423ab5d63c38050d37220da06bc5d2dc12a77d6ef1a8` |
| `tools/agx-isa/validation.json` (read-only) | `a30309f0bf0004085b8327de2eaeeae9f987a7b930961b303c654aa9764c9bc9` |

`validation.json.db_sha256 == a77f8cfa…` — the pinned db **is** the one the live label
table was generated against. **This experiment resolves `isadb` explicitly to
`work/frozen/`; the path fall-through that silently picked up the neo's stale shared copy
for a sibling experiment is removed, not merely reordered.**

Repo revision at pre-registration: `db7c3c957a8788b8589978a48c044b049dde2cc2`, working tree
dirty (25 unstaged/untracked paths, all sibling experiments). Per `SUBAGENT_BRIEF.md` the
gate is the **authored blob hashes**, not live `HEAD`.

**Target set (`analysis/target_rows.py` → `work/target_rows.json`):**

* **25 row-claims over 16 DISTINCT FIELDS.** The 9 `EXP-M4-14` rows are a **strict subset**
  of the 16 rows EXP-0169 held; the union is 16, not 25. Nine fields therefore carry two
  independent claims each and get two verdicts each.
* **0 spans moved** since EXP-0169 measured them; 0 fields absent from the pinned db.
* `EXP-M4-14` is cited by **46 rows across the whole db**; only 9 are in this family.

**Current committed state of the 16 (this is what a run must substantiate or withdraw):**

| citation | rows | labels |
|---|---|---|
| `EXP-M4-14` (A18, no `raw/` tree anywhere) | 9 | 6 `hardware-run`, 3 `isolated-byte-diff` |
| `EXP-0138` (M4) | 4 | 4 `hardware-run` |
| `EXP-0169` (G17P) | 3 | 3 `untested` |

## M2 — 2026-08-30 — root cause of the EXP-0169 ladder failure IDENTIFIED, offline, from committed raw

Named **DEF-0180-A**. See `PRE_REGISTRATION.md` §3. One-line form: the C1_alu seeds are
`falu2i` minifloat fixed points whose fp32 bit patterns have **zero low 16 bits**, and a
half-precision operand descriptor with its size bit clear reads exactly those 16 bits — so
the lifted anchor's operands were `0.0`, its result was `0`, and it wrote that `0` into a
register the same instruction had already released to `0`. The pre-registered falsifier
(byte0 → `0x00`) therefore scored `match: true` **by construction**, exactly as EXP-0140's
co-varying oracle did. This is a *carrier* defect, distinct from DEF-0169-1 (the async
`device_load`), and it is why the C1/C2 asymmetry existed at all.

## M3 — 2026-08-30 — the root cause is NOT what EXP-0169 assumed, and there is a db-model defect under it

All of this is **offline re-analysis of EXP-0169's committed `raw/g17p_20260830_run01/sweep.jsonl`**.
No device. It is recorded here before any build because it changes the design.

### DEF-0180-A (carrier) — the anchors were COMPUTATIONALLY DEAD in C1_alu

`half_alu` (6B) passed its falsifier; `half_alu_ext8` and `half_alu_fma12` failed it with
`outcome: ok, match: true`. The difference is not the instruction, it is the **anchor's base
operand values relative to the carrier's seeded state**:

* the ext8/fma12 anchors were lifted from `k_hfma` / `k_hfma_abs`, whose operand bytes name
  half-registers `0x81`/`0x83` — **registers 64/65**, which in the native kernel held
  `device_load` results and which the synthesized carrier **never seeds**;
* the C1_alu seeds are `falu2i` minifloat fixed points, so every GPR's **low 16 bits are
  zero**, and every EVEN half-register descriptor therefore reads `0.0`.

So the product term was `0`, the sum was `0`, and `0` was written where `0` already was.
The falsifier could not fire. Quantitatively, in EXP-0169's own raw (C1_alu, run01):

| field | moved / dispatched | which values moved |
|---|---|---|
| `half_alu_ext8.dst` | 28 / 256 | exactly `{2k+1 : k=0..13} ∪ {128+2k+1 : k=0..13}` |
| `half_alu_ext8.b5` | 28 / 256 | the identical set |
| `half_alu_ext8.rsv6` | 0 / 256 | — |
| `half_alu_ext8.b7_lo` | 0 / 2 | — |
| `half_alu_ext8.op_valid_marker` | **0 / 2** | — (a direct contradiction of the EXP-M4-14 claim) |

Only descriptors naming a **seeded register's non-zero half** could move anything;
`r14`/`r15` seed to `0`, which is why the set stops at `k=13`. **Bit 7 of the descriptor is a
don't-care** — `129..155` mirrors `1..27` exactly.

### DEF-0180-B (db model) — `half_alu*.dst` is at the WRONG OFFSET

Reading EXP-0169's `half_alu` `dst`/`srcB` sweeps value by value:

    anchor  10 02 1c 03 00 c0   (opsel=4 hadd, opflags=3, srcA=0x03, srcB=0x00, mod=0xc0)
    seeds   r0=5.0 r1=1.5 r2=3.0 r3=0.5   -> hi halves 0x40A0 0x3FC0 0x4040 0x3F00

| byte+1 (`dst` per db) | observed | reads as |
|---|---|---|
| `0x00,0x02,0x04,0x06` | r1 = `0x00003FC0`, all else = seeds | operand = an EVEN half = `0.0` → `1.9375 + 0` |
| `0x01` | r1 = `0x00004440`, **r0 → 0** | `1.9375 + 2.3125 = 4.25` = h1 = r0.hi, and r0 released |
| `0x03` | r1 = `0x000043C0` | `1.9375 + 1.9375 = 3.875` = h3 = r1.hi |
| `0x05` | r1 = `0x00004410`, **r2 → 0** | `1.9375 + 2.125 = 4.0625` = h5 = r2.hi |
| `0x07` | r1 = `0x00004360`, **r3 → 0** | `1.9375 + 1.75 = 3.6875` = h7 = r3.hi |

**byte+1 is a SOURCE half-register descriptor (half-reg index = the byte's value), not the
destination.** The result lands in **r1 in every case** — and `byte0 == 0x10`, whose HIGH
NIBBLE is `1`. `db.json` pins all eight bits of byte0 in `match: [[0,8,16]]`.

> **Hypothesis H0: the destination of the `byte0==0x10` half-ALU family is byte0 bits 4..7,
> exactly as in `falu2` (`dst 4 4`), `n3_mov`, `mov_zext16` and `cvt_f2h_dst` — and `db.json`
> models it at bits 8..15 instead.**

`db.json` already records this exact structure for the neighbouring families:
`cvt_f2h` — *"byte0 0x11 … (dst r1)"*, generalised by `cvt_f2h_dst` to *"ANY dst register
(byte0 high nibble)"*; `mov_zext16` — *"the pre-2026-08-30 descriptor pinned byte0 to the full
fixed byte 0x13 and modelled byte+1 as the source register, so the real register selector was
invisible to an emitter"* (DEF-0161-2). **This is the same defect, one family over, and it is
underneath two of my 25 rows** (`half_alu_ext8.dst`, `half_alu_fma12.dst`, both currently
`hardware-run`).

### DEF-0180-C (length model) — `opsel` bit 1 is the LENGTH bit, and `half_alu_fma12` has no length rule

`db.json length_rule.byte0_table["0x10"] = "6, or 8 if (byte+2 & 0x02)"`. Byte+2 bit 1 is
**bit 17 = `opsel` bit 1**. So half of every `opsel` sweep re-lengths the instruction, and
`half_alu_fma12` (length 12) has **no entry in the length table at all** — it is one of the
three instructions `db.json` itself flags as an over-consumer (`doc02_over_consumers_20260828`,
`emit_unsafe`). `half_alu_fma12.ext` is 64 bits wide with an encodable range of 2^64 and can
never meet the coverage bar.

## M4 — 2026-08-30 — DEF-0180-B and DEF-0180-D CONFIRMED offline; the falsifier EXP-0169 used was never valid for this family

### The `byte0` falsifier does not null the op — it MOVES THE DESTINATION

EXP-0169 `raw/g17p_20260830_run01`, `HALF_ALU@C1_alu`, `__falsifier_byte0`
(`10 02 1c 03 00 c0` → `00 02 1c 03 00 c0`):

    baseline   r0 = 40a00000   r1 = 00003fc0      <- result 0x3FC0 in r1.LOW half
    byte0=0x00 r0 = 40a03fc0   r1 = 00000000      <- SAME result, now in r0.LOW half,
                                                     r0's HIGH half preserved

**HW evidence, G17P, already in the committed corpus: the destination GPR of the
`byte0==0x10` half-ALU family is byte0's HIGH NIBBLE, and the result is written to that
register's LOW 16 bits.** `db.json` pins all 8 bits of byte0 in `match` (so an emitter
following it can only ever write `r1`) and calls bits 8..15 `dst`, which the same raw shows
is a **source half-register descriptor** (§M3). `isadb.instr_length` has the mirror-image
bug: its own docstring records that for the `0x09` float family "byte0's high nibble carries
the dst register number … using the full byte mis-tokenizes any falu2 whose dst >= 1", and
then line 1861 gates the half family on `b0 == 0x10` — the full byte.

**Consequence for EXP-0169's ladder: `__falsifier_byte0` is not a falsifier for this family.**
It changes only which register is written. For `half_alu` the result was non-zero so it moved
anyway; for `half_alu_ext8`/`half_alu_fma12` the result was `0` and the target low half was
already `0`, so it could not. The "ladder failure" that held 16 rows was an artefact of a
falsifier that does not falsify.

### DEF-0180-D — the length selector is `byte+4 & 3`, and `db.json`'s stated rule is wrong

`isadb.instr_length` implements, for `b0 == 0x10`: `6 + 2*(byte+4 & 3)`, with an
`8`-when-zero override if `byte+2 & 2`. `db.json length_rule.byte0_table["0x10"]` states
something different and simpler: `"6, or 8 if (byte+2 & 0x02)"`. Both cannot be right, and
**neither has ever been measured against the hardware.**

The code rule predicts EXP-0169's otherwise-unexplained `half_alu.srcB` (= byte+4) sweep
exactly:

| `byte+4 & 3` | predicted length | EXP-0169 observed at `srcB` ≡ that value (mod 4) |
|---|---|---|
| 0 | 6 (2 spare bytes → harmless `pad_operand`) | `match` (baseline) |
| 1 | 8 (the anchor) | `match` (baseline) |
| 2 | 10 (swallows 4 bytes of the following dump) | **every output word still `0xDEADBEEF`** — the program never stored anything |
| 3 | 12 (swallows 6 bytes) | r1 keeps its seed — the op did not write |

**So `half_alu_ext8.srcB_desc`'s low two bits and `half_alu_fma12.ext`'s byte+4 are LENGTH
selectors, not operand bits.** Three quarters of a 256-value `srcB_desc` sweep encode a
*different-length instruction* — the `falu2_uni.uni_mode` lesson (EXP-0169 §16b) at scale.
This is why every case in EXP-0180 records `tok_instr` **and** a hardware-measured length.
