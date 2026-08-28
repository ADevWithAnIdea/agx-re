# RESULTS — EXP-0102 M4 INT-*/PACK-* semantics

Clean-room category: **OWN-SHADER + HW-PROBE** (+ `PUBLIC` for NIR/GLSL/Metal-Shading-Language-
Specification/IEEE754 definitions used only to write the host oracle, never to source an
Apple9-specific encoding fact). Every byte compiled, dispatched, or inspected is the compiled
form of MSL authored in this experiment (`kernels/*.metal`) or the READ-ONLY `tools/agx-isa`
tokenizer applied to those same compiled bytes. No Apple binary was disassembled, decompiled,
or otherwise introspected.

**Target: local Apple M4 / G16G only** (10 GPU cores, macOS 26.6.2 build 25G82, Metal 4). A18
Pro is hands-off (standing directive); nothing here is A18/G17P-validated. Per
`docs/isa/README.md`'s target-equivalence rule, this is treated as the operational Apple9
evidence, not `INFERRED`-by-family, for every claim below unless explicitly marked otherwise.

**Two-run gate: MET.** `raw/m4-20260828T063920Z-run01` and `raw/m4-20260828T063935Z-run02`,
51/51 cases `status=OK` in both, `verify.py --captured --compare run01 run02` → **51/51 GATED
records BYTE-IDENTICAL**. All facts below are drawn from `run01` (byte-identical to `run02`).

---

## Gate results

