# M5 (Apple10 / G17g) Shader ISA

The M5 GPU (`MTLGPUFamilyApple10`, arch `applegpu_g17g`, SoC T8142) runs a **G17-family sibling** of
the A18 Pro (G17P/Apple9) ISA documented in `README.md` + `encoding-tables.md` (this dir). Empirically
(EXP-M5-02/03) **~84% of M5 instruction bytes decode with the unmodified A18 DB**, and after fixing the
G17P→G17g deltas the M5 DB reaches **96.6% (own) / 98.0% (third-party) byte coverage with round-trip
identity** (EXP-M5-05). So the M5 ISA is documented as **"the A18 ISA (see `README.md`/`encoding-tables.md`)
plus the deltas below"**, not re-specified from scratch.

## Machine-readable DB
`../../tools/agx-isa-m5/` — the M5 (dis)assembler DB (`isadb.py` + generated `db.json`), forked from the
A18 `tools/agx-isa/`. `db.json` is the exhaustive, machine-readable per-instruction encoding table
(match bits + typed bit-fields + lengths + semantics + provenance). Use `agxisa.py tokenize/disasm/asm`.

## G17P → G17g ISA deltas (the M5-specific part)
Source: EXP-M5-02 (census) + EXP-M5-05 (fork). The divergence is concentrated in a small set of
**length-rule** changes plus a few new/relocated leaders, in the low-nibble byte0 families `_6 _e _0 _f _7`
(high nibble = dst register):
- **`n3_mov` and other multi-word ops** — length rules changed on G17g (the top delta lever; the A18
  length under/over-counted on M5). Fixed in the fork's `instr_length`.
- **The `0xNe` byte0 column** (`0x3e/0x5e/0x7e/0x9e/0xbe/0xde/0xfe/0xae`) — a generational format change;
  re-lengthed/added on G17g.
- **`0xb7`** — a leader the A18 DB never resolves; new/relocated on G17g.
- **Memory access is SPLIT on M5** (HW-splice-validated, EXP-M5-07): A18's monolithic 14-byte
  `device_load`(0x67)/`device_store`(0xe7) becomes **three ops** — an ADDRESS-GEN op (`?f <slot<<2> 03
  <idxmode>`, 4B), a LOAD (`0x18/0x38/0x58/0x78` = 1/2/3/4-component, 10B/4B), and a STORE (`0x01/0x21/0x41/
  0x61` = 1/2/3/4-component, 4B/6B). base-slot / index-mode / element-size / store-format fields are all
  splice-proven; LOAD-vs-STORE is distinct opcodes, not a direction bit. (This corrected the census guesses:
  the "0x41 store" was a load *tail*, "0x78 typed" was vec4 *load*.) See EXP-M5-07 for the field maps.
- **Matrix / neural (HW-validated, EXP-M5-09 — marquee):** the matrix path **SPLITS** on M5. Unlike A18
  (everything → `0xcf`), `simdgroup_matrix` MAC emits **zero `0xcf`** — it lowers to a low-nibble-`0xf` **tile
  load/store family** (`?f ..07..`) plus a **`2f 00 05` MAC** op; only the MPP `tensor_ops::matmul2d` path
  keeps `0xcf`. **There is NO new dedicated "neural" ISA leader** — the Apple10 Neural Accelerator rides the
  existing matrix family, not a new opcode. (Op identity splice-proven; full 8×8 operand packing is splice-TODO.)
- **Ray tracing (EXP-M5-09):** `rt_intersect` (byte0 low-nibble `0x4` + byte+1 `0xea`) **transfers unchanged
  from A18** (traverse + result-read, 2×/kernel; inline query too). `rt_as_load`/`ray_mem` no longer distinct
  leaders — migrated into the M5 memory family; **exact AS-load encoding OPEN**.
- **Atomics + subgroup/quad (EXP-M5-09):** UNIFIED reduction selector `2f 00 <scope> 0a 27 80 <OP> 02 <mode>`
  — byte+6 OP (`a0`and/`a1`or/`a2`xor/`a3`add/`a6`min/`a7`max/`ac`float-add), byte+2 scope, byte+9 reduce/scan;
  shuffle = `2f 00 21`. **Texture (EXP-M5-09):** sample family = byte0 low-nibble `0xf` + byte+2 (`0x12`
  sample-class / `0x1a` read). (These are documented; their DB descriptors are the next integration wave —
  they need length disambiguation in the overloaded `0x2f`/`0x0f` space.)
