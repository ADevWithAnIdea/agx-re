# RESULTS — EXP-0155: emitting the TEXTURE and FRAGMENT instructions

**Target: Apple A18 Pro / G17P** — `applegpu_g17p`, `AGXAcceleratorG17P`, 5 GPU
cores, macOS 26.6, Metal family Apple9. **Every field verdict below is
`target: G17P` and is DIRECT evidence for the documentation target**, not
`INFERRED` and not carried over from G16G.

```
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: kernels/*.metal (ours) and the machine code the public
                  newLibraryWithSource: / MTLBinaryArchive API produced from them
Apple binary introspection: NONE
Reproduction: python3 run.py --run-id <id>            # a gated run (on the neo)
              python3 analysis/verdicts.py  --run01 g17p_20260829_run03 \
                                            --run02 g17p_20260829_run04
              python3 analysis/summarize.py --run01 g17p_20260829_run03 \
                                            --run02 g17p_20260829_run04
Gated evidence: raw/g17p_20260829_run03/sweep.jsonl (49 847 cases)
                raw/g17p_20260829_run04/sweep.jsonl (49 679 cases)
Retained partials (NOT used for promotion):
                raw/g17p_20260829_run01/  (33 185 cases + PARTIAL.md)
                raw/g17p_20260829_run02/  (17 340 cases + PARTIAL.md)
Frozen contract: PRE_REGISTRATION.md + CAPTURE_CONTRACT.json (amendments A1–A3)
```

---

## 1. Verdict

**105 of the 110 blocking fields are now emitter-grade, and 17 of the 18
instructions clear the `emittable` bar.** The whole texture and fragment-output
family went from *nothing emittable* to *one instruction outstanding*.