| gate | result |
|---|---|
| `verify.py --selftest` | PASS (39 hand-worked vectors + struct cross-sweep + casematrix build, 0 failures) |
| `verify.py --seqtest` | PASS in `PRE_GPU` phase before capture; PASS in `RUN01_PRESENT`/`RUN02_PRESENT` after each capture completed (the mid-run FAIL lines visible in `PROGRESS.md` are `run.py` calling `--seqtest` **before** that run's own capture has started, which is correctly reported as "results.jsonl missing" at that instant — informational, not a real gate failure; not gated on by `run.py`) |
| NON-RECORDED smoke gate (`--preflight` before run01, `--between-runs` before run02) | PASS both times, never written under `raw/` |
| Case status | 51/51 `OK` in both runs (0 faults, 0 timeouts, 0 harness errors) |
| Cross-run byte-identity (`--captured --compare`) | **51/51 records identical** |
| No nondeterministic field in gated records | enforced by construction (`verify.py::GATED_FIELDS` excludes timestamps/duration/argv/stdout) |

**Two disclosed, self-caught process issues** (both fixed before the promoted capture; full
detail in `PROGRESS.md`):
1. An initial capture (`raw/m4-20260828T063741Z-run01`, **quarantined**,
   see its `QUARANTINE.md`) wrote scratch Metal binary archives under `raw/.../work/`, violating
   the text/JSON-only rule for `raw/`. Fixed (`harness/case_exec.py --work-dir` now points
   outside `raw/`); the officially promoted `run01`/`run02` above were captured with the fix and
   contain zero binary files under `raw/`.
2. `verify.py::run_smoke` originally used `tempfile.TemporaryDirectory()`, which resolves
   outside the repo on this host — caught immediately after `SUBAGENT_BRIEF.md` was updated
   mid-session to explicitly forbid this, fixed to use a `work/smoke/` directory inside the
   experiment tree with explicit cleanup. This only affected the four NON-RECORDED smoke calls in
   this session; no gated evidence was affected, so the captures were not redone.

---

## OBSERVED (directly, from `raw/m4-20260828T063920Z-run01`, before interpretation)

### Bitfield extract / insert (INT-01, INT-02, INT-03, INT-11) — `int0102_extract_unsigned`, `int03_extract_signed`, `int11_insert_bits`

Runtime-supplied `(a, off, cnt)` / `(base, val, off, cnt)`, 122 and 256 rows respectively, boundary
sweep incl. `off`/`cnt` at 0, small values, 31, 32, 33, 40, 63, 64, 1000, and 2^32-1.

- Every `cnt==0` row returned exactly `0` (extract) / the unmodified `base` (insert).
- Every `cnt==32` row returned the operand **verbatim with the offset having no effect at all** —
  extract: the full 32-bit input; insert: the full 32-bit `val`, regardless of how large `off` was
  (including `off == 2^32-1`).
- Every other row (`cnt` ∈ {1..31} ∪ {33,40}) matched **`off` applied as a literal, unmasked shift
  amount**: `off >= 32` → the field contributes nothing (extract returns 0 for that field / insert
  leaves `base` unchanged there); `off < 32` → ordinary `(data >> off) & mask` / mask-clear-and-OR,
  with `mask` clamped to a full 32 bits once `cnt > 32`.
- Signed extract (`int03`, same rows, `int` cast): every row equals unsigned extract's result
  (above) with a plain two's-complement sign extension over `min(cnt,32)` bits — no row showed a
  result inconsistent with that construction.
- Model fit on this exact 122/256-row dataset: **122/122** and **256/256** for the model above
  (`oracle.ubfe_model_d_width32_bypasses_offset` / `insert_bits_model_d`); the two originally-
  recorded competing models (`offset masked mod 32`, `offset literal but no cnt==32 special case`)
  each mismatched on a disjoint subset of rows and are both refuted as complete descriptions.
- Structural (`analysis/structural.py`, `tools/agx-isa` tokenizer on the same captured bytes):
  with RUNTIME (buffer-fed, non-compile-time-constant) `off`/`cnt` — i.e. exactly the shape this
  experiment needed to probe the boundary behavior with real hardware masking, rather than
  compile-time folding — extract compiles to `get_sr, device_load×3, ibfe, ibfins, b_alu10_loe,
  n2_op6, <unknown 20-byte tail>` (one static body, executed once per grid lane across all 122
  rows; the 20-byte tail almost certainly holds `device_store`+`stop`, matching every other
  kernel's tail shape, going by the recognizable `e7 00 54...` device_store lead-in bytes visible
  in the raw hex). This is **NOT** the single-`ibfe`-op shape EXP-0033 reported for
  `extract_bits(a, 4u, 8u)` — EXP-0033's `off`/`cnt` were COMPILE-TIME CONSTANTS the compiler
  could statically prove `!= 32`, letting it skip whatever the `ibfins`/`b_alu10_loe`/`n2_op6`
  apparatus here implements (very likely the compiler's own cnt==32 detection-and-blend logic,
  though this experiment did not isolate which specific instruction encodes the comparison). See
  INTERPRETED for the resulting, more cautious compiler-consequence reading. Insert is
  **NOT single-instruction**: the tokenized body is `get_sr, device_load×4, ibfins, b_alu10_loe,
  ibfins, ibfins, b_alu10_loe, <unknown 40-byte tail>` — **three** `ibfins`-mnemonic instances
  (with different `form` sub-field values 0/16/32, i.e. `fields.form` distinguishing what look
  like distinct roles within one op family) interleaved with **two** `b_alu10_loe` helper ALU
  instructions, for a kernel whose MSL source makes exactly ONE `insert_bits(...)` call — so this
  is one static kernel body compiled once, not an artifact of the 256-row runtime sweep. The
  40-byte `<unknown>` tail is bytes `tools/agx-isa`'s current tokenizer cannot yet name in this
  context (it almost certainly contains at least the kernel's `device_store`+`stop`, going by
  every other kernel's tail shape) — reported as a DB coverage gap, not a hardware fact.

### Rotate (INT-04, INT-05, INT-06) — `int04_rotate_imm{0,1,31,32,33,63,64}`, `int0506_rotate_var`

- Immediate rotate, all 7 amounts × 4 base values: exact `rotl32(a, K mod 32)` in every case.
- Byte-for-byte: `imm0 == imm32 == imm64` (identical `_agc.main`, 36 bytes, **no rotate
  instruction present at all** — the compiler folds a mod-32-zero immediate rotate to identity
  and eliminates it). `imm31 == imm63` (identical, 48 bytes). `imm33 == imm1` (identical, 48
  bytes). Every non-degenerate immediate kernel disassembles to exactly one `irotate` instruction
  (`get_sr, device_load, irotate, device_store, stop`).
- Runtime-amount rotate (`int0506_rotate_var`, 64 rows, amounts including 0,31,32,33,63,64,65,
  127,128,255,256,1000,2^31,2^32-1): exact `rotl32(a, n mod 32)` in all 64 rows. `_agc.main` is
  98 bytes and disassembles to `get_sr, device_load, device_load, tex_coord_setup, ibfins, iadd2,
  ibfe, shift_amt_move, device_store, stop` — **ten instructions**, no `irotate` present at all.
  (The `tex_coord_setup` label is very likely a naming/DB-collision artifact — this kernel has no
  texture operations — see INTERPRETED.)

### IMAD (INT-07, INT-08) — `int0708_imad_wrap_{u,s}`, `int08_imad_register_pressure`

- Unsigned/signed boundary triples (incl. `0xFFFFFFFF*2+1`, `INT32_MIN*-1+0`, etc.): exact
  `(a*b+c) mod 2^32` (two's-complement for signed) in all 8 + 6 rows.
- Register-pressure kernel (40 independent live temporaries feeding one final `acc*b+c`,
  `--dump-main` captured): `_agc.main` is 1402 bytes, 137 instructions, including **16** separate
  `imad` instances (the compiler builds the 40-term reduction as a chain of paired multiply-adds,
  not 39 plain adds) plus 76 `iadd2` and 38 `b_alu10_loe`. The `dst` register field across all 16
  `imad` instances ranges only **0–26**; the final result (`observed_inline`) matched the
  independently host-recomputed expression exactly.

### CLZ / popcount (INT-09, INT-10) — `int0910_clz`, `int0910_popcount_baseline`

- `clz` boundary sweep (0, 1, 2, 3, 0x7FFFFFFF, 0x80000000, 0x80000001, 0xFFFFFFFF, 0x00008000,
  0x00000100, 0x40000000, 0x55555555, 0xAAAAAAAA): exact `clz32` (0→32, 1→31, 0x80000000→0) in
  all 13 rows.
- `_agc.main`: `clz` = 64 bytes, `['get_sr','device_load','ibitcount','iadd2','isel10',
  'device_store','stop']` (5 non-boilerplate instructions: one `ibitcount`, then `iadd2` +
  `isel10`). `popcount` (same input sweep) = 44 bytes, `['get_sr','device_load','ibitcount',
  'device_store','stop']` — a single `ibitcount` instance, no follow-on arithmetic.

### Logic LUT (INT-12) — `int12_logic00`..`int12_logic15`

16 canonical two-input Boolean functions, runtime `a`/`b`. Functional: all 16 exact against
`oracle.logic_lut` (5 rows each, incl. all-0/all-1/alternating patterns). Structural (per-function
`_agc.main`, tabulated in `analysis/structural_report.json::INT12_logic16`):

| idx | function | mnemonics | notes |
|---|---|---|---|
| 0 | constant `0` | `get_sr, reg_move_c0, device_store, stop` | folds to a register move, no logic op |
| 1 | `a & b` | `..., ilogic, ...` | `fields: lut_a=0, lut_b=0` |
| 2 | `a & ~b` | `..., ilogic, ...` | `lut_a=2, lut_b=0`, operands swapped vs #4 |
| 3 | `a` | `get_sr, device_load, device_store, stop` | pure passthrough, no ALU op |
| 4 | `~a & b` | `..., ilogic, ...` | `lut_a=2, lut_b=0`, operands swapped vs #2 |
| 5 | `b` | `get_sr, device_load, device_store, stop` | pure passthrough |
| 6 | `a ^ b` | `..., ilogic, ...` | `lut_a=2, lut_b=8` |
| 7 | `a \| b` | `..., ilogic, ...` | `lut_a=2, lut_b=8`, operands swapped vs #6 |
| 8 | `~(a\|b)` (NOR) | `..., ilogic, ...` | `lut_a=1, lut_b=0` |
| 9 | `~(a^b)` (XNOR) | `..., ilogic, ...` | `lut_a=1, lut_b=0`, operands swapped vs #8 |
| 10 | `~b` | `get_sr, device_load, funary, device_store, stop` | dedicated unary op, NOT `ilogic` |
| 11 | `a \| ~b` | `..., ilogic, ...` | `lut_a=3, lut_b=0` |
| 12 | `~a` | `get_sr, device_load, funary, device_store, stop` | dedicated unary op, NOT `ilogic` |
| 13 | `~a \| b` | `..., ilogic, ...` | `lut_a=3, lut_b=0`, operands swapped vs #11 |
| 14 | `~(a & b)` (NAND) | `..., ilogic, ...` | `lut_a=3, lut_b=8` |
| 15 | constant all-ones | `get_sr, mov_imm, iminmax, device_store, stop` | folds to an immediate + min/max clamp, no logic op |

Every `ilogic` instance's `fields` dict has genuinely varying `lut_a` (∈{0,1,2,3}) and `lut_b`
(∈{0,8}) sub-fields (confirmed by direct field inspection, not just op-name/length), plus operand
order (`srcA`/`srcB`) swapping between the four asymmetric-function pairs (2/4, 6/7, 8/9, 11/13).

### u64 carry-generate (INT-13, INT-14) — `int1314_u64add`, `int13_u64add_expr`

- Plain `a+b`: exact for all 6 boundary pairs. `_agc.main` disassembles to `get_sr, device_load,
  device_load, iadd2, carry_gen, psel, iadd2, iadd2, device_store, stop` — `carry_gen`
  **immediately** follows the low-word `iadd2` and is immediately followed by `psel` then the
  high-word `iadd2` chain, in every one of the 6 rows (same static code, so this is one
  compilation, exercised functionally 6 times).
- `(a+b)+c` embedded shape: exact for all 3 boundary triples. `_agc.main`: `get_sr, device_load×3,
  iadd2, iadd2, carry_gen, psel, iadd2, iadd2, carry_gen, psel, iadd2, iadd2, device_store, stop`
  — **two** `carry_gen` instances, each still immediately adjacent to the specific `iadd2` whose
  overflow it tests, in a different compiled context than the first shape.
- No independent-source splice of `carry_gen`'s own operand fields was attempted (INT-14 scoping,
  see PRE_REGISTRATION.md §3).

### Pack/unpack half2x16 (PACK-01, PACK-02) — `pack0102_pack_half2x16`, `pack0102_unpack_half2x16`

- Pack (`float2 -> half2 -> as_type<uint>`): exact `pack_half_2x16` (via `f16_encode_exact`) for
  all 7 rows incl. fp16 max/min-normal and overflow-to-±inf. `_agc.main`: `get_sr, device_load,
  cvt_f2h_dst, cvt_f2h_dst, device_store, stop` — **two `cvt_f2h_dst` (native float→half convert)
  instances, zero `ibfins`/mask/shift/combine instructions.**
- Unpack (`uint -> as_type<half2> -> float2`): exact for all 10 rows incl. NaN(0x7E00)/Inf(0x7C00)
  lanes (NaN-aware comparison). `_agc.main`: `get_sr, device_load, falu2, falu2, device_store,
  stop` — two `falu2` (general float-ALU) instances, no dedicated "unpack" mnemonic and no
  `ibfins`/mask-shift-combine either.

### Snorm/unorm 2x16 (PACK-03, PACK-04, PACK-05, PACK-06) — `pack0304_pack_snorm2x16`,
`pack0304_unpack_snorm2x16_exhaustive`, `pack0506_pack_unorm2x16_edge`, `pack0506_unpack_unorm2x16_exhaustive`

- `pack_float_to_snorm2x16`: exact for 7 rows. `_agc.main` = 46 bytes, `get_sr, device_load,
  pack_convert, device_store, stop` — **byte-length-identical** to `pack_float_to_unorm2x16`'s
  edge-case kernel (also 46 bytes, also `pack_convert`).
- `pack_float_to_unorm2x16` boundary/exceptional sweep (10 rows: negative, >1, both-lane-NaN
  combinations, ±Inf, subnormal-magnitude, three genuine exact-tie fractions built via exact
  `Fraction` arithmetic on the float32-snapped input): **10/10 exact**, including
  round-to-nearest-**even** at the one true tie (`N=32767`, `.5` exactly representable in binary32
  → rounds to `32768`, the even neighbor). NaN in either lane clamps to that lane's packed `0`.
- `unpack_snorm2x16_to_float` / `unpack_unorm2x16_to_float`: **EXHAUSTIVE** — every one of the
  65536 possible 16-bit lane bit patterns, one dispatch each (`gid | (gid<<16)`, low lane read
  back): **65536/65536 bit-exact** for both. Both disassemble to `get_sr, n3_mov, n3_mov,
  shift_amt_move, unpack_convert, device_store, stop` — identical instruction sequence, same
  `unpack_convert` mnemonic.

### 4x8 pack/unpack (PACK-07, PACK-08) — `pack0708_pack_{unorm,snorm}4x8`, `pack07_pack4x8_manual_generic`, `pack0708_unpack_{unorm,snorm}4x8`

- `pack_float_to_unorm4x8`/`pack_float_to_snorm4x8`: both **compile** (confirmed by the 51/51
  compile-smoke check) and both exact for 5 boundary quads each. `_agc.main` disassembles to
  `get_sr, device_load, pack_convert, frag_color_pack, device_store, stop` for BOTH — same
  two-instruction tail (`pack_convert` then `frag_color_pack`) in a plain **compute** kernel
  (no fragment stage involved).
- Hand-written generic (non-normalized) 4×8-bit integer pack idiom (`(a&0xFF)|((b&0xFF)<<8)|...`):
  exact for 3 rows, but `_agc.main` is a **15-instruction** sequence (`get_sr, device_load×4,
  ibfins, ibfins, b_alu10_lof, ibitcount, pad_operand, n1_word, iadd2×3, device_store, stop`) —
  no single dedicated op, and notably NOT the same shape as the native `pack_convert`+
  `frag_color_pack` pair.
- `unpack_unorm4x8_to_float`/`unpack_snorm4x8_to_float`: both compile, both exact for 8 rows each
  (incl. round-tripped pack outputs and raw boundary words). Both disassemble to `get_sr,
  device_load, unpack_convert, unpack_convert, device_store, stop` — **two** `unpack_convert`
  instances for both (vs. one for the 2x16 case), same family.

### Half2 exceptional matrix (PACK-09, PACK-10) — `pack0910_half2_{add,mul,fma}`

8 rows each, per-lane exceptional pairs (NaN, ±0, ±Inf, subnormal crossed against ordinary values
in the OTHER lane). All three (`add2`, `mul2`, `fma3`) **exact against the from-scratch, exactly-
rounded `oracle.f16_op` reference** (Fraction-based, genuinely fused for `fma3`) in all 8 rows
each — including every case where one lane is NaN/Inf/subnormal/signed-zero and the other lane is
an ordinary value: **the ordinary lane's result was never corrupted by the other lane's
exceptional value**, in any of the 24 total rows across the three ops.

### Short2 (PACK-11) — `pack11_short2_{add,mul,and}`

- `add`: exact (5 rows, scalar 16-bit wraparound model). `_agc.main`: `get_sr, device_load,
  device_load, iadd2, iadd2, device_store, stop` — **two independent `iadd2`** instances (no
  packed-2-lane op).
- `mul`: exact (5 rows). `_agc.main`: `..., imad, imad, ...` — **two independent `imad`**
  instances (multiply lowered through the IMAD path with an implicit zero addend, not a plain
  2-input multiply op).
- `and`: exact (5 rows). `_agc.main`: `get_sr, device_load, device_load, mov_zext16,
  pad_operand×3, mov_zext16, mov_imm, pad_operand×2, device_store, stop` — a materially
  **different** shape from `add`/`mul`: two `mov_zext16` (zero-extend-to-16-bit move) instances
  plus an `mov_imm` and several `pad_operand` tokens, and **no `ilogic` instance at all**. See
  INTERPRETED below.

---

## INTERPRETED (supported by the above, not itself observed)

- **INT-01/02/11 (extract/insert boundary):** the **source-level compiled behavior** of
  `extract_bits`/`insert_bits` does **not** implement "mask offset mod 32, clamp width to 32" as
  a single uniform rule. It implements: `cnt==0` → no-op/zero; `cnt==32` **exactly** → the width
  field short-circuits the whole operation, returning the un-shifted operand with the offset
  having no effect whatsoever (not even for enormous offsets); every other `cnt` (`1..31` or
  `>32`) → a literal, unmasked shift by `off` (an `off>=32` shifts the field out of existence).
  This is a genuine three-way disjoint behavior, not equivalent to either of the two originally-
  hypothesized simpler models. **This behavior is established at the level of "what Metal's
  compiler emits for `extract_bits(a,off,cnt)`/`insert_bits(base,val,off,cnt)` with RUNTIME
  operands", not "what the raw single hardware `ibfe`/`ibfins` instruction alone does when its
  encoded width field is exactly 32."** With runtime `off`/`cnt`, extract compiles to `ibfe` PLUS
  three more instructions (`ibfins`, `b_alu10_loe`, `n2_op6`) before the store — a materially
  larger body than EXP-0033's single-`ibfe`-op finding, which used COMPILE-TIME-CONSTANT
  `off`/`cnt` the compiler could statically prove `!=32` and therefore never needed to guard.
  It is plausible (but **not established by this experiment**) that the extra instructions are
  the compiler's own cnt==32 detection-and-blend logic layered in software on top of a raw `ibfe`
  that does NOT itself bypass the offset — i.e. MODEL D may be a **compiler-contract** fact (safe
  to rely on when using Metal-generated code as a template) rather than a **raw-instruction**
  fact (which would need an independent splice of `ibfe` alone, with an explicit `width=32`
  field, to confirm or refute). `insert_bits` similarly remains multi-instruction on this fresh
  M4 compile — three `ibfins`-family instances (distinct `form` sub-field values 0/16/32) plus
  two `b_alu10_loe` helper ALU ops for one source-level `insert_bits` call — consistent with (and
  a finer-grained refinement of) EXP-0033's A18 finding of a mask/shift/combine lowering; the
  mnemonic naming has evidently been refined since EXP-0033 (all three steps now share the
  `ibfins` family name, distinguished by an internal `form` field, rather than EXP-0033's three
  unrelated-looking byte0 values), but the underlying claim (no single dedicated insert
  instruction) still stands.
- **INT-04/05/06 (rotate):** immediate rotate is unambiguously a **single 12-byte `irotate`**
  instruction whenever the (compiler-pre-reduced) amount is non-zero mod 32, and the compiler
  performs the modulo-32 reduction **at AIR-compile time** for compile-time-constant amounts
  (proving `imm33`'s compiled bytes are byte-identical to `imm1`'s, not merely producing the same
  numeric answer via a different encoding). Runtime-amount rotate is unambiguously a
  **multi-instruction expansion** (10 instructions total, `ibfins`+`iadd2`+`ibfe`+
  `shift_amt_move` doing the actual funnel-shift-and-combine work) — there is no one-instruction
  dynamic rotate form on this hardware. The `tex_coord_setup` label in that token stream is very
  likely a **naming collision** in `tools/agx-isa`'s current `db.json` (this kernel is a pure
  compute integer kernel with no texture access whatsoever), not a real texture-subsystem
  instruction being emitted here — flagged as a DB accuracy issue for `tools/agx-isa`, not
  asserted as a hardware fact.
- **INT-07 (IMAD wrap):** confirmed exact 2^32/2^32 (signed) wraparound, matching NIR's `imad`
  contract, with no rounding/saturation observed at any tested boundary.
- **INT-08 (IMAD register range):** the register-pressure probe is **inconclusive for the
  ≥64-register claim**, not merely "not yet tried harder" — the compiler chose to lower the
  40-term reduction as a *tree* of paired multiply-adds (16 separate `imad`s) rather than
  serializing through one heavily-loaded accumulator, which kept every observed `dst` register
  index in 0–26. This is itself informative (compilers naturally avoid extreme register pressure
  by restructuring the dataflow), but it means this probe design cannot answer INT-08 as posed;
  the item remains genuinely open pending the register≥64-addressing blocker.
- **INT-09 (find-MSB):** still a **derived**, not directly isolated, answer: `clz`'s own compiled
  body (`ibitcount` → `iadd2` → `isel10` → store) is consistent with the EXP-0033 (A18)
  decomposition (a find-MSB-shaped primitive, a subtract-from-31, and a zero-clamp select), now
  independently re-confirmed structurally on M4 (three non-trivial ops present, in the same
  relative order), and `clz`'s own boundary values (0→32, 1→31, 0x80000000→0) are exactly what
  that decomposition predicts. `31 - clz(x)` for `x != 0` therefore gives `0x80000000 -> 31`,
  `1 -> 0` — the `ufind_msb` convention, not `ufind_msb_rev` (which would need no subtraction at
  all). The find-MSB primitive's OWN standalone output was not read back directly (would require
  splicing out the subtract/clamp trailer — scoped out, see PRE_REGISTRATION.md).