- **INTEGRATED into `db.json` (EXP-M5-11, HW-validated):** the M5 op-selector families are now emittable
  descriptors — **`m5_reduce`** (10B, subgroup/quad reduce+scan + device-atomic-on-uniform; op byte+6
  a0/a1/a2/a3/a6/a7/ac, scope byte+2, mode byte+9), **`m5_shuffle`** (10B, `2f 00 21`), **`m5_alu`** (12B,
  general compute ALU byte0=0x27, op byte+6 hi-nibble 0xa), **`m5_iadd`** (12B, split-memory index add). The
  split-memory field maps are resolved: **m5_load byte+5 = index register** (splice-proven), the `a[i+k]`
  immediate offset is **folded into a preceding `m5_alu` add** (no offset field — a negative vs A18), and the
  store/load **data register is implicit/positional**. `0x67`/`0xe7` (A18 device_load/store) **still occur on
  M5** alongside the split model; A18 atomics migrated to `m5_reduce`.
- **TEXTURE — EMITTABLE (EXP-M5-17, pixel-splice HW-validated):** `m5_tex` (0x12 compute-sample / 0x16 FRAGMENT
  sample; byte+1 op 04/05/06/07 = explicit-LOD/bias|compare/implicit|gather/register-LOD) + `m5_tex_read` (0x1a) +
  `m5_store_texresult`. **Operand byte map, each proven by an observed pixel delta:** coordinate register = **byte+3**
  (reg32<<1), texture slot = **byte+6** (slot0=0x60, +0x08/slot), sampler slot = **byte+5[6:0]**, LOD/bias immediate
  = **byte+12** (round(level·64)); result reg = byte0 hi-nibble; per-variant length sample 22B / gather 14B / read
  8B. A driver can now emit a working sample/read. Still raw (rule 5): descriptor-bank nibble (byte+4) for dense
  slot≥2, coordinate scoreboard (byte+7, proven inert), gradient/pad words. `tex_write` (`0xd7`) image-store also fully specified.
  **Divergent-address atomics** — `m5_atomic_div` (12B) / `m5_atomic_xchg` (10B), `0f 00 03 … c0` form,
  splice-confirmed (the A18 per-lane `0x67` path is gone). **`simdgroup_matrix` MAC** — `m5_matrix_mac`
  (`2f 00 05`, 14B leader/accumulate) + `m5_tile_ldst`; 8×8 operand packing raw (extension-gated).
  Retained A18 descriptors the M5 *supersedes* (do-not-emit for M5): `tex_sample`(0x5), `matrix_mac`(0xcf for
  simdgroup), `atomic_rmw`/`atomic_mem`(0x67 divergent form), `call`/`call_indirect`, `rt_as_load`(0xdf),
  `rt_ray_mem`(0x5f) — each carries a "superseded-on-M5" note in its `semantics`. (NOTE: `tex_write`0xd7 and the
  `0x67`/`0xe7` uniform/monolithic forms are RETAINED-and-valid on M5, not superseded.)
- **Still open (documented, extension-gateable, with fallbacks in `porting-guide-m5.md` §8):** texture
  descriptor-bank nibble (byte+4) for dense binding slots ≥2 (slots 0–1 fully mapped); the M5 `24 80 03`
  image-store length; matrix `simdgroup_matrix` 8×8 operand packing + tile 12-vs-16 length determinant (raw);
  atomic op-selector not per-bit exhaustively spliced; **call ABI `0xef/0xff`** (needs pipeline-`linkedFunctions`
  extraction — standalone archive yields a link-time stub); **RT AS-load** (migrated off `0xdf` — needs an
  AS-bound splice testbed). Intra-shader control flow is green; a driver can gate function-pointers /
  coop-matrix-operands / RT-traversal until these are mapped. (Texture sample/read coord+slot+LOD are RESOLVED,
  EXP-M5-17.)