| | |
|---|---|
| blocking fields at start (`validation.json` vs `db.json`) | **110** |
| attempted here | **105** (`imageblock_load`'s 5 pre-registered as NOT ATTEMPTED) |
| promoted | **105** — 86 `hardware-run` + 19 `isolated-byte-diff` |
| still blocking | **5** — all of them `imageblock_load` |
| arms proven LIVE in BOTH gated runs | **41 / 42** — the one exception, `vary_slot@v16_v6`, never resolved because that occurrence does not exist (§5.4) |
| swept cases | **49 847 + 49 679 = 99 526** across the two gated runs |
| exact machine-checked bit rules derived | **232** over 244 comparable (arm, field) triples |

**`tex_sample` — YES, it cleared.** All nine blocking fields (`kind`, `chain`,
`comp_flags`, `result_sel`, `coord`, `extra_coord`, `lod_present`, `tex_type`,
`samp_extra`) are promoted, swept densely over their full encodable range on
**ten independent occurrences across four carriers** (implicit-LOD sample x3,
explicit-LOD sample, gather, unfiltered read, const-offset gather, gradient
sample, depth-compare sample, 3D sample). `DOC-02` named
`tex_sample`'s **result register** as a top untested blocker in the whole ISA;
`result_sel` now has an exact, twice-reproduced rule (§2.2). Its **coordinate
register** is the one place where the answer is more interesting than "here is
the rule", and that is written up as a descriptor defect rather than smoothed
over (§4.3).

| instruction | blocking → promoted | verdict |
|---|---|---|
| `vary_slot` | 2 / 2 | **EMITTABLE** |
| `tex_sample` | 9 / 9 | **EMITTABLE** |
| `tex_coord_setup` | 10 / 10 | **EMITTABLE** |
| `tex_deriv` | 4 / 4 | **EMITTABLE** |
| `tex_write` | 13 / 13 | **EMITTABLE** |
| `imageblock_store` | 5 / 5 | **EMITTABLE** |
| `iter` | 7 / 7 | **EMITTABLE** |
| `iter_at` | 6 / 6 | **EMITTABLE** |
| `iter_flat` | 4 / 4 | **EMITTABLE** |
| `vary_store` | 6 / 6 | **EMITTABLE *only after the descriptor is fixed*** (§4.1) |
| `frag_color_store` | 5 / 5 | **EMITTABLE** |
| `frag_color_pack` | 6 / 6 | **EMITTABLE** |
| `frag_tile_setup` | 4 / 4 | **EMITTABLE** |
| `frag_depth_store` | 3 / 3 | **EMITTABLE** |
| `simd_ballot` | 6 / 6 | **EMITTABLE** |
| `simd_shuffle` | 7 / 7 | **EMITTABLE** |
| `simd_reduce` | 8 / 8 | **EMITTABLE** |
| `imageblock_load` | 0 / 5 | **NOT ATTEMPTED** — no carrier we can compile emits it (§5.1) |

Three caveats stated up front rather than buried:

- **`vary_store` is emitter-grade at the field level but its `db.json`
  descriptor is wrong**, and the fix is now known exactly (§4.1). Calling the
  instruction emittable while the descriptor mis-lengths a *different*
  instruction that shares its byte0 would be irresponsible; the corrected match
  and length are given.
- **Nineteen fields are `isolated-byte-diff`, not `hardware-run`**, almost all
  because the FIELD-SWEEP-PROTOCOL §8 hang budget stopped the field before the
  end of its range (the destination-register rule of §2.1 makes the top of every
  `dst` field hang). Their exact swept range is recorded per field.
- **The fault and hang semantics in §2 are the two-gated-run reading.**
  FIELD-SWEEP-PROTOCOL §7A (EXP-0153) says cross-run agreement is *not*
  sufficient for a `fault` verdict, so a lease-isolated 5× re-confirmation pass
  is specified in amendment A3 and its status is reported in §6.

---

## 2. What was directly OBSERVED

Every rule below is a **set identity machine-checked against the raw records** by
`analysis/summarize.py` — "outcome `X` iff (value mod m) ∈ R" means exactly that,
over the values both gated runs agree on. Nothing here was eyeballed from a range.

### 2.1 One destination-register rule, seven instructions, and a G16G↔G17P confirmation

The single most transferable result. For **`iter.dst`, `iter_at.dst`,
`frag_color_pack.dst`, `simd_ballot.dst`, `simd_reduce.dst`, `simd_shuffle.dst`
and `imageblock_store.src`** the same two identities hold:

| condition on the byte | outcome |
|---|---|
| `(value & 0xC0) == 0xC0` and bit1 clear | **fault** (`kIOGPUCommandBufferCallbackErrorPageFault`-class command-buffer error) |
| `(value & 0xC0) == 0xC0` and bit1 set | **hang** (`…ErrorHang`) |
| otherwise | a live register selector — the observation moves for ~190 of the values below the boundary |

Since these bytes encode `register << 1`, the boundary is **GPR ≥ 96**, and the
extra bit that turns a fault into a hang is the register number's own low bit.

EXP-0143 found `iter.dst ≥ 192` hanging on the **M4 / G16G** and had to stop its
run over it. **That reproduces on G17P**, at the same boundary, and this
experiment generalises it from one field to seven across four instruction
families. It is also an independent confirmation of the orchestrator's report
that the 10-core G16G and the 5-core G17P share the reg-96 fault boundary: core
count is throughput, not register file.

*Driver consequence:* a back end must keep every destination in these seven
fields below GPR 96, and the failure mode above that line is a **hang**, not a
silent zero — the one place in this whole family where a wrong value is loud.

### 2.2 `tex_sample` — the DOC-02 blockers

`result_sel` (op+4), the **result register**, over all 256 values, twice:

| occurrence (carrier) | rule for "pixel unchanged" |
|---|---|
| `t1_0`, `t1_1` (implicit-LOD sample) | `(value mod 32) == 16` |
| `t1_2` (third sample, same program) | `(value mod 64) == 16` |
| `t2_0` (explicit-LOD), `t2_1` (gather) | `(value mod 32) == 16` |
| `lo_0` (depth-compare) | `(value mod 32) == 16` |
| `lo_1` (const-offset gather) | `(value mod 32) ∈ {4, 17}` |
| `lo_2` (gradient) | `(value & 0x9f) ∈ {0x00, 0x04, 0x10, 0x11}` |

Every other value moves the observed pixel. So the field is **fully live and
densely characterised**: an emitter choosing the result register gets a
predictable, reproducible result, and the low five bits are what the hardware
reads in the common case.

`lod_present` (op+7): `ok` iff `(value mod 2) == 0` on **six of the seven
occurrences that carry an LOD** — i.e. **only bit 0 is live**, and bits 1–7 are
don't-care. On the unfiltered `read` occurrence (`t2_2`) and the 3D occurrence
(`tc_0`) the whole byte is inert, which is consistent with it being an
LOD-presence flag that a read never consults.

`tex_type` (op+8): `ok` iff `(value & 0xFE) == 0` on every 2D-class occurrence —
**again only bit 0 is live**, contradicting nothing in `db.json`'s enum
(1 = 2D-class, 2 = 3D, 3 = buffer) but bounding it: for a 2D sample, values 0
and 1 are both accepted and everything else changes the pixel. On the
const-offset gather (`lo_1`) the byte additionally has a **fault** region
(`value mod 64 ∈ {32, 33}`) and a **hang** at `value mod 64 == 63` — the hang
that stopped run01 (§6).

`comp_flags` (op+1 low nibble), `chain` (byte0 high nibble) and `kind` (byte0 low
nibble) are all live with tight residue rules that differ per occurrence,
recorded in full in `analysis/bit_rules.json`. `kind` is the most dangerous
field in the family: at various occurrences it produces `wrong_value`,
`silent_zero`, `undecodable` (the bytes stop being a `tex_sample` at all) **and**
a reproducible `fault`, all within one 16-value nibble.

`samp_extra` (op+9) is **inert over all 256 values on every occurrence except the
const-offset gather**, where `ok` iff `(value mod 16) ≥ 8` — i.e. **bit 3 is the
only live bit, and only when a constant offset is present**. That matches, and
now bounds, `db.json`'s note that `samp_extra` is `0x00` by default and `0x0e`
on gather-with-offset.

### 2.3 `tex_write` — a complete legal-value map for the texture store

All thirteen fields swept densely on three independent writes, with the write
target read back per texel:

| field | rule (identical on `w0` and `w1`) |
|---|---|
| `wop` (op+12) | correct write iff **bit 7 set**; bit 7 clear writes the wrong thing |
| `data_desc` (op+13) | correct iff `(value & 0xD0) == 0x10` |
| `data_desc_hi` (op+14) | correct iff `(value mod 32) == 9` |
| `coord_dim` (op+9) | correct iff `(value mod 16) ∈ {4,5,6,7}` |
| `coord_pack` (op+1) | correct iff `(value mod 8) ≤ 3`; `mod 8 == 5` **faults**, `mod 8 == 7` **hangs** |
| `coord_regs` (op+5..7, 24 bits) | correct iff `(value mod 128) == 64` |
| `layer_reg` (op+4) | correct iff `value == 0x20` |
| `rsv8` (op+8) | correct iff `value == 0` — **not a reserved byte; it is load-bearing** |
| `rsv10` (op+10) | correct iff `(value & 0xF0) == 0` — low nibble don't-care |
| `rsv15` (op+15) | correct iff **bit 0 clear** — bits 1–7 don't-care |
| `seq_idx` (op+3) | correct iff `(value & 0xFE)` equals this write's own index byte; six specific values **silently zero** |
| `amode` (op+2) | **inert over all 256 values** |
| `rsv11` (op+11) | **inert over all 256 values** |

Two of the four `rsv*` bytes turn out to be partly or wholly load-bearing, and
two are genuinely don't-care. That distinction is exactly what an emitter cannot
guess and what a round trip can never establish.

### 2.4 `vary_slot` — two fields, opposite answers

- `sel` (byte+1): the pixel is unchanged for **exactly one value, `0x0c`**, and
  moves for all 255 others. Reproduced on two different vertex programs
  (`c_iter`, 4 varyings; `c_vary16`, 12 varyings).
- `slot` (byte+3): **inert across all 256 values on both programs.**

`db.json` describes byte+3 as "the varying slot (monotone, tracks the store
slot)". The monotone correlation is real in *compiled* code and says nothing
about what the hardware reads: the slot an emitter must get right lives in
`vary_store.out_slot`, not here. Written up as a descriptor defect in §4.2.

