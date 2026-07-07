# EXP-0036 RESULTS — ISA consolidation + encoding tables + byte0-group census

## Part A — descriptor merge (host)

Merged the 5 staged descriptor files into `tools/agx-isa/isadb.py` and regenerated `db.json`.

- **Descriptor count: 50 → 61** (+11 net). Added: `mov_imm`, `half_alu`, `ibitcount`, `irotate`,
  `pack_convert`, `unpack_convert`, `iminmax_chain`, `frame_marker`, `call`, `ret`, `call_indirect`.
  **Replaced** in place: `get_sr` (EXP-0031 — SR# is **byte1**, byte0-hi = dst GPR; old descriptor had
  the SR-select in byte0-hi) and `tex_sample` (EXP-0034 — added compare/gather-component/offset/LOD-query
  fields + the full op+2 variant enum).
- **6 EXP-0033 length-rule corrections applied** in `instr_length()`: `0xa7 b1∈{04,05}`→8 (reverse_bits/
  find-MSB), `0x27 b1==0x01`→12 (rotate-by-immediate), `0x27 b1==0x05`→8 (popcount, already), `0x10`→6/8
  (native-half ALU), `0x2b/3b/5b/8b`→10 (shift-prep, gated on byte+2 low-nibble e/f), `0x22`→6/10 (min/max
  chain vs shift helper).
- **Cross-experiment corrections applied:**
  - **`0x43` re-scoped** from EXP-0030's mesh-only `obj_mesh_ctrl` to the **generic call/frame-setup
    marker** `frame_marker` — it precedes every out-of-line CALL in plain compute kernels too (confirmed:
    `k_cf_call` shows `43 00 00 01` before each `0f 05` call).
  - **`0x97`/`0x17` collisions gated:** `pack_convert`/`unpack_convert` (byte+2==0x56) vs the fragment
    `frag_color_pack` (0x97, byte+2==0x54) and `simd_ballot` (0x17, gated on **byte+1==0x07**). Verified
    against real compiled bytes: `k_cvt_pack` pack = `97 04 56 …`, `k_subgroup_ballot` = `17 07 56 …`.
  - **get_sr/mov_imm disambiguation** (both byte0 low-nibble 0xC): get_sr carries a 32-bit-source suffix
    (**byte+3 low-nibble == 6**, e.g. `.. 10 06` / `.. 14 66`); the bare 2-byte `mov_imm` does not. This
    also decodes the 0xN4 datapath forms (`24 a8 10 06`) that were previously unlengthed.
  - **`call_indirect` = 6 bytes** (not the 8 EXP-0035 structurally estimated) — confirmed by `k_fptr`
    alignment (`0f 80 85 02 07 02` immediately precedes the result store); `call` gated on **byte+4==0x8f**
    (the 0x8f link register) since byte+6 is 0x54/0x56 depending on the cache/last-use bit.
  - **New EXP-0036 length finding:** the **compact call-argument move** (byte0 low-nibble 0xb, **byte+2
    high-nibble 2**, e.g. `ab 82 21 c0`) is **4 bytes** — the r10/r11 argument marshalling around a CALL;
    adding this makes the whole call ABI (`k_cf_call`) tokenize with zero leftover.

- **Round-trip: PASS.** `roundtrip_test.py` extended with 15 new real single-op vectors (one per merged
  descriptor, harvested from the corpus / the source experiments) and 2 new whole-program tokenizations
  (`merged_alu`, `merged_call`). All four test sections (real asm↔disasm, synth field round-trip, whole-
  program tokenization to 0 leftover, packed-immediate codec) report **ALL PASS**.

## Part B — self-contained encoding tables (host)

- **`docs/isa/encoding-tables.md` written** by `tools/agx-isa/gen_encoding_tables.py` (rendered from
  `db.json`): **all 61 instruction descriptors tabulated**, grouped into 14 families (Float ALU, Integer
  ALU, Conversions/pack, Bitwise, Move/SR, Memory, Atomics, Texture, Control-flow/function-ABI,
  SIMD/quad, Matrix, Ray tracing, Barrier/ordering, Fragment). Each descriptor lists its byte0 group +
  length, the match/opcode bits, and every field (name, bit-range, type, enum values), plus the byte-0
  length-rule appendix. Generated-but-committed; a one-line pointer was appended to `docs/isa/README.md`.

## Part C — byte0-group census (device)

Corpus: **61 extracted stage `_agc.main` programs** (57 unique after dedup of identical vertex stages),
10,110 instruction bytes, spanning every required category. Tokenized with the merged DB via an
align-forward resync tokenizer (`census.py`); full output in `raw/census.txt`.