- **INT-10 (CLZ compound):** confirmed structurally — `clz`'s body has 3 non-trivial instructions
  (`ibitcount`, `iadd2`, `isel10`) vs. `popcount`'s single `ibitcount`, on the SAME op family,
  same input sweep, same fresh M4 compile.
- **INT-12 (logic LUT):** the honest answer is **not a uniform "yes"**. There genuinely is one
  `ilogic` instruction with a real, non-trivial LUT-selector (`lut_a` 2 bits + `lut_b` 1 bit
  observed varying, i.e. a field wide enough for at least 8 distinct codes) plus operand-order
  swapping, and it covers 10 of the 16 canonical functions in this compiler-emitted corpus (AND,
  NAND, OR, NOR, XOR, XNOR, and the two AND-NOT/OR-NOT pairs in both operand orders). But the two
  **projections** (`a`, `b` alone) never reach an ALU op at all (free), the two **negations**
  (`~a`, `~b`) go through a **different, dedicated `funary`** op rather than `ilogic`, and the two
  **degenerate constants** (`0`, all-ones) fold to `reg_move`/`mov_imm`+`iminmax` paths that never
  touch `ilogic` either. Whether `ilogic`'s LUT field could ALSO encode the negations/projections/
  constants if driven directly (rather than via what the compiler happens to emit for these exact
  10 MSL expressions) is **not established** — this experiment observed compiler-chosen encodings,
  not an exhaustive splice sweep of the raw `lut_a`/`lut_b` field, so INT-12 is answered as
  **PARTIAL**: a real multi-value LUT selector exists and is confirmed load-bearing for 10 of the
  16 functions; whether it is a complete, splice-provable 16-function generic LUT is open.