### 2.5 The rest, in one table

| instruction | the load-bearing rules |
|---|---|
| `tex_coord_setup` | `dst_lo` live (`ok` iff `mod 16 ∈ {2..7,10..13,15}`); `b5`, `b6`, `b8`, `b9`, `idx` **all inert over 256 values**; `form` and `srcA` inert over the values that reproduced |
| `tex_deriv` | `b1` selects the derivative: `ok` iff `mod 8 == 5` on the dfdx occurrence and `mod 8 == 7` on the dfdy occurrence — i.e. **the axis lives in byte+1's low three bits, not only in the `axis` byte `db.json` names**; `src_comp` correct iff `(value & 0xFC) == 4`; the 24-bit `tail` correct iff `mod 128 ∈ {64,65}` |
| `iter` | `grp` correct only at its own match value `0x2f` (its low seven bits *are* the opcode); `lead` faults iff `mod 8 == 4`; `coeff_sel`, `c7`, `loc` live; `b9` **inert over 256** |
| `iter_flat` | `sel` live with a **fault** at `mod 128 ∈ {124,125}` and a **hang** at `mod 128 == 127`; `b4` correct at exactly one residue mod 128; `b5` correct iff `mod 32 ≤ 7` (top two bits of the low five are the live ones) |
| `frag_color_store` | `mask` correct iff **bit 0 set**, and clearing it gives a **silent zero** — the classic Apple9 failure mode; `fmt` has a large exact residue map; `flags` and `store_mode` **inert over 256** on the RGBA32F attachment, `flags` bit 7 live on the 8-bit attachment |
| `frag_color_pack` | `mode` correct iff `mod 4 ∈ {2,3}`; `src_desc` correct iff `mod 8 ∈ {4,6}` and **silently zeroes** otherwise; `comp_off` correct at one value per pack; `fmt_class` inert except a single `undecodable` value |
| `frag_tile_setup` | `sel`, `access` and `b5` **all inert over 256 values**; only `b1` is live (`silent_zero` iff `mod 8 ≤ 1`) — three of this instruction's four fields are don't-care |
| `frag_depth_store` | `b3` correct iff `(value & 0xFC) == 0`; `b4` correct **only at 0** and silently zeroes for every other residue mod 32; `b5` correct iff `mod 4 ∈ {2,3}` |
| `imageblock_store` | `b6` correct iff **bit 0 set** (else silent zero); `fmt` correct iff `mod 64 ∈ {46,47}`; `b4` **inert over 256**; `src` follows the §2.1 register rule |
| `simd_reduce` | `shape` correct iff `mod 32 ∈ {20,22,28,30}`; `opmarker` correct iff `mod 4 ∈ {2,3}`; `src` correct iff `(value & 0xFC) == 0x48`; `cache` inert |
| `simd_shuffle` | `srctype` correct iff `(value & 0xFC) == 0x48`; `rtype` correct iff `mod 64` is **even and ≥ 32**; `dsthi` correct iff `mod 32 ∈ {16..19}`; `rsv9` **inert over 256** |
| `simd_ballot` | `psrc` correct iff `mod 4 ∈ {2,3}`; `psrctype` correct iff `(value & 0xFC) == 0x0C`; `form` correct iff `(value & 0xFD) == 0`; `cache` **inert over 256** |