**Headline (objective ISA-completeness metric):**

| metric | value |
|---|---|
| instructions walked (unique) | 1286 |
| **named** (matched a descriptor) | 926 (**72.0%**) |
| length-only (clean length, no descriptor) | 99 (7.7%) |
| **cleanly tokenized (length known)** | 1025 / 1286 = **79.7%** of tokens |
| **byte coverage** | 8268 / 10110 = **81.8%** of instruction bytes |
| distinct byte0 groups seen | ~55 real leaders (+ resync-noise) |

**Byte coverage by stage category** — the core ISA is near-complete; gaps concentrate in the
vertex/mesh emit path and texture address arithmetic:

| category | coverage |
|---|---|
| render:fragment | **94.9%** |
| compute:function-table | 90.1% |
| compute:core (ALU/mem/atomics/subgroup/quad/matrix/CF) | 86.9% |
| render:vertex | 69.7% |
| compute:texture | 68.6% |
| mesh | 62.0% |

Top named mnemonics: `iadd2`(104), `get_sr`(89), `device_load`(81), `falu3`(65), `iminmax`(59),
`stop`(57), `fspecial`(41), `device_store`(38), `falu2`(36), `iter`(27) — i.e. the merged DB names the
bulk of what the compiler actually emits.

### Remaining undecoded byte0 groups — the last ISA gaps

The census cannot decode these leaders (counts are undecoded-region occurrences; each has a hex sample in
`raw/census.txt`). They match the expected frontier:

- **Vertex/mesh varying-emit stores — `0x57` / `0x05` / `0x06`** (+ their coefficient-setup companions).
  `set_vertex`/varying stores lower to a `0x57`-family store the DB does not yet model; these dominate the
  vertex (69.7%) and mesh (62.0%) shortfall.
- **Half pack/unpack — `0x18` / `0x30` / `0x38`.** The `half2`/`pack_unorm` lowering assembles the 32-bit
  result from packed 16-bit lanes with these ops (`18 84 24 85 …`); characterized only as a pack "0x18"
  in the `half_alu` note, not as their own descriptors.
- **64-bit carry-chain — `0x32`** (`32 83 26 ea …`), the explicit carry-generate op EXP-0033 noted for the
  alternate u64 add form.
- **Texture address arithmetic — `0x2e` / `0xb0` / `0x92` / `0x26`.** In-shader texel-address / gather-
  footprint / interpolation-coefficient math around the sampler op; drives the texture shortfall (68.6%),
  worst on `k_tex_msaa`, `k_tex_atomic`, `k_tex_gather`.
- **Non-leaf frame prologue `0x6f`** and a second marker `0x73` (`73 00 00 01`) seen alongside `0x43`.
- **`0x2b`/`0x3b`/`0x5b`/`0x8b` shift-prep** and **`0x97`/`0x17` corners:** now length-tokenized (the prep
  ops via byte+2 low-nibble e/f; the pack/unpack via byte+2==0x56) but only partially descriptor-named — a
  `0x54`-cache-bit variant of `simd_reduce` (`bf 00 54 …`) and unpack (`17 04 54 …`) still fall through.
- The `0x00` / `0x54` "leaders" in the list are **resync noise** (operand bytes reached after an undecoded
  op desyncs the walk), not real opcodes.

### Interpretation

The consolidated DB decodes **~82% of instruction bytes** across a broad own-shader corpus, and **>87%**
of the *core* compute + fragment ISA (the bulk of compiler output — ALU, memory, atomics, control flow,
function calls, subgroup/quad, matrix, transcendentals, get_sr). The residual gaps are a **short, concrete
list** (vertex/mesh varying-emit `0x05/06/57`, half-pack `0x18/30/38`, u64 carry `0x32`, texture address
math `0x2e/b0/92/26`, non-leaf frame `0x6f`) — the objective backlog for closing G-13.

## Established facts → docs
- `docs/isa/encoding-tables.md` — the rendered authoritative encoding table (all 61 descriptors).
- `docs/isa/README.md` — one-line pointer to the above.
- (The prose ISA facts these descriptors encode are already in `docs/isa/README.md` from EXP-0029..0035.)

## Follow-ups
- Descriptor the vertex/mesh varying-store family (`0x05/06/57`) and the half pack/unpack ops
  (`0x18/30/38`) — the largest remaining coverage gap.
- Fully bit-decode the texture-address / interpolation-coefficient ops (`0x2e/b0/92/26`).
- Resolve the `0x54`-vs-`0x56` cache/last-use bit so byte+2-gated descriptors (unpack, simd_reduce)
  match both variants without ambiguity.