## Machine model — registers / uniforms / spill (RE-MEASURED on M5, EXP-M5-21)
The A18 machine model (`README.md` §"Machine model — registers, uniforms, Dynamic Caching") transfers
to M5 **except the register-file size**, which is larger. Re-measured on G17g (own-shader compile→read
own `__GPU_METADATA`, + HW copy-correctness + iotrace occupancy correlation; 0 faults, 0 reboots):

- **GPR file is LARGER than A18 — footprint caps at 126, not 96 (the marquee delta, +30 GPRs).** The
  compiler's register footprint (metadata **field 0**, 32-bit-register units) grows with the *identical*
  A18 slope (`f0 ≈ round(1.25·K)+3`; K=8→13, K=16→23, K=48→63 all byte-identical to A18) but **caps at
  exactly 126** (K=98…256 all report 126). Fine ladder: K=96→**123** (zero scratch), K=98→**126** (scratch
  appears). **HW-proven:** a kernel declaring **123 live 32-bit regs with zero scratch computes correctly**
  (n=1 copy, exact readback), and all spilled kernels (f0=126) also compute correctly. ⇒ **a compiler must
  target 126 GPRs before spill on M5** (vs 96 on A18). *(Physical file 126-vs-128 not yet disambiguated: the
  A18 r96 memory-index hard-fault probe does NOT transfer — M5 memory is split, and splicing the `m5_load`
  index-reg byte+5 across 0x00–0xff faults nothing / is inert because the index is carried by `m5_addr_gen`.
  Most-likely-126 by analogy to A18, cap=physical, same −3 no-spill gap 123/126 vs 93/96. Follow-up: map the
  `m5_addr_gen` index field.)*
- **16-bit halves packed 2 per GPR — CONFIRMED, identical to A18.** Half footprint slope 0.75 (64 halves →
  **50** GPRs; impossible if a half owned a 32-bit reg). Halves spill at the same 126-GPR ceiling.
- **Uniform register file — CONFIRMED, identical to A18.** Metadata **field 31** = uniform footprint, ~8 B
  per bound scalar uniform (2→32, 8→80, 16→144 B); fed by the `constant_program` uniform datapath. Exact
  uniform-register *count* still unpinned (8-bit index ⇒ ≤128; pushing past ~30 uniforms hits Metal's
  31-buffer binding limit, not a HW cap).
- **Spill / Dynamic Caching — same mechanism, higher onset.** Above 126 GPRs the compiler spills to
  per-thread **scratch (stack)**; byte size in metadata field **14/41**, appearing exactly at f0=126 (K=98)
  and growing with pressure (96→400→1184 B). Spilled kernels compute correctly.
- **Occupancy tier bit — MEASURED threshold f0≈20 (A18 was ≈12).** Launch compute-config word `+0x00`
  (BO `0x100000b0000`) bit **23** is the 2-level occupancy tier (EXP-M5-13 `--heavy` flip). f0↔bit23
  correlation: **clear for f0 ≤ 19, set for f0 ≥ 20** (directly observed 19│20 adjacent transition; tracks
  f0, not workload). M5 base `+0x00` = `0x00000000` (**bit19 dropped** vs A18's `0x00080000`); heavy =
  `0x00800000`. The higher tier threshold is consistent with the larger register file.

**For a driver (M5):** allocate ≤ **126** 32-bit GPRs before spilling to scratch; 2 independent halves per
GPR; uniforms/base-pointers in the separate uniform file (source picks GPR-vs-uniform via a mode bit, as
A18); scratch/GPR/uniform footprints declared in the shader's own `__GPU_METADATA` (fields 14/41, 0, 31);
set config `+0x00` bit23 once the footprint reaches ~20 GPRs. Evidence: `experiments/EXP-M5-21-gpr-machine-model/`.

## Status & provenance
- **Tokenization + op families:** DB = **189 descriptors**; byte coverage **97.4% (own) / 98.4% (tp)**, named
  **93.4% / 95.5%**, round-trip green, 0 hangs (EXP-M5-05 + EXP-M5-11).
- Everything is HW-grounded: own-shader compile→extract→disassemble, validated against 842 own + 3095
  third-party real programs, and (for changed encodings) splice-and-observe on the live M5.
- Residual undecoded tail: own 2.60% / tp 1.61%. Remaining named-but-raw fields (operand packing of the
  unified-op families) are marked raw per clean-room rule 5 rather than guessed.