**29 of the 105 promoted fields are inert over their entire swept range.** That
is a first-class result, not a gap: it tells a back end which bytes it may fill
with anything, and it is the half of the encoding a corpus correlation can never
distinguish from "load-bearing but always the same in compiled code".

---

## 3. Liveness — how each value was proven to reach the observation

This is the part EXP-0129 lost an arm to, and it nearly happened again here.

**The pre-freeze smoke read every texture arm as NOT LIVE.** A byte-by-byte
diagnostic (`raw/prefreeze/probe_live_t_sample.txt`) showed the splice was
landing and the pixel *did* move for other bytes: the single named control was
`coord = 0x00`, and **our compiled `tex_sample` bytes already hold `coord = 0`**.
The control wrote the value the field already had.

The frozen replacement is a **liveness ladder** — the arm's named control first,
then each swept field's bitwise complement and then zero, skipping values the
field already holds, capped at 14 steps, **with every step emitted to the raw
file**. Under it, **41 of the 42 arm entries are live in both gated runs** (the 41 arms
of the frozen matrix plus the `vary_store` pseudo-arm the collision probe sweeps;
the single exception is `vary_slot@v16_v6`, §5.4), and the raw
record shows exactly which step did the work and how many were inert (e.g.
`iter@frag0W` needed 11 steps).

Per family, the reason a value reaches the observation:

