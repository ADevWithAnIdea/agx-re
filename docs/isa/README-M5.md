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
- **Ray tracing (EXP-M5-09 + EXP-M5-19 RESOLVED):** `rt_intersect` (byte0 low-nibble `0x4` + byte+1 `0xea`)
  **transfers from A18 and is now splice-confirmed on M5** (byte+1 ea=traverse, byte+2 mode, byte+4 ray/AS
  operand). The A18 dedicated `rt_as_load`(0xdf)/`rt_ray_mem`(0x5f) leaders are **gone** on M5 — RT loads
  migrated into the `0x?f` split-memory family: the **AS handle** is an index-fixed argument/uniform load
  (`?f 48 …`, byte+1=0x48; buffer-binding-index-independent — `as_slot1==as_slot3`), and **ray origin/dir**
  ride `0x?f` split-memory loads (byte+2 ∈ {0x43,0x83}). So a driver emits RT via the general argument-load +
  split-memory forms — **no dedicated RT-load opcode on M5**. (AS-aware splice testbed built; open: exact
  0x83-load sub-field widths, op#2 result-field layout.)
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
  8B. A driver can now emit a working sample/read. **Binding-slot selection (EXP-M5-22, pixel-proven):** for a
  Tier-2 argument buffer the sample op is **slot-agnostic** — `tex[k].sample()` compiles byte-identical for k=0..7;
  the slot is chosen by a **preamble descriptor-address immediate `0xa0+index`** (idx0→red…idx3→yellow observed).
  For direct bindings, byte+6 `tex_slot` = `0x60+0x08·slot` (dense-direct byte+4 = compiler-allocated descriptor
  regs, raw). `m5_tex`/`m5_tex_read` leader typed 6→8B so the assembler can set `tex_slot`/`samp_slot`/`coord_ctl`
  (LOD byte+12 kept in prose — typing needs len≥13 which over-reads the 8B image-read). Coordinate scoreboard
  (byte+7) proven inert. **Image store (EXP-M5-22):** the M5 compute image store is an **18-byte `m5_image_store`**
  (`<fmt>5 … 24 <desc> a0 02 …`; texture = compiler-allocated descriptor, supersedes A18 `0xd7` on the compute
  path); `tex_write`(`0xd7`) still fully specified for the graphics path. **Correction:** `24 80 03` is a 10-byte
  constant-materialisation move (`m5_const_move`), **NOT** an image store (the EXP-M5-16 attribution was wrong).
  **Divergent-address atomics** — `m5_atomic_div` (12B) / `m5_atomic_xchg` (10B), `0f 00 03 … c0` form,
  splice-confirmed (the A18 per-lane `0x67` path is gone). **`simdgroup_matrix` MAC** — `m5_matrix_mac`
  (`2f 00 05`, 14B) + `m5_tile_ldst` — **operands EMITTABLE (EXP-M5-20):** tile register = byte0 hi-nibble,
  memory-address GPR = tile-ldst byte+1 (proven by numeric matrix deltas); MAC A&B regs byte+3, **C reg
  byte+13[4:3]**, accumulate byte+9, datapath byte+6, input-dtype byte+1; tile length = `16 if (byte+10 & 0x40)
  else 12`. Latent capability: MAC byte+13 bit6 = **negate the A·B product** (Metal doesn't expose this — see
  `hypotheses.md`). A/B sub-bit packing inside byte+3 stays raw (rule 5) but a driver can place A/B/C via the tile convention.
  Retained A18 descriptors the M5 *supersedes* (do-not-emit for M5): `tex_sample`(0x5), `matrix_mac`(0xcf for
  simdgroup), `atomic_rmw`/`atomic_mem`(0x67 divergent form), `call`/`call_indirect`, `rt_as_load`(0xdf),
  `rt_ray_mem`(0x5f) — each carries a "superseded-on-M5" note in its `semantics`. (NOTE: `tex_write`0xd7 and the
  `0x67`/`0xe7` uniform/monolithic forms are RETAINED-and-valid on M5, not superseded.)
- **Still open (documented, extension-gateable, with fallbacks in `porting-guide-m5.md` §8):** dense-direct
  texture byte+4 descriptor-register allocation (arg-buffer slotting IS resolved — preamble `0xa0+index`); atomic
  op-selector not per-bit exhaustively spliced; the exact A/B sub-bit split inside matrix-MAC byte+3 (byte proven,
  canonical value works); image-store data/descriptor packing (18B length + slot-is-descriptor resolved);
  intra-tile Morton within-tile permutation (inherited from A18 — the raw twiddled backing is not CPU-observable
  on M5, EXP-M5-23; allocation model byte-confirmed). **RESOLVED this wave:** texture sample/read coord+slot+LOD (EXP-M5-17); RT AS-load
  / ray-data (EXP-M5-19 — general argument + split-memory forms, no dedicated op); GPR machine model 126 GPRs
  (EXP-M5-21); function-call ABI (EXP-M5-18); cooperative-matrix operands + tile length (EXP-M5-20); **texture
  binding-slot selection + typed fields + 18B image-store (EXP-M5-22)**.
- **CALL ABI — MAPPABLE (EXP-M5-18, linked-pipeline extraction + splice):** out-of-line direct + indirect calls
  round-trip exactly. Sequence: `43 00 00 01` frame_marker (inherited, runtime-inert) → `9e 60 <type> 0e` call-setup
  (byte+2 = 0x00 direct / 0x01 indirect; direct embeds target PC in a `fe 1f…` tail, indirect loads the target
  code-VA from the `MTLVisibleFunctionTable` via a preceding `m5_load`) → **`ff c7 ff 7f be 03 40 0e`
  branch-and-link (`m5_call`, 8B)** [+ `m5_call_tail` `fb 1e 1f 00` 4B on indirect]; callee ret = `27 00 04 00 20
  00 a5 02` (`a5` = ret marker). Args by-register (no per-call-site marshalling); return in a fixed reg. The A18
  `0f 05…8f`/`0f 80`/`0x8f` forms all changed on M5; only the `43` marker + intra-shader control flow carried over.
  NEGATIVES: Metal **inlines** most vft calls (needs ≥8 fns behind a runtime index, or `[[noinline]]`); the census
  `ef/ff 48 43` is **RT traversal, NOT a call**. Open: intra-setup bit-typing of `9e 60`, direct target-PC tail
  encoding, spill frame. New reusable tooling: `experiments/EXP-M5-18-call-abi/{shdumplink,agxrunlink}.m`.

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