- **INT-13 (carry-generate adjacency):** confirmed in TWO independently compiled contexts (plain
  sum, and a sum embedded in a larger three-operand expression) that `carry_gen` is emitted
  immediately adjacent to its specific producing `iadd2`, never detached, never reused across
  unrelated adds. This is compiler-emitted-instance evidence (every instance we can observe is
  adjacent), not proof the hardware enforces adjacency (INT-14's job, deferred).
- **PACK-01/02 (pack/unpack half2x16):** the pack direction is unambiguously **native and
  dedicated** — two `cvt_f2h_dst` convert instructions, with no generic-bitfield lowering
  signature (`ibfins`/mask-shift-combine) anywhere in the body. The unpack direction is more
  subtle: it compiles through the GENERAL `falu2` float-ALU op (used elsewhere for ordinary
  arithmetic, per EXP-0090/EXP-0099's `falu2` characterization), not a dedicated "unpack" mnemonic
  and not `unpack_convert` either (the family used for snorm/unorm unpack, see below) — the
  half-unpack is evidently realized as an `falu2`-family type-conversion mode rather than a
  standalone unpack primitive. Both directions are clean of the generic `ibfins` signature either
  way, so PACK-01/02's core question ("without generic integer bitfield lowering") is answered
  YES for both, with the caveat that "native conversion/pack sequence" for unpack specifically
  means "the general float ALU's convert mode," not a dedicated unpack opcode.
- **PACK-03/04 (snorm2x16 family membership):** directly confirmed by TOKEN NAME, not just byte
  length coincidence — `pack_float_to_snorm2x16` and `pack_float_to_unorm2x16` both compile to a
  single `pack_convert` instruction; `unpack_snorm2x16_to_float` and `unpack_unorm2x16_to_float`
  both compile to a single `unpack_convert` instruction. This is the strongest possible
  confirmation available without splicing the format-select sub-field directly.
- **PACK-05/06 (unorm2x16 rounding/exhaustive):** the earlier-appearing "tie rounding" anomaly in
  the pilot phase was a **methodology artifact** (float64 approximation of an intended exact tie),
  not a hardware finding — once corrected to exact `Fraction` arithmetic on the actual float32
  input, the hardware's rounding is round-to-nearest **with ties resolved to the even neighbor**,
  matching the standard `packUnorm`/IEEE754-style contract exactly, with correct NaN→0/negative→0/
  >1→max clamping. PACK-06's exhaustive 65536/65536 match is as strong an "every 16-bit lane
  value" result as this method can produce.
- **PACK-07/08 (4x8):** the NORMALIZED float packs (`pack_float_to_{unorm,snorm}4x8`) ARE native,
  but as a **two-instruction** sequence (`pack_convert` + `frag_color_pack`), not one — and the
  second instruction's name (`frag_color_pack`, presumably named from a fragment-output-writing
  context in `tools/agx-isa`'s corpus) appearing in a plain compute kernel is worth flagging: EITHER
  the same physical instruction genuinely serves both a general 4-lane pack role and a
  fragment-color-pack role (plausible — packing 4 normalized components into one word is exactly
  what fragment output packing also needs), OR `tools/agx-isa`'s naming for this byte pattern is
  narrower than its true role. This experiment cannot distinguish those without deeper `db.json`
  provenance review, and reports the observed mnemonic as-is rather than asserting either reading.
  The hand-written GENERIC (non-normalized) 4×8 integer gather is **conclusively NOT native** — 15
  instructions, `ibfins`-based, matching the already-established `insert_bits` lowering shape, not
  the 2-op native pack path. `pack_32_4x8`'s answer is therefore: normalized-format packing is
  native (2 ops); a generic integer 4x8 pack is not.
- **PACK-09/10 (half2 lane independence):** conclusively demonstrated across `add`/`mul`/`fma`
  and every tested exceptional-value class (NaN, ±0, ±Inf, subnormal) — the packed 2-lane op never
  let one lane's exceptional operand corrupt the other lane's ordinary result, in 24/24 rows.
- **PACK-11 (short2 absence of packed ALU):** `add` and `mul` cleanly confirm the EXP-0033
  finding (two independent 32-bit ops, `iadd2`×2 / `imad`×2) — extending it from A18-only-`add` to
  fresh M4 evidence for both `add` and `mul`. `and`'s different shape (`mov_zext16` + `mov_imm` +
  `pad_operand` tokens, no `ilogic`) is a genuine surprise: it does NOT decompose the same way as
  add/mul, and does NOT reach a packed-2-lane op either. The most likely reading is that MSL's
  `short2 & short2` on signed 16-bit lanes routes through a zero-extension-based bitwise idiom
  distinct from the plain integer `ilogic` path used for the 32-bit logic functions above — but
  this experiment did not isolate why, so PACK-11's core negative claim (no packed 2-lane int ALU)
  still holds for all three tested forms, while the EXACT decomposition of `and` specifically is
  reported as observed, not fully explained.

---

## Exact tested range

Every numeric claim above is bounded by the exact rows enumerated in `analysis/casematrix.py`
(122/256/64/13/40/16×5/6+3/7+10/10/exhaustive-65536×2/5×3/8×3/5×3 rows per case family, as
tabulated in OBSERVED). Nothing above is generalized past its tested set except where explicitly
marked `INFERRED`/`PARTIAL` (INT-08, INT-09, INT-12, INT-14). Rotate/IMAD/shift amounts were swept
at boundary/representative points (0,1,16,31,32,33,63,64,65,127,128,255,256,1000,2^31,2^32-1), not
exhaustively over the full 32-bit domain — the one case where full exhaustion was both feasible and
performed is the two 16-bit-lane unpack cases (PACK-04/06, 65536/65536).

## Target and scope label

**M4/G16G only, HW-PROBE + OWN-SHADER.** No A18 Pro claim; the standing target-equivalence
argument (`docs/isa/README.md`, `EXP-M4-*`) applies as project policy, not as independent
re-validation performed here.

---

## Finite-resource rows

| Namespace/resource | Scope | Encoding | Exact usable range/count | Holes/reserved | First invalid value | Observed failure | Correct "need more" fallback | Evidence |
|---|---|---|---:|---|---:|---|---|---|
| `extract_bits`/`insert_bits` width (`cnt`) | per-instruction, runtime GPR | width field, tested 0–2^32-1 | `0`→no-op; `1..31`→literal partial mask; `32` EXACTLY→verbatim bypass; `33..2^32-1`→literal full-32-bit mask (same as `>=32` clamp, offset still literal) | none observed — every value produces a defined, deterministic result, no faults | n/a — no value faulted | n/a (never faults; behavior changes discretely at `cnt==32`) | compiler must special-case `cnt==32` as a distinct code path, never assume "clamp to 32" covers it | `int0102_extract_unsigned`/`int11_insert_bits`, `raw/m4-20260828T063920Z-run01` |
| `extract_bits`/`insert_bits` offset (`off`) | per-instruction, runtime GPR | shift-amount field, tested 0–2^32-1 | literal/unmasked for `cnt != 32`: `0..31` shifts normally, `>=32` shifts the field out entirely (zero contribution); IGNORED ENTIRELY when `cnt==32` | none observed | n/a — no value faulted | field silently contributes 0 once `off>=32` (for `cnt!=32`); silently ignored for `cnt==32` | never assume NIR's "mask offset mod 32" — emit the literal offset and let the hardware's own `>=32` zero-contribution behavior apply, EXCEPT special-case `cnt==32` | same as above |
| Rotate amount (immediate, compile-time) | per-instruction, AIR-constant-folded | 12-byte `irotate`, tested K∈{0,1,31,32,33,63,64} | effectively unbounded input value, reduced mod 32 by the COMPILER before emission (K=0/32/64 fold away entirely; K=33≡K=1 byte-identical) | none | n/a | n/a | compiler-side mod-32 reduction is already correct/required; no runtime masking needed for the immediate path | `int04_rotate_imm*`, `analysis/structural_report.json` |
| Rotate amount (runtime GPR) | per-instruction, runtime GPR | multi-instr `ibfins+iadd2+ibfe+shift_amt_move`, tested 16 boundary values incl. 2^31, 2^32-1 | full 32-bit domain, hardware/codegen applies mod-32 wrap (`n mod 32`) for every tested value | none observed | n/a | n/a (all 64 rows exact) | no native single-op dynamic rotate exists; the compiler MUST emit the 4-op expansion, mod-32 already correctly applied | `int0506_rotate_var` |
| `ilogic` LUT selector (`lut_a`,`lut_b`) | per-instruction | 2-bit `lut_a` (0–3) + 1-bit `lut_b` (0/8) observed varying across 10 compiler-emitted functions | **PARTIAL/OPEN** — only 8 of the field's apparent ≥8-code space were exercised via compiler-chosen MSL expressions; the 6 remaining two-input functions (2 projections, 2 negations, 2 constants) never route through `ilogic` in this compiler's output, so whether the SAME field could encode them via direct construction is untested | unknown — no splice sweep performed | unknown | n/a | do not assume `ilogic` alone realizes all 16 canonical functions; emit `funary`/`reg_move`/`mov_imm` for the 6 that this compiler routes elsewhere, until a direct field sweep says otherwise | `int12_logic*`, `analysis/structural_report.json::INT12_logic16` |
| IMAD register operand range | per-instruction | `dst`/`srcB`/`srcC_lo` fields, single best-effort register-pressure probe | **PARTIAL/OPEN** — observed `dst` values only 0–26 under 40-live-temporary pressure; probe did not force allocation into the ≥64 range (compiler restructured the reduction as a multiply-add tree instead of a long dependency chain) | unknown | unknown | n/a | do not assume IMAD's encoding is capped near register 26 — this is a probe-design limitation, not a hardware ceiling; the actual 0–95 (or wider) capability remains bound to the project-wide register≥64-addressing blocker | `int08_imad_register_pressure` |

---

## Required response blocks (format copied from `APPLE9_RE_IMPLEMENTATION_GAPS.md`)

### INT-01

```text
Status: [x] Closed
Answer, where Yes/No: [x] Yes
Applies to: [ ] A18 Pro/G17P  [x] M4/G16G  [ ] both tested independently
Evidence: [x] independently assembled HW execution  [ ] HW splice
          [ ] API create/submit/exhaustion test       [ ] Linux end-to-end UAPI test
          [ ] captured userspace/command memory      [ ] encode/decode round trip
          [ ] own-MSL byte diff only                 [ ] corpus inference only
Test/artifact: experiments/EXP-0102-m4-int-pack-semantics/, case
    int0102_extract_unsigned, cnt==0 rows (24/122), raw/m4-20260828T063920Z-run01
    (byte-identical to run02).
Exact observed semantics or field mapping: extract_bits(data, off, 0) == 0 for
    every tested (data, off) combination (6 data patterns x 4 offsets).
Finite namespace: width field, value 0 -> always 0, no exception.
Maximum-valid and first-invalid tests: n/a (0 is a fully valid, defined width).
Failure/overflow behavior: [ ] reject  [x] zero/discard  [ ] alias/wrap  [ ] fault/device loss
Correct behavior when the compiler/driver needs more: none needed; width==0 is a
    legal, deterministic zero-producing case, safe to emit directly.
Lifetime, destruction, and reuse semantics: n/a.
Counterexamples and untested cases: only 6 `data` values x 4 `off` values tested
    at cnt==0; not exhaustive over the full 32-bit `data` domain (result is
    architecturally independent of `data` when cnt==0, so this is not expected
    to matter, but was not exhaustively proven).
Driver/compiler consequence: extract_bits with a runtime-zero width can be
    lowered directly to the native op; no software zero-check is required.
```

### INT-02

```text
Status: [x] Closed
Answer, where Yes/No: [x] No
Applies to: [ ] A18 Pro/G17P  [x] M4/G16G  [ ] both tested independently
Evidence: [x] independently assembled HW execution  [ ] HW splice
          [ ] API create/submit/exhaustion test       [ ] Linux end-to-end UAPI test
          [ ] captured userspace/command memory      [ ] encode/decode round trip
          [ ] own-MSL byte diff only                 [ ] corpus inference only
Test/artifact: case int0102_extract_unsigned, 122-row boundary sweep,
    raw/m4-20260828T063920Z-run01 (byte-identical run02).
Exact observed semantics or field mapping: MODEL D (see OBSERVED/INTERPRETED
    above) -- NOT NIR's presumed "mask offset mod 32, clamp width to 32":
    cnt==32 EXACTLY bypasses the offset entirely (verbatim passthrough, even
    for off==2^32-1); cnt in {1..31} or {33..2^32-1} applies off as a LITERAL
    (unmasked) shift, off>=32 zeroing the contribution. IMPORTANT SCOPE NOTE:
    this is the SOURCE-LEVEL compiled behavior of Metal's extract_bits with
    RUNTIME off/cnt (compiled body: ibfe + ibfins + b_alu10_loe + n2_op6 +
    store), not a splice-isolated reading of the raw `ibfe` instruction
    alone -- whether the cnt==32 bypass is a raw hardware `ibfe` behavior or
    software logic the compiler adds around a plainer `ibfe` was NOT
    distinguished by this experiment (see structural.py output for
    int0102_extract_unsigned).
Finite namespace: off tested 0..2^32-1 at representative boundary points; cnt
    tested 0..2^32-1 at representative boundary points including 31/32/33.
Maximum-valid and first-invalid tests: no value faulted; behavior is fully
    defined (if surprising) at every tested point, including off=cnt=2^32-1.
Failure/overflow behavior: [ ] reject  [x] zero/discard  [ ] alias/wrap  [ ] fault/device loss
Correct behavior when the compiler/driver needs more: a NIR-targeting backend
    should REPLICATE the observed compiled sequence's contract (ibfe result,
    with an explicit cnt==32 check overriding it to the verbatim operand, and
    off applied literally/unmasked otherwise) rather than emitting a bare
    `ibfe` and trusting it to reproduce NIR's masking assumptions -- whether
    a bare spliced `ibfe` alone already does this is an open follow-up (see
    Counterexamples).
Lifetime, destruction, and reuse semantics: n/a.
Counterexamples and untested cases: the offset x width space was swept at
    representative points, not exhaustively (2^64 combinations); a hole
    between tested points cannot be ruled out with certainty, though the
    tested points are dense enough near every observed transition (28,30,
    31,32,33,40) to be confident about the discrete cnt==32 special case.
    RECOMMENDED FOLLOW-UP: independently assemble a bare `ibfe` instruction
    (no surrounding ibfins/b_alu10_loe/n2_op6) with an explicit width field
    of 32 and splice-execute it to determine whether the cnt==32 bypass is
    intrinsic to the raw hardware op or added by the compiler.
Driver/compiler consequence: NIR's `nir_op_ubfe` legalization for Apple9 must
    emit an explicit cnt==32 check (select/branch or a distinct instruction
    form) rather than relying on hardware clamping to reproduce NIR semantics
    -- this is proven true of Metal's OWN compiled output and is the safe
    default; it is not yet proven whether the raw ibfe instruction needs this
    help or already provides it.
```

### INT-03

```text
Status: [x] Closed
Answer, where Yes/No: [x] Yes
Applies to: [ ] A18 Pro/G17P  [x] M4/G16G  [ ] both tested independently
Evidence: [x] independently assembled HW execution  [ ] HW splice
          [ ] API create/submit/exhaustion test       [ ] Linux end-to-end UAPI test
          [ ] captured userspace/command memory      [ ] encode/decode round trip
          [x] own-MSL byte diff only                 [ ] corpus inference only
Test/artifact: case int03_extract_signed, same 122 rows as INT-01/02, plus
    structural byte-diff vs the unsigned kernel.
Exact observed semantics or field mapping: signed result == MODEL D's
    unsigned result, sign-extended over min(cnt,32) bits, in all 122 rows;
    no row showed a hidden signed mode (i.e. no row's signed result was
    inconsistent with a plain post-hoc sign extension of the unsigned MODEL
    D value).
Finite namespace: same as INT-02.
Maximum-valid and first-invalid tests: n/a.
Failure/overflow behavior: [ ] reject  [x] zero/discard  [ ] alias/wrap  [ ] fault/device loss
Correct behavior when the compiler/driver needs more: emit unsigned extract
    (MODEL D semantics) then an explicit sign-extend shift pair for signed
    extract_bits, exactly as EXP-0033 found on A18 -- this M4 run finds no
    counterexample across the boundary sweep.
Lifetime, destruction, and reuse semantics: n/a.
Counterexamples and untested cases: same representative-not-exhaustive
    caveat as INT-02; a structural (not splice) evidence tier only.
Driver/compiler consequence: no dedicated single-instruction signed-extract
    form should be assumed; lower signed extract_bits to unsigned+sign-extend.
```

### INT-04

```text
Status: [x] Closed
Answer, where Yes/No: [x] Yes
Applies to: [ ] A18 Pro/G17P  [x] M4/G16G  [ ] both tested independently
Evidence: [x] independently assembled HW execution  [ ] HW splice
          [ ] API create/submit/exhaustion test       [ ] Linux end-to-end UAPI test
          [ ] captured userspace/command memory      [ ] encode/decode round trip
          [x] own-MSL byte diff only                 [ ] corpus inference only
Test/artifact: cases int04_rotate_imm{0,1,31,32,33,63,64}, functional +
    structural (analysis/structural_report.json::INT04_INT06_rotate).
Exact observed semantics or field mapping: rotl32(a, K mod 32) for all 7
    tested K and 4 base values (28 rows). Byte-identical compiled bodies
    confirm the compiler applies the mod-32 reduction AT COMPILE TIME:
    imm0==imm32==imm64 (fold to identity, no rotate op emitted at all),
    imm31==imm63, imm33==imm1.
Finite namespace: amount field effectively unbounded as source syntax (any
    uint32 literal), always reduced mod 32 before reaching the single
    12-byte `irotate` op.
Maximum-valid and first-invalid tests: n/a -- no invalid immediate amount
    exists; every uint32 literal is legal source and produces a defined
    (mod-32) result.
Failure/overflow behavior: [ ] reject  [ ] zero/discard  [x] alias/wrap  [ ] fault/device loss
Correct behavior when the compiler/driver needs more: none needed.
Lifetime, destruction, and reuse semantics: n/a.
Counterexamples and untested cases: 7 K values tested (0,1,31,32,33,63,64);
    not exhaustive over all uint32 K, but the byte-identity results give
    strong structural confidence the compiler does simple K mod 32 folding.
Driver/compiler consequence: NIR urol/uror with a constant amount can be
    pre-reduced mod 32 in the backend and emitted as the single `irotate`
    op directly.
```

### INT-05

```text
Status: [x] Closed
Answer, where Yes/No: [x] Yes
Applies to: [ ] A18 Pro/G17P  [x] M4/G16G  [ ] both tested independently
Evidence: [x] independently assembled HW execution  [ ] HW splice
          [ ] API create/submit/exhaustion test       [ ] Linux end-to-end UAPI test
          [ ] captured userspace/command memory      [ ] encode/decode round trip
          [ ] own-MSL byte diff only                 [ ] corpus inference only
Test/artifact: case int0506_rotate_var, 64 rows (4 base values x 16 runtime
    amounts incl. 0,1,16,31,32,33,63,64,65,127,128,255,256,1000,2^31,2^32-1).
Exact observed semantics or field mapping: rotl32(a, n mod 32) exact in all
    64 rows.
Finite namespace: runtime amount, full 32-bit domain, mod-32 wrap confirmed
    at every tested boundary/representative point.
Maximum-valid and first-invalid tests: n/a -- no invalid runtime amount;
    2^32-1 and 2^31 both produced the mod-32-correct result.
Failure/overflow behavior: [ ] reject  [ ] zero/discard  [x] alias/wrap  [ ] fault/device loss
Correct behavior when the compiler/driver needs more: none needed; the
    4-instruction expansion already implements full mod-32 semantics.
Lifetime, destruction, and reuse semantics: n/a.
Counterexamples and untested cases: 16 representative amounts tested per
    base value, not exhaustive over the full 2^32 amount domain.
Driver/compiler consequence: preserved NIR urol/uror with a non-constant
    amount can rely on the hardware/codegen's own mod-32 wrap; no additional
    software masking is required before emitting the expansion.
```

### INT-06

```text
Status: [x] Closed
Answer, where Yes/No: [x] Yes
Applies to: [ ] A18 Pro/G17P  [x] M4/G16G  [ ] both tested independently
Evidence: [x] independently assembled HW execution  [ ] HW splice
          [ ] API create/submit/exhaustion test       [ ] Linux end-to-end UAPI test
          [ ] captured userspace/command memory      [ ] encode/decode round trip
          [x] own-MSL byte diff only                 [ ] corpus inference only
Test/artifact: analysis/structural_report.json::INT04_INT06_rotate (built
    from the already-captured, gated int04_rotate_imm31 and int0506_rotate_var
    bytes -- no new hardware contact).
Exact observed semantics or field mapping: the runtime-amount kernel's
    _agc.main disassembles to 10 instructions (get_sr, device_load x2,
    tex_coord_setup[likely a DB-naming artifact], ibfins, iadd2, ibfe,
    shift_amt_move, device_store, stop) vs. the immediate kernel's single
    `irotate`. 98 bytes vs 48 bytes for the same logical operation.
Finite namespace: n/a (structural/existence claim, not a range).
Maximum-valid and first-invalid tests: n/a.
Failure/overflow behavior: [ ] reject  [ ] zero/discard  [ ] alias/wrap  [ ] fault/device loss
Correct behavior when the compiler/driver needs more: emit the 4-op
    expansion for any non-constant rotate amount; do not search for a
    single-op dynamic form.
Lifetime, destruction, and reuse semantics: n/a.
Counterexamples and untested cases: only one runtime-amount kernel shape was
    compiled; a different MSL idiom for the same rotate might in principle
    compile differently, though this would be surprising given INT-04's
    strong compile-time-fold evidence for the immediate path.
Driver/compiler consequence: confirms INT-04-INT-06 jointly license
    legalizing NIR urol/uror to the immediate `irotate` for constant amounts
    and the dynamic 4-op expansion otherwise -- never a hypothetical
    single-op dynamic form.
```

### INT-07

```text
Status: [x] Closed
Answer, where Yes/No: [x] Yes
Applies to: [ ] A18 Pro/G17P  [x] M4/G16G  [ ] both tested independently
Evidence: [x] independently assembled HW execution  [ ] HW splice
          [ ] API create/submit/exhaustion test       [ ] Linux end-to-end UAPI test
          [ ] captured userspace/command memory      [ ] encode/decode round trip
          [ ] own-MSL byte diff only                 [ ] corpus inference only
Test/artifact: cases int0708_imad_wrap_u (8 rows), int0708_imad_wrap_s (6 rows).
Exact observed semantics or field mapping: (a*b+c) mod 2^32 exactly, for
    both unsigned and two's-complement-signed interpretations, at every
    tested boundary triple (incl. 0xFFFFFFFF*2+1, INT32_MIN*-1+0, -1*-1*-1).
Finite namespace: n/a (arithmetic identity, not a resource count).
Maximum-valid and first-invalid tests: n/a.
Failure/overflow behavior: [ ] reject  [ ] zero/discard  [x] alias/wrap  [ ] fault/device loss
Correct behavior when the compiler/driver needs more: none needed; NIR
    imad's wraparound contract is satisfied directly.
Lifetime, destruction, and reuse semantics: n/a.
Counterexamples and untested cases: 14 total directed boundary triples, not
    a randomized/exhaustive sweep of the full (a,b,c) space.
Driver/compiler consequence: native IMAD can be used directly for NIR
    `imad`/multiply-add lowering with no extra wraparound handling.
```

### INT-08

```text
Status: [ ] Open  [x] Partial  [ ] Closed  [ ] Not applicable
Answer, where Yes/No: [ ] Yes  [ ] No  [x] Unknown
Applies to: [ ] A18 Pro/G17P  [x] M4/G16G  [ ] both tested independently
Evidence: [ ] independently assembled HW execution  [ ] HW splice
          [ ] API create/submit/exhaustion test       [ ] Linux end-to-end UAPI test
          [ ] captured userspace/command memory      [ ] encode/decode round trip
          [x] own-MSL byte diff only                 [ ] corpus inference only
Test/artifact: case int08_imad_register_pressure (1 case, 40 live
    temporaries, --dump-main captured, 1402-byte body, 137 instructions,
    16 imad instances).
Exact observed semantics or field mapping: functional result matched the
    independently host-recomputed expression exactly, but the compiled
    IMAD instances' `dst` register field only reached 0-26 -- the compiler
    restructured the 40-term reduction as a tree of paired multiply-adds
    rather than serializing through a long dependency chain, so register
    pressure never forced allocation past the low range.
Finite namespace: 96-register file (per prior project documentation);
    THIS PROBE established only that registers 0-26 work for IMAD, which
    was never in doubt.
Maximum-valid and first-invalid tests: NOT established by this experiment.
Failure/overflow behavior: [ ] reject  [ ] zero/discard  [ ] alias/wrap  [ ] fault/device loss
Correct behavior when the compiler/driver needs more: unresolved; depends
    on the still-open register>=64 addressing blocker
    (docs/isa/register-move-and-liveness.md SS2.7/EXP-0099), which is a
    DIFFERENT instruction family (falu2) than IMAD (the 0x9f/12-byte
    family per EXP-0033) -- IMAD's own high-register reachability has not
    been independently tested by ANY experiment to date, to this agent's
    knowledge.
Lifetime, destruction, and reuse semantics: n/a.
Counterexamples and untested cases: a probe design that FORCES serialized
    (not tree-shaped) register pressure -- e.g. an explicit sequential
    dependency chain the compiler cannot reorder -- is a recommended
    follow-up, distinct from this experiment's approach.
Driver/compiler consequence: do NOT assume IMAD can address the full
    0-95 (or wider) register range independent of construction; treat as
    UNKNOWN until a dedicated successor experiment (either forcing genuine
    high-register pressure, or independently assembling an IMAD instance
    with an explicit high register field and splice-validating it) closes
    this gap.
```

### INT-09

```text
Status: [x] Closed
Answer, where Yes/No: [x] Yes
Applies to: [ ] A18 Pro/G17P  [x] M4/G16G  [ ] both tested independently
Evidence: [ ] independently assembled HW execution  [ ] HW splice
          [ ] API create/submit/exhaustion test       [ ] Linux end-to-end UAPI test
          [ ] captured userspace/command memory      [ ] encode/decode round trip
          [x] own-MSL byte diff only                 [ ] corpus inference only
Test/artifact: case int0910_clz (13-row boundary sweep) + structural
    re-confirmation of the EXP-0033 (A18) find-MSB/clz decomposition on
    fresh M4-compiled bytes.
Exact observed semantics or field mapping: DERIVED, not directly isolated:
    clz(x) is HW-VALIDATED exact (0->32, 1->31, 0x80000000->0, 13 rows), and
    clz's own compiled body (ibitcount -> iadd2 -> isel10) is structurally
    consistent with "find-MSB primitive, then 31-minus, then zero-clamp
    select" -- under that decomposition, find-MSB(0x80000000)=31,
    find-MSB(1)=0, i.e. the ufind_msb convention (bit-index-from-LSB), NOT
    ufind_msb_rev (which would need no subtraction step at all, since it
    would already equal clz).
Finite namespace: n/a.
Maximum-valid and first-invalid tests: n/a.
Failure/overflow behavior: [ ] reject  [x] zero/discard  [ ] alias/wrap  [ ] fault/device loss
Correct behavior when the compiler/driver needs more: n/a.
Lifetime, destruction, and reuse semantics: n/a.
Counterexamples and untested cases: the find-MSB primitive's OWN standalone
    output was never read back directly (would require splicing out the
    subtract/clamp trailer, scoped out of this experiment -- see
    PRE_REGISTRATION.md); this is DERIVED/OWN-SHADER-DIFF-tier evidence, not
    the stronger direct-isolation tier.
Driver/compiler consequence: confirms `ufind_msb` (not `_rev`) is the
    correct NIR op to target if/when a direct find-MSB primitive is
    exposed; until then, continue lowering via the clz decomposition.
```

### INT-10

```text
Status: [x] Closed
Answer, where Yes/No: [x] Yes
Applies to: [ ] A18 Pro/G17P  [x] M4/G16G  [ ] both tested independently
Evidence: [ ] independently assembled HW execution  [ ] HW splice
          [ ] API create/submit/exhaustion test       [ ] Linux end-to-end UAPI test
          [ ] captured userspace/command memory      [ ] encode/decode round trip
          [x] own-MSL byte diff only                 [ ] corpus inference only
Test/artifact: cases int0910_clz (64 bytes, 3 non-trivial ops) vs
    int0910_popcount_baseline (44 bytes, 1 non-trivial op), same op family
    (ibitcount), same input sweep, same fresh M4 compile.
Exact observed semantics or field mapping: clz = ibitcount + iadd2 + isel10;
    popcount = ibitcount alone. Confirms clz is NOT a single instruction.
Finite namespace: n/a.
Maximum-valid and first-invalid tests: n/a.
Failure/overflow behavior: [ ] reject  [ ] zero/discard  [ ] alias/wrap  [ ] fault/device loss
Correct behavior when the compiler/driver needs more: n/a.
Lifetime, destruction, and reuse semantics: n/a.
Counterexamples and untested cases: none found; consistent with the prior
    A18 finding (EXP-0033), now independently re-confirmed on M4.
Driver/compiler consequence: NIR uclz must remain a lowered sequence
    (find-MSB-shaped primitive + subtract + zero-clamp select), not a
    single Apple9 IR pseudo-op backed by one instruction.
```

### INT-11

```text
Status: [x] Closed
Answer, where Yes/No: [x] Yes (necessarily a multi-instruction sequence)
Applies to: [ ] A18 Pro/G17P  [x] M4/G16G  [ ] both tested independently
Evidence: [x] independently assembled HW execution  [ ] HW splice
          [ ] API create/submit/exhaustion test       [ ] Linux end-to-end UAPI test
          [ ] captured userspace/command memory      [ ] encode/decode round trip
          [x] own-MSL byte diff only                 [ ] corpus inference only
Test/artifact: case int11_insert_bits, 256-row boundary sweep +
    tools/agx-isa tokenization of the same captured bytes.
Exact observed semantics or field mapping: insert_bits is NOT a single
    instruction -- one source-level insert_bits(base,val,off,cnt) call
    compiles to THREE `ibfins`-family instances (distinguished by an
    internal `form` sub-field: 0, 16, 32) plus TWO `b_alu10_loe` helper ALU
    ops, consistent with (and a finer-grained refinement of) EXP-0033's A18
    finding of a mask/shift/combine lowering -- the mnemonic naming has
    evidently been refined in tools/agx-isa since EXP-0033 (all three steps
    now share the `ibfins` family name, distinguished by `form`, rather
    than EXP-0033's three differently-named byte0 values), but the
    underlying claim (no single dedicated insert instruction) still holds.
    Functionally, the 256-row sweep matches the "MODEL D" formula (cnt==0
    no-op, cnt==32 exact bypass, else literal-offset mask/shift/clear/
    combine) exactly, 256/256.
Finite namespace: same off/cnt boundary characterization as INT-02.
Maximum-valid and first-invalid tests: no value faulted.
Failure/overflow behavior: [ ] reject  [x] zero/discard  [ ] alias/wrap  [ ] fault/device loss
Correct behavior when the compiler/driver needs more: continue lowering
    insert_bits to the multi-instruction ibfins-family (mask-clear /
    shift-insert / combine) sequence; no single dedicated op exists to
    target directly.
Lifetime, destruction, and reuse semantics: n/a.
Counterexamples and untested cases: representative-not-exhaustive
    off/cnt/base/val combinations (256 rows); a 40-byte `<unknown>` trailing
    tail in the tokenizer output for this kernel (almost certainly the
    device_store+stop epilogue, going by every other kernel's tail shape)
    indicates a residual byte range tools/agx-isa does not yet name in this
    context -- flagged as a DB coverage gap, not resolved here.
Driver/compiler consequence: CONFIRMS (does not revise) the standing
    "insert_bits has no dedicated single-op form" guidance -- lower to the
    3-instruction ibfins-family + helper-ALU sequence.
```

### INT-12

```text
Status: [x] Closed  [x] Partial (see note)
Answer, where Yes/No: [ ] Yes  [ ] No  [x] Unknown (nuanced -- see below)
Applies to: [ ] A18 Pro/G17P  [x] M4/G16G  [ ] both tested independently
Evidence: [x] independently assembled HW execution  [ ] HW splice
          [ ] API create/submit/exhaustion test       [ ] Linux end-to-end UAPI test
          [ ] captured userspace/command memory      [ ] encode/decode round trip
          [x] own-MSL byte diff only                 [ ] corpus inference only
Test/artifact: 16 cases int12_logic00..15, functional (5 rows each) +
    per-function structural tokenization
    (analysis/structural_report.json::INT12_logic16).
Exact observed semantics or field mapping: a real `ilogic` instruction with
    a varying `lut_a` (2 bits, 0-3) + `lut_b` (1 bit, 0/8) selector plus
    operand-order swapping realizes 10 of the 16 functions (AND, NAND, OR,
    NOR, XOR, XNOR, AND-NOT and OR-NOT in both operand orders). The 2
    projections (a, b) never reach any ALU op (free passthrough). The 2
    negations (~a, ~b) route through a DIFFERENT dedicated `funary` op, not
    `ilogic`. The 2 degenerate constants (0, all-ones) fold to
    `reg_move`/`mov_imm`+`iminmax`, never `ilogic`.
Finite namespace: `ilogic`'s lut_a/lut_b field is wide enough for >=8 codes
    (2+1 bits observed varying); the FULL field width and whether it could
    encode the other 6 functions directly is NOT established (no splice
    sweep of the raw field was performed -- see PARTIAL note).
Maximum-valid and first-invalid tests: not performed (would require
    independently assembling an `ilogic` instance with unobserved lut_a/
    lut_b values and splice-executing it -- explicitly out of this
    experiment's scope, recommended follow-up).
Failure/overflow behavior: [ ] reject  [ ] zero/discard  [ ] alias/wrap  [ ] fault/device loss
Correct behavior when the compiler/driver needs more: for the 10
    compiler-confirmed functions, target `ilogic` directly with the
    observed lut_a/lut_b/operand-order mapping; for the other 6, use the
    observed alternate lowerings (free passthrough / `funary` / `mov_imm`)
    rather than assuming a generic LUT covers them.
Lifetime, destruction, and reuse semantics: n/a.
Counterexamples and untested cases: the 6 non-`ilogic` functions are the
    main open question -- a direct splice test constructing an `ilogic`
    instance with lut_a/lut_b values chosen to predict `~a`/`~b`/`0`/`~0`
    (if the field is a true 4-bit LUT, values 4-7 and 12-15 by the standard
    truth-table encoding) would close this decisively.
Driver/compiler consequence: a NIR backend may target `ilogic` directly for
    the 10 confirmed two-input combining functions; it must NOT assume
    `ilogic` also covers projections/negations/constants without further
    evidence -- use the compiler-observed alternate paths for those.
```

### INT-13

```text
Status: [x] Closed
Answer, where Yes/No: [x] Yes (for every compiler-emitted instance observed)
Applies to: [ ] A18 Pro/G17P  [x] M4/G16G  [ ] both tested independently
Evidence: [ ] independently assembled HW execution  [ ] HW splice
          [ ] API create/submit/exhaustion test       [ ] Linux end-to-end UAPI test
          [ ] captured userspace/command memory      [ ] encode/decode round trip
          [x] own-MSL byte diff only                 [ ] corpus inference only
Test/artifact: cases int1314_u64add, int13_u64add_expr (two different
    compiled expression shapes), structural tokenization of both.
Exact observed semantics or field mapping: in BOTH shapes, every `carry_gen`
    instance is immediately preceded by the specific low-word `iadd2` whose
    overflow it tests and immediately followed by `psel` then the dependent
    high-word add(s) -- re-confirming EXP-0038's A18 finding, fresh on M4.
Finite namespace: n/a.
Maximum-valid and first-invalid tests: n/a.
Failure/overflow behavior: [ ] reject  [ ] zero/discard  [ ] alias/wrap  [ ] fault/device loss
Correct behavior when the compiler/driver needs more: n/a (this item is
    about whether the hardware REQUIRES adjacency, which compiler-emitted
    evidence alone cannot prove -- see INT-14).
Lifetime, destruction, and reuse semantics: n/a.
Counterexamples and untested cases: only compiler-emitted instances were
    examined; no independently constructed non-adjacent `carry_gen` was
    tried (that is INT-14's question, explicitly deferred).
Driver/compiler consequence: a NIR backend targeting Apple9 carry-out should
    always emit `carry_gen` immediately adjacent to its producing add,
    matching the only pattern ever observed to work, until INT-14 is closed.
```

### INT-14

```text
Status: [ ] Open  [x] Partial  [ ] Closed  [ ] Not applicable
Answer, where Yes/No: [ ] Yes  [ ] No  [x] Unknown
Applies to: [ ] A18 Pro/G17P  [x] M4/G16G  [ ] both tested independently
Evidence: [ ] independently assembled HW execution  [ ] HW splice
          [ ] API create/submit/exhaustion test       [ ] Linux end-to-end UAPI test
          [ ] captured userspace/command memory      [ ] encode/decode round trip
          [ ] own-MSL byte diff only                 [x] corpus inference only
Test/artifact: none new -- carried over from EXP-0038's byte-level
    decode of `carry_gen` (6 bytes, compare-family, byte+2==0x35 marker).
Exact observed semantics or field mapping: NOT established this experiment.
    DEFERRED: independently re-sourcing carry_gen's operands via splice was
    scoped out given (a) the standing project-wide warning that a wrong
    operand-field value on this hardware silently zeroes rather than
    faults (docs/isa/register-move-and-liveness.md), and (b) carry_gen's
    own register-field layout has never been independently characterized
    (only its position/length are established) -- attempting a guessed
    splice risks a false result from a misread field rather than a genuine
    hardware fact.
Finite namespace: unknown.
Maximum-valid and first-invalid tests: not performed.
Failure/overflow behavior: [ ] reject  [ ] zero/discard  [ ] alias/wrap  [ ] fault/device loss
Correct behavior when the compiler/driver needs more: unresolved; see
    Counterexamples for the recommended path.
Lifetime, destruction, and reuse semantics: n/a.
Counterexamples and untested cases: RECOMMENDED FOLLOW-UP (explicit, not
    silently dropped): a dedicated successor experiment should FIRST
    characterize carry_gen's operand-register field bit layout via
    structural byte-diff across several u64-add contexts with DIFFERENT
    GPR allocations (varying which registers hold the two addends), THEN
    attempt an independent-source splice once that field is understood
    well enough to avoid a silent-zero misread.
Driver/compiler consequence: until closed, treat carry_gen as ONLY safe to
    emit in the exact adjacent-to-its-producing-add pattern observed under
    INT-13; do not attempt to synthesize a standalone carry-generate.
```

### PACK-01

```text
Status: [x] Closed
Answer, where Yes/No: [x] Yes
Applies to: [ ] A18 Pro/G17P  [x] M4/G16G  [ ] both tested independently
Evidence: [x] independently assembled HW execution  [ ] HW splice
          [ ] API create/submit/exhaustion test       [ ] Linux end-to-end UAPI test
          [ ] captured userspace/command memory      [ ] encode/decode round trip
          [x] own-MSL byte diff only                 [ ] corpus inference only
Test/artifact: case pack0102_pack_half2x16, 7 rows (incl. fp16 max/min-
    normal, overflow-to-inf), structural tokenization.
Exact observed semantics or field mapping: float2->half2->as_type<uint>
    compiles to TWO `cvt_f2h_dst` (native float->half convert) instructions,
    zero `ibfins`/mask-shift-combine instructions. Functionally exact
    (f16_encode_exact reference) for all 7 rows.
Finite namespace: n/a.
Maximum-valid and first-invalid tests: n/a.
Failure/overflow behavior: [ ] reject  [ ] zero/discard  [ ] alias/wrap  [ ] fault/device loss
Correct behavior when the compiler/driver needs more: n/a.
Lifetime, destruction, and reuse semantics: n/a.
Counterexamples and untested cases: 7 directed rows, not randomized/
    exhaustive over the float32 domain.
Driver/compiler consequence: pack_half_2x16 should be lowered to the
    native `cvt_f2h_dst` convert path, not a generic bitfield pack.
```

### PACK-02

```text
Status: [x] Closed
Answer, where Yes/No: [x] Yes
Applies to: [ ] A18 Pro/G17P  [x] M4/G16G  [ ] both tested independently
Evidence: [x] independently assembled HW execution  [ ] HW splice
          [ ] API create/submit/exhaustion test       [ ] Linux end-to-end UAPI test
          [ ] captured userspace/command memory      [ ] encode/decode round trip
          [x] own-MSL byte diff only                 [ ] corpus inference only
Test/artifact: case pack0102_unpack_half2x16, 10 rows incl. NaN/Inf lanes.
Exact observed semantics or field mapping: uint->as_type<half2>->float2
    compiles to TWO `falu2` (general float-ALU) instructions -- native, but
    via the general float-ALU's convert mode rather than a dedicated
    "unpack" mnemonic; zero ibfins/mask-shift-combine. Exact for all 10
    rows including NaN(0x7E00)/Inf(0x7C00) lanes.
Finite namespace: n/a.
Maximum-valid and first-invalid tests: n/a.
Failure/overflow behavior: [ ] reject  [ ] zero/discard  [ ] alias/wrap  [ ] fault/device loss
Correct behavior when the compiler/driver needs more: n/a.
Lifetime, destruction, and reuse semantics: n/a.
Counterexamples and untested cases: 10 directed rows.
Driver/compiler consequence: unpack_half_2x16 should be lowered via the
    general float-ALU convert-mode path (falu2-family), not a bitfield
    extract/generic unpack.
```

### PACK-03

```text
Status: [x] Closed
Answer, where Yes/No: [x] Yes
Applies to: [ ] A18 Pro/G17P  [x] M4/G16G  [ ] both tested independently
Evidence: [x] independently assembled HW execution  [ ] HW splice
          [ ] API create/submit/exhaustion test       [ ] Linux end-to-end UAPI test
          [ ] captured userspace/command memory      [ ] encode/decode round trip
          [x] own-MSL byte diff only                 [ ] corpus inference only
Test/artifact: case pack0304_pack_snorm2x16, 7 rows + structural comparison
    against pack0506_pack_unorm2x16_edge.
Exact observed semantics or field mapping: pack_float_to_snorm2x16 compiles
    to a SINGLE `pack_convert` instruction, the exact same mnemonic as
    pack_float_to_unorm2x16 (byte-length-identical bodies, 46B each).
Finite namespace: n/a.
Maximum-valid and first-invalid tests: n/a.
Failure/overflow behavior: [ ] reject  [ ] zero/discard  [ ] alias/wrap  [ ] fault/device loss
Correct behavior when the compiler/driver needs more: n/a.
Lifetime, destruction, and reuse semantics: n/a.
Counterexamples and untested cases: 7 directed rows.
Driver/compiler consequence: pack_snorm_2x16 confirmed as a member of the
    same native pack_convert family as pack_unorm_2x16.
```

### PACK-04

```text
Status: [x] Closed
Answer, where Yes/No: [x] Yes
Applies to: [ ] A18 Pro/G17P  [x] M4/G16G  [ ] both tested independently
Evidence: [x] independently assembled HW execution  [ ] HW splice
          [ ] API create/submit/exhaustion test       [ ] Linux end-to-end UAPI test
          [ ] captured userspace/command memory      [ ] encode/decode round trip
          [x] own-MSL byte diff only                 [ ] corpus inference only
Test/artifact: case pack0304_unpack_snorm2x16_exhaustive, ALL 65536 16-bit
    lane bit patterns, one dispatch.
Exact observed semantics or field mapping: 65536/65536 bit-exact against
    the exact-Fraction oracle; compiles to a single `unpack_convert`
    instruction, same mnemonic as unpack_unorm2x16_to_float.
Finite namespace: 16-bit lane value, 0-65535, EVERY value tested.
Maximum-valid and first-invalid tests: n/a -- no value produced an
    unexpected result.
Failure/overflow behavior: [ ] reject  [ ] zero/discard  [ ] alias/wrap  [ ] fault/device loss
Correct behavior when the compiler/driver needs more: n/a.
Lifetime, destruction, and reuse semantics: n/a.
Counterexamples and untested cases: none within the 16-bit lane domain
    (exhaustive); the OTHER lane's value was fixed equal to the tested
    lane's value in this construction (gid|(gid<<16)), so cross-lane
    interaction at every possible (lane0,lane1) PAIR was not exhaustively
    tested (would be 2^32 combinations) -- see PACK-09/10 for the targeted
    cross-lane-independence tests instead.
Driver/compiler consequence: unpack_snorm_2x16 can be trusted to match its
    single-op native semantics for every possible 16-bit input.
```

### PACK-05

```text
Status: [x] Closed
Answer, where Yes/No: [x] Yes
Applies to: [ ] A18 Pro/G17P  [x] M4/G16G  [ ] both tested independently
Evidence: [x] independently assembled HW execution  [ ] HW splice
          [ ] API create/submit/exhaustion test       [ ] Linux end-to-end UAPI test
          [ ] captured userspace/command memory      [ ] encode/decode round trip
          [ ] own-MSL byte diff only                 [ ] corpus inference only
Test/artifact: case pack0506_pack_unorm2x16_edge, 10 directed rows (negative,
    >1, both-lane NaN combinations, +-Inf, subnormal-magnitude, 3 exact
    ties built via exact Fraction arithmetic on the float32-snapped input).
Exact observed semantics or field mapping: 10/10 exact against
    round(clamp(x,0,1)*65535) with ties resolved to the EVEN neighbor
    (confirmed at the one true exact tie, N=32767 -> 32768); NaN clamps to
    0 in either lane; negative clamps to 0; >1 clamps to max (65535); +-Inf
    clamp the same as any out-of-range value.
Finite namespace: n/a (continuous input domain, directed boundary sample).
Maximum-valid and first-invalid tests: n/a.
Failure/overflow behavior: [ ] reject  [x] zero/discard  [ ] alias/wrap  [ ] fault/device loss
Correct behavior when the compiler/driver needs more: n/a.
Lifetime, destruction, and reuse semantics: n/a.
Counterexamples and untested cases: only 3 exact ties were constructible
    with confidence (verified via exact Fraction arithmetic, not float64
    approximation -- an earlier float64-based construction had 2 spurious
    mismatches from non-exact "ties", corrected before this capture, see
    PROGRESS.md); a wider tie sweep (e.g. all N where (N+0.5)/65535 rounds
    exactly given float32 precision) is a possible but not-yet-done
    follow-up for full confidence in the tie-breaking rule.
Driver/compiler consequence: pack_unorm_2x16 matches the standard
    round-to-nearest-even, clamp-first, NaN-to-0 contract; safe to advertise
    without a software correction layer.
```

### PACK-06

```text
Status: [x] Closed
Answer, where Yes/No: [x] Yes
Applies to: [ ] A18 Pro/G17P  [x] M4/G16G  [ ] both tested independently
Evidence: [x] independently assembled HW execution  [ ] HW splice
          [ ] API create/submit/exhaustion test       [ ] Linux end-to-end UAPI test
          [ ] captured userspace/command memory      [ ] encode/decode round trip
          [ ] own-MSL byte diff only                 [ ] corpus inference only
Test/artifact: case pack0506_unpack_unorm2x16_exhaustive, ALL 65536 16-bit
    lane bit patterns, one dispatch.
Exact observed semantics or field mapping: 65536/65536 bit-exact against
    u/65535.0 (rounded through binary32) for every possible 16-bit value.
Finite namespace: 16-bit lane value, 0-65535, EVERY value tested.
Maximum-valid and first-invalid tests: n/a -- exhaustive, no exceptions.
Failure/overflow behavior: [ ] reject  [ ] zero/discard  [ ] alias/wrap  [ ] fault/device loss
Correct behavior when the compiler/driver needs more: n/a.
Lifetime, destruction, and reuse semantics: n/a.
Counterexamples and untested cases: same lane-pairing caveat as PACK-04.
Driver/compiler consequence: unpack_unorm_2x16 can be trusted bit-for-bit
    for every possible 16-bit input.
```

### PACK-07

```text
Status: [x] Closed
Answer, where Yes/No: [x] Yes (normalized); [x] No (generic, non-normalized)
Applies to: [ ] A18 Pro/G17P  [x] M4/G16G  [ ] both tested independently
Evidence: [x] independently assembled HW execution  [ ] HW splice
          [ ] API create/submit/exhaustion test       [ ] Linux end-to-end UAPI test
          [ ] captured userspace/command memory      [ ] encode/decode round trip
          [x] own-MSL byte diff only                 [ ] corpus inference only
Test/artifact: cases pack0708_pack_unorm4x8, pack0708_pack_snorm4x8 (5 rows
    each), pack07_pack4x8_manual_generic (3 rows), all with structural
    tokenization.
Exact observed semantics or field mapping: pack_float_to_{unorm,snorm}4x8
    (both confirmed to COMPILE, not previously exercised in this repo)
    compile to a TWO-instruction sequence (`pack_convert` then
    `frag_color_pack`), functionally exact for both. The hand-written
    GENERIC (non-normalized) 4x8 integer gather idiom is NOT native --
    15 instructions, ibfins-based, the same shape as plain insert_bits
    lowering.
Finite namespace: n/a.
Maximum-valid and first-invalid tests: n/a.
Failure/overflow behavior: [ ] reject  [ ] zero/discard  [ ] alias/wrap  [ ] fault/device loss
Correct behavior when the compiler/driver needs more: for NORMALIZED
    (unorm/snorm) 4x8 packing, target the native pack_convert+
    frag_color_pack pair; for a GENERIC integer 4x8 gather, no native
    single-op path exists -- continue lowering via mask/shift/insert.
Lifetime, destruction, and reuse semantics: n/a.
Counterexamples and untested cases: the `frag_color_pack` mnemonic
    appearing in a plain COMPUTE kernel (no fragment stage) is flagged as
    worth independent review of tools/agx-isa's db.json provenance for
    this byte pattern -- reported as observed, not asserted as either "this
    op is genuinely shared" or "the DB name is wrong."
Driver/compiler consequence: `.has_pack_32_4x8` should be split in the
    driver's capability model: TRUE for normalized-format 4x8 packing,
    FALSE for a generic (non-normalized) integer 4x8 pack.
```

### PACK-08

```text
Status: [x] Closed
Answer, where Yes/No: [x] Yes
Applies to: [ ] A18 Pro/G17P  [x] M4/G16G  [ ] both tested independently
Evidence: [x] independently assembled HW execution  [ ] HW splice
          [ ] API create/submit/exhaustion test       [ ] Linux end-to-end UAPI test
          [ ] captured userspace/command memory      [ ] encode/decode round trip
          [x] own-MSL byte diff only                 [ ] corpus inference only
Test/artifact: cases pack0708_unpack_unorm4x8, pack0708_unpack_snorm4x8,
    8 rows each.
Exact observed semantics or field mapping: unpack_{unorm,snorm}4x8_to_float
    (both confirmed to COMPILE) both compile to TWO `unpack_convert`
    instructions (same mnemonic family as the 2x16 case), functionally
    exact for both (8/8 rows each, incl. round-tripped pack outputs and
    raw boundary words).
Finite namespace: n/a.
Maximum-valid and first-invalid tests: n/a.
Failure/overflow behavior: [ ] reject  [ ] zero/discard  [ ] alias/wrap  [ ] fault/device loss
Correct behavior when the compiler/driver needs more: n/a.
Lifetime, destruction, and reuse semantics: n/a.
Counterexamples and untested cases: 8 directed rows each, not exhaustive
    over the 32-bit packed-word domain (unlike PACK-04/06's exhaustive
    16-bit-lane approach, exhaustion here would be 2^32 -- not attempted).
Driver/compiler consequence: `.has_pack_32_4x8`-adjacent UNORM/SNORM 4x8
    UNPACK can be advertised as native, targeting unpack_convert directly.
```

### PACK-09

```text
Status: [x] Closed
Answer, where Yes/No: [x] Yes
Applies to: [ ] A18 Pro/G17P  [x] M4/G16G  [ ] both tested independently
Evidence: [x] independently assembled HW execution  [ ] HW splice
          [ ] API create/submit/exhaustion test       [ ] Linux end-to-end UAPI test
          [ ] captured userspace/command memory      [ ] encode/decode round trip
          [ ] own-MSL byte diff only                 [ ] corpus inference only
Test/artifact: cases pack0910_half2_{add,mul,fma}, 8 rows each, per-lane
    exceptional-value pairs (NaN, +-0, +-Inf, subnormal crossed against an
    ordinary value in the other lane).
Exact observed semantics or field mapping: all 24 rows (8x3 ops) exact
    against a from-scratch, exactly-rounded binary16 reference
    (oracle.f16_op, genuinely fused for fma3); the "ordinary" lane's result
    was correct in every row regardless of the other lane's exceptional
    value.
Finite namespace: n/a.
Maximum-valid and first-invalid tests: n/a.
Failure/overflow behavior: [ ] reject  [ ] zero/discard  [ ] alias/wrap  [ ] fault/device loss
Correct behavior when the compiler/driver needs more: n/a.
Lifetime, destruction, and reuse semantics: n/a.
Counterexamples and untested cases: 8 directed rows per op; not exhaustive
    over the fp16 x fp16 exceptional-value cross-product (11 fp16
    categories x 11 x 11 for fma would be a large but finite follow-up).
Driver/compiler consequence: .vectorize_vec2_16bit's correctness side is
    confirmed for add/mul/fma with independent, lane-correct exceptional
    handling.
```

### PACK-10

```text
Status: [x] Closed
Answer, where Yes/No: [x] Yes
Applies to: [ ] A18 Pro/G17P  [x] M4/G16G  [ ] both tested independently
Evidence: [x] independently assembled HW execution  [ ] HW splice
          [ ] API create/submit/exhaustion test       [ ] Linux end-to-end UAPI test
          [ ] captured userspace/command memory      [ ] encode/decode round trip
          [ ] own-MSL byte diff only                 [ ] corpus inference only
Test/artifact: same three cases as PACK-09 -- the matrix was designed to
    answer both items from one dataset.
Exact observed semantics or field mapping: confirmed independent per-lane
    results across NaN, +-0, subnormal, and +-Inf in 24/24 rows: no
    cross-lane corruption observed for any exceptional-value class.
Finite namespace: n/a.
Maximum-valid and first-invalid tests: n/a.
Failure/overflow behavior: [ ] reject  [ ] zero/discard  [ ] alias/wrap  [ ] fault/device loss
Correct behavior when the compiler/driver needs more: n/a.
Lifetime, destruction, and reuse semantics: n/a.
Counterexamples and untested cases: same as PACK-09.
Driver/compiler consequence: same as PACK-09.
```

### PACK-11

```text
Status: [x] Closed
Answer, where Yes/No: [x] Yes
Applies to: [ ] A18 Pro/G17P  [x] M4/G16G  [ ] both tested independently
Evidence: [x] independently assembled HW execution  [ ] HW splice
          [ ] API create/submit/exhaustion test       [ ] Linux end-to-end UAPI test
          [ ] captured userspace/command memory      [ ] encode/decode round trip
          [x] own-MSL byte diff only                 [ ] corpus inference only
Test/artifact: cases pack11_short2_{add,mul,and}, 5 rows each, structural
    tokenization of all three.
Exact observed semantics or field mapping: `add` -> two independent iadd2;
    `mul` -> two independent imad (with implicit zero addend); `and` -> a
    DIFFERENT, non-packed shape (two mov_zext16 + mov_imm + pad_operand
    tokens, no ilogic instance). None of the three forms reaches a
    packed-2-lane integer ALU op (the kind confirmed to exist for half2 in
    PACK-09/10).
Finite namespace: n/a.
Maximum-valid and first-invalid tests: n/a.
Failure/overflow behavior: [ ] reject  [ ] zero/discard  [ ] alias/wrap  [ ] fault/device loss
Correct behavior when the compiler/driver needs more: n/a (this is a
    negative-capability finding: no packed short2 ALU exists to target).
Lifetime, destruction, and reuse semantics: n/a.
Counterexamples and untested cases: `and`'s exact decomposition (why
    mov_zext16 rather than two ilogic instances, unlike the 32-bit logic
    functions in INT-12) is observed but not explained -- flagged as an
    open follow-up, not asserted to be understood.
Driver/compiler consequence: confirms the FP16 vectorizer (.vectorize_
    vec2_16bit) must never generalize to 2x16 integer operations -- add,
    multiply, AND all decompose to independent scalar/32-bit lowerings.
```

---

## Clean-room provenance audit

```text
Clean-room provenance: OWN-SHADER + HW-PROBE (+ PUBLIC for NIR/GLSL/Metal-Shading-
    Language-Specification/IEEE754 op DEFINITIONS used only in the host oracle,
    never as an Apple9 encoding source)
Inputs inspected: kernels/*.metal (51 functions, all authored here), the compiled
    _agc.main bytes those kernels produce (via tools/shdump, unmodified -- READ-
    ONLY), tools/agx-isa/isadb.py's disassemble() applied to those same bytes
    (READ-ONLY, not modified)
Apple binary introspection: NONE
Reproduction: python3 -B verify.py --selftest && python3 -B verify.py --seqtest
    && python3 -B run.py --run-id <new-id> --repo ../.. (harness/build.sh
    compiles tools/shdump + tools/agxtest/agxrun fresh each run); analysis:
    python3 -B analysis/structural.py --run raw/<run-id> --repo ../..
Evidence: raw/m4-20260828T063920Z-run01/, raw/m4-20260828T063935Z-run02/
    (byte-identical per verify.py --captured --compare), analysis/structural_report.json,
    authored_hashes.json (30 authored files), CAPTURE_CONTRACT.json,
    PRE_REGISTRATION.md, PROGRESS.md (full pilot + capture + two disclosed-and-
    fixed process issues)
```

---

## Deferred / Partial items summary (not silently dropped)

| item | status | why | recommended follow-up |
|---|---|---|---|
| INT-02/INT-11 (compiler-contract vs raw-instruction) | Closed at the compiler-contract tier | this experiment characterizes what METAL'S COMPILER emits for extract_bits/insert_bits with runtime operands (ibfe/ibfins + several helper instructions); it does not isolate whether the cnt==32 bypass is intrinsic to a bare `ibfe`/`ibfins` or added by the surrounding compiler-generated code | independently assemble a bare `ibfe`/`ibfins` (no helper instructions) with an explicit width=32 field and splice-execute it |
| INT-08 | Partial/Unknown | register-pressure probe design did not force allocation past r0-26 | a probe forcing a genuinely serialized (non-tree) IMAD dependency chain, or an independently-assembled high-register IMAD splice |
| INT-09 | Closed, but DERIVED not directly isolated | find-MSB's own standalone output was never read back; only its role inside the clz decomposition was re-confirmed structurally | splice out clz's subtract/clamp trailer to read the raw find-MSB result directly |
| INT-12 | Closed for 10/16 functions via `ilogic`; the other 6 (2 projections, 2 negations, 2 constants) route elsewhere and were not tested against `ilogic`'s raw field directly | compiler never emits those 6 through `ilogic` | independently assemble an `ilogic` instance with lut_a/lut_b values the compiler never emits (e.g. predicted NAND/XNOR complements) and splice-execute to test the field's full width |
| INT-14 | Partial/Unknown, deferred by design | operand-field layout of `carry_gen` not characterized; splicing without that risks a silent-zero misread (per the project's standing hardware-behavior warning) | characterize the operand-register field first (structural byte-diff across varied-register u64-add contexts), then attempt an independent-source splice |
| PACK-07 | Closed but with an open naming question | `frag_color_pack` mnemonic appearing in a compute-only kernel is reported as observed, not resolved | review tools/agx-isa/db.json provenance for this byte pattern's naming |
| PACK-11 (`and` sub-case) | Closed for the core negative claim, but the exact `and` decomposition (mov_zext16-based, unlike add/mul) is unexplained | not investigated further within this experiment's time budget | isolate why MSL's short2 `&` routes through zero-extension moves rather than `ilogic`/packed ops |

No item was silently dropped: every one of the 14 `INT-*` and 11 `PACK-*` items has a response
block above, and every partial/deferred item is named both here and in `PRE_REGISTRATION.md` §1.