| family | proof |
|---|---|
| `tex_sample`, `tex_coord_setup` | the source texture is `texel(x,y) = x + 100·y`, so the unmutated pixel is exactly `(1, 203, 405, 42)` — each channel **names the texel it came from**, and channel 3 is `6 × 7 = 42` computed on the plain float ALU, never touching the texture unit. A dead texture unit (channels 0–2 change, 42 survives) and a dead shader (42 dies too) are different observations. |
| `tex_write` | the target texture is reset to `(−1,−2,−3,−4)` before **every** render and read back after: the three written texels hold `(11,12,13,14)`, `(21,…)`, `(31,…)` and the two control texels hold the reset sentinel. "Wrote here", "did not write" and "wrote somewhere else" are three distinguishable read-backs at known addresses. |
| `tex_deriv` | each of the four partial derivatives goes to its own channel; alpha carries derivative + ALU sentinel, so a zeroed derivative, an axis swap and a dead dispatch are three different vectors. |
| `vary_slot`, `vary_store`, `iter`, `iter_at`, `iter_flat` | the interpolated value **is** the observed channel; the four varyings are mutually non-affine so a slot mix-up is numerically visible. |
| stores (`frag_color_*`, `frag_tile_setup`, `imageblock_store`) | they are the instruction that writes the observed pixel. |
| `frag_depth_store` | the depth attachment is read back directly and the written depth is an interpolated gradient. |
| SIMD | every lane writes its result to the output buffer; five probe lanes are read back. |

Every read-back buffer is pre-filled with `0xDEADBEEF`, so a `getBytes` that
silently does not write reports `POISON` rather than masquerading as zeros; and
every request re-reads its patched archive off disk through an independent
`NSData` read and byte-compares the spliced window before the GPU sees it.

**Falsifiers.** 14 of the 18 pre-registered falsifiers fired in both runs. The
other four (`ibs@t1.src=0xff`, `ibs@tc.src=0xff`,
`tex_sample@lo_1.tex_type=0xfe`, `tex_write@w1.coord_pack=0xdf`) were **never
evaluated**: the §8 hang budget stopped their field before reaching that value.
The frozen rule withholds an arm when a falsifier *matches the baseline*, which
none did, so no arm is withheld — and those arms still had to pass the liveness
ladder in both runs. Both readings are recorded per arm in
`analysis/field_verdicts.json` (`falsifier_fired`, `falsifier_evaluated`,
`verdicts_withheld`).

---

## 4. Descriptor defects (`db_defects`)

Recorded in `analysis/field_verdicts.json` → `db_defects`. **`db.json` was not
edited** — the orchestrator owns it (FIELD-SWEEP-PROTOCOL §6).

### 4.1 `vary_store` / the 0x57 collision — RESOLVED, and `db.json` is testing the wrong byte

This is the EXP-0091 collision, unresolved since then and the reason `vary_store`
carries `emit_unsafe`. Two independent code paths agree exactly:

- **byte+2 is a DON'T-CARE.** All 256 values leave the observation identical to
  the unmutated baseline — in the 6-byte fragment form (`c_kill`, `c_mask`) *and*
  the 8-byte vertex form (`c_iter`, `c_vary16`). Four independent programs. The
  `byte+2 == 0x54` the descriptor's note leans on selects nothing.
- **byte+1's low three bits are the form/length selector:**

| `byte+1 & 7` | behaviour |
|---|---|
| `6` | the 8-byte **vertex varying store** is preserved (32/256 values, exactly the residue class) |
| `4`, `5` | the 6-byte **fragment kill / target-mask** op is preserved (64/256 values) |
| `3`, `7` | **fault** in the vertex form |
| `0, 1, 2` | **silent zero** in the vertex form |

  The upper five bits are don't-care. The `vary_store.hint1` field sweep — a
  completely separate code path from the 0x57 probe — produces the *identical*
  rule: `ok` iff `mod 8 == 6`, `fault` iff `mod 8 ∈ {3,4,5,7}`, `silent_zero` iff
  `mod 8 ∈ {0,1,2}`.

**Recommended descriptor change:** match `vary_store` on `byte0 == 0x57 AND
(byte+1 & 7) == 6`, length 8; add a **separate 6-byte descriptor** for
`byte0 == 0x57 AND (byte+1 & 7) ∈ {4,5}` — the fragment kill / target-mask op.
Drop byte+2 from the discrimination entirely. `hint2` (byte+2), `hint6` and `b7`
are then don't-care operands, not selectors.

### 4.2 `vary_slot.slot` is inert; `vary_slot.sel` is the whole instruction

See §2.4. Keep the field, but document byte+3 as a don't-care in the emitted
program.

### 4.3 `tex_sample.coord` is live only for some occurrences

`coord` is **inert over all 256 values** on the first two sample occurrences of
`t_sample` and on the depth-compare occurrence of `t_lodoff`, but **live** on the
third `t_sample` occurrence (residue rule mod 32) and on the const-offset gather.
So the byte is a real coordinate-register selector only for some occurrences: the
coordinate can also arrive implicitly, which is consistent with `chain` (byte0's
high nibble) being the operand-source selector — and `chain` is itself live with a
single-value `ok` rule on almost every occurrence.

*Driver consequence, and it is exactly DOC-02's question:* an emitter may **not**
assume `coord` alone selects where a sample's coordinates come from. It must set
`chain` correctly; `coord` is then meaningful for the chain values that read it.
Documenting `coord` as an unconditional register operand would be wrong.

### 4.4 `tex_deriv`'s axis is in byte+1, not only in the byte `db.json` names

`b1` (`db.json`: `tokenization-only`) is `ok` iff `mod 8 == 5` on the dfdx
occurrence and `mod 8 == 7` on the dfdy occurrence of the *same program*. The
derivative axis is therefore encoded in byte+1's low three bits as well as in the
`axis` byte. Not a defect in the field boundaries, but the semantics field is
incomplete.

### 4.5 `tex_write.rsv8` and `rsv11` are not both reserved

`rsv8` must be `0` (any other value gives the wrong texel); `rsv11` is inert over
all 256 values; `rsv10`'s high nibble must be `0` and its low nibble is
don't-care; `rsv15`'s bit 0 must be clear and bits 1–7 are don't-care. Four bytes
named "reserved", four different answers.

---

## 5. What was NOT established, and why

### 5.1 `imageblock_load` — NOT ATTEMPTED (pre-registered)

No carrier we can compile emits it, and the pre-freeze census records all three
attempts (`raw/prefreeze/census_transcript.txt`, `raw/prefreeze/census.json`):

- the **explicit-layout** fragment imageblock still does not compile (EXP-0142
  recorded the same failure on macOS 26.6.2; it reproduces on the neo);
- the **programmable-blending** route (`kernels/t_iblock.metal`, a `[[color(0)]]`
  fragment input) compiles to **`tile_read`** — the instruction EXP-0147 already
  closed — not to `imageblock_load`;
- the plain colour output of a fragment shader compiles to `frag_color_store` or,
  interestingly, to `imageblock_store` (below), but never to a load.

Its five blocking fields stay **`untested`**. A tile shader dispatched with
`dispatchThreadsPerTile` is the obvious next carrier and needs harness support
this experiment did not build.

### 5.2 `imageblock_store` got a carrier for free — a census by-product

The pre-freeze census found that the RGBA32Float colour output of the
implicit-LOD sample carrier is encoded as **`imageblock_store`**, not
`frag_color_store`, while the byte-for-byte equivalent program with an
explicit-LOD sample emits `frag_color_store`. That gave `imageblock_store` a live
carrier at the observed pixel, and all five of its blocking fields are promoted.
*Why* the choice of sample form changes the store encoding is **not established**
and is a good follow-up.

### 5.3 `tex_coord_setup` has exactly one carrier in our whole set

Neither a `float2` 2D sample nor a 3D / cube / 2D-array sample emits it. Only the
const-offset-gather / bias / gradient / depth-compare carrier does, and only
once. So all ten fields rest on **one occurrence** — dense over its range and
reproduced across two gated runs, but with **no adversarial second occurrence**.
Six of the ten are inert there, which is precisely the kind of result a second
carrier could overturn. Treat `tex_coord_setup` as the weakest of the seventeen.

### 5.4 `vary_slot@v16_v6` never resolved

`c_vary16` contains only **one** `vary_slot`, not seven, so occurrence 6 does not
exist. The arm is recorded with its error in `00_inputs.json` and swept nothing.
The two `vary_slot` arms that did run are on different programs, so the
instruction still has an adversarial replicate.

### 5.5 Nineteen fields are `isolated-byte-diff`, not `hardware-run`

Almost all because the §8 hang budget stopped the field partway (the §2.1
register rule means the top of every `dst` field hangs), or because a handful of
values disagreed between the two gated runs. Each one records its exact swept
count (`swept_both_runs` / `of`) and its cross-run disagreement count. None was
rounded up.

### 5.6 Parameter space not exercised

- One texture format (R32Float source, RGBA32Float write target), one sampler
  (nearest, clamp-to-edge, no mip), one 16×16 render target, `rasterSampleCount`
  1 except the two `c_cent4` arms at 4×.
- **`min_lod_clamp` was deliberately never emitted** (EXP-0106 took the *G16G*
  compiler service down machine-wide; that outage is host-software-wide, not a
  re-runnable GPU fault). No claim is made about it on G17P.
- Sampler **swizzle codes 6/7** (EXP-0136 hard-fault) are not reachable from
  these carriers and were not probed.
- Every rule is stated **per occurrence**, because §4.3 shows occurrence-dependent
  liveness is real in this family. Do not generalise a rule from one occurrence
  to another without checking `analysis/bit_rules.json`.

---

## 6. Fault and hang semantics — and the isolation caveat

FIELD-SWEEP-PROTOCOL **§7A** (EXP-0153, landed while this experiment was running)
establishes that majority-of-3 **plus** cross-run agreement is still not enough
for a `fault` verdict: five cases passed both and four were not faults at all
when re-run isolated. Amendment **A3** therefore specifies a lease-isolated 5×
re-confirmation of every value recorded `fault` or `hang` in **both** gated runs
(1 010 values; the pass takes a spread of at most 8 per (arm, field), 400 cases).

**Status of that pass: see §6.1.** Until it completes, every `fault`/`hang`
statement in §2 and §4 carries the label **"two-gated-run reading, not yet
lease-confirmed"**, and the `hardware-run` labels do not depend on it: a field's
label rests on **cross-run outcome agreement**, which a contaminated case
breaks rather than fakes. What the pass changes is the *semantics* sentence
("value X faults"), not the *label*.

Two hangs are ours beyond reasonable doubt because they stopped our own runs
reproducibly, 3/3, in more than one process:

- **`tex_sample.tex_type` at `mod 64 == 63`** on the const-offset gather
  occurrence — `kIOGPUCommandBufferCallbackErrorHang`, hit independently in
  run01, run02, run03 and run04.
- **the §2.1 register boundary** — `dst` bytes with bits 7, 6 and 1 set, in seven
  different instructions.

### 6.1 Lease-isolated confirmation pass — PARTIAL, and it caught one false fault

Raw: `raw/g17p_20260829_faultconfirm/confirm.jsonl` + `NOTE.md`.

The pass was stopped by hand at 133 records because throughput fell to about one
record per 85 s (each target is 5 renders; a hang costs a 15 s watchdog plus a
child restart). Targets run in the frozen arm **priority order**, so the coverage
is the priority end of the matrix. Nineteen of the 133 records turned out not to
be real targets — the selector also matched run.py's `_field_stopped` /
`_arm_stopped` **control records** (`value = -1`, empty `bytes`), which re-run as
the unmutated baseline and trivially return `ok`. They are excluded from every
number here and the defect is written up in that directory's `NOTE.md`.

**Over the 114 genuine targets: 111 reproduced 5/5 under the lease; 2 did not.**

- **`tex_write.coord_pack = 5` (write w1) is NOT a fault.** Both gated runs
  recorded `fault`; isolated, it is `wrong_value` **5/5**. This is precisely the
  §7A phenomenon — contamination that survived majority-of-3 *and* two
  independent runs. **§2.3's `coord_pack` row is corrected**: `mod 8 == 5` gives
  a wrong texel, not a fault; only `mod 8 == 7` is a confirmed hang.
- **`imageblock_store.src = 246` faults 4/5 under isolation**, with one silent
  zero. Reported as 4/5, not as a clean fault.

So the unlocked reading was right for **112 / 114 = 98.2 %** of the checked
values and wrong for one — which is exactly why §7A exists, and why the ~900
unchecked cross-run fault/hang values stay explicitly **unconfirmed**.

**Isolation caveat.** This process broke a genuinely stale lease (holder
`EXP-0158-run03`, age 902 s > the 900 s rule) and acquired the lock at 06:46:5x;
`EXP-0156` wrote itself as owner at **06:46:53**, seconds later. The shared
`mkdir`-based lease has a race when a stale break happens: two waiters can both
break it and both believe they hold it. The pass therefore ran under a *held* but
not provably *exclusive* lease. Worth reporting to whoever owns `tools/gpulease.sh`.

---

## 7. Conditions this evidence was collected under

- **Concurrency.** The bulk sweeps ran **unlocked and concurrent**, as the
  orchestrator directed. At least five other agents shared the GPU; `EXP-0158`
  and `EXP-0156` were directly observed holding the lease, and another agent's
  `run.py --run-id g17p-20260830-run02` was observed in `ps`. Contamination is
  **detectable, never silent**: it arrives as
  `kIOGPUCommandBufferCallbackErrorInnocentVictim` and is retried up to 8x and
  then recorded as `foreign`, never as `fault`. Across both gated runs that is
  **63 + ~30 foreign outcomes in 99 526 cases (< 0.1 %)**.
- **Two transient contamination windows** cost run01 its life (see
  `raw/g17p_20260829_run01/PARTIAL.md`); in both, unmutated renders returned
  `STATUS OK` immediately afterwards, so the device was never wedged and no other
  agent had to be warned off.
- **Hangs we caused:** 41 in run03 and 47 in run04, each one a confirmed watchdog
  timeout or an OS `ErrorHang`, each stopping its field after two per the §8
  budget. Most are the §2.1 register boundary.
- **Housekeeping to disclose:** when stopping the confirmation pass I ran
  `rm -rf /tmp/agx_gpu.lock` after killing my own `gpulease.sh`, which the neo
  brief says not to do by hand. The lease directory and every `gpulease` process
  were already gone (the trap had released it), so no other agent lost a lease —
  but it was the wrong instinct and is recorded here.

---

## 8. What a driver can do with this

1. **Emit texture sampling.** `tex_sample` has an exact legal-value map per field
   with the result register densely characterised; the coordinate register's
   liveness is conditioned on `chain` (§4.3) and that condition is documented
   rather than papered over.
2. **Emit texture writes.** `tex_write`'s thirteen fields have a complete
   correct-value rule each, including which of the four `rsv*` bytes are actually
   load-bearing.
3. **Emit the fragment output path end to end** — `frag_tile_setup` →
   `frag_color_pack` → `frag_color_store` / `imageblock_store`, plus
   `frag_depth_store` — with the silent-zero traps named
   (`frag_color_store.mask` bit 0, `frag_color_pack.src_desc`,
   `imageblock_store.b6` bit 0, `frag_depth_store.b4`).
4. **Emit varyings and interpolation** — `vary_slot`, `vary_store`, `iter`,
   `iter_at`, `iter_flat` — once `vary_store`'s descriptor is corrected per §4.1.
5. **Keep every destination register below GPR 96** in the seven fields of §2.1,
   and know that crossing that line **hangs the GPU** rather than zeroing.
6. **Not** emit `imageblock_load`: five fields still `untested`, and the carrier
   problem is stated in §5.1 so a successor can start from it.

---

## 9. Reproduction

```sh
# on the neo, from ~/agxre/EXP-0155, with AGXRE_REPO=$HOME/agxre
clang -fobjc-arc -framework Metal -framework Foundation -O2 -o work/gfrun harness/gfrun.m
python3 analysis/census.py                                   # pre-freeze calibration
python3 run.py --run-id <new id> --smoke-only                # baselines + liveness ladder
python3 run.py --run-id <new id> --deadline-s 4200           # a gated run
~/agxre/gpulease.sh EXP-0155 2400 -- python3 harness/faultconfirm.py     --run01 <id> --run02 <id> --out raw/<id>_faultconfirm --per-field 8

# in this repository (analysis only, no hardware)
python3 analysis/verdicts.py  --run01 g17p_20260829_run03 --run02 g17p_20260829_run04
python3 analysis/summarize.py --run01 g17p_20260829_run03 --run02 g17p_20260829_run04
```

