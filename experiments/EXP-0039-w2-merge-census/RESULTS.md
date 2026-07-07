# EXP-0039 RESULTS — W2 descriptor merge + byte0-census re-run

## Part A — descriptor merge (host)

Merged the two staged W2 descriptor files into `tools/agx-isa/isadb.py` and regenerated `db.json`.

- **Descriptor count: 61 → 68** (+7). Added:
  - **EXP-0037:** `vary_store` (0x57, 8B — VS varying/[[position]] store), `tex_coord_setup`
    (0xNb, 10B — texture coord/LOD/gather-offset setup), `coord_madf` (0x2e leader, 10B —
    coordinate fused mul-add).
  - **EXP-0038:** `carry_gen` (0x32, 6B — u64 carry-generate), `frame_prologue` (0x6f, 6B —
    non-leaf frame prologue), `link_save_restore` (0x07, 8B — link-reg save/restore), `half_pack`
    (0x18, 4B — half2 pack).
- **Length-rule additions / fixes** in `instr_length()`:
  - `0x57`→8 (vary_store); `0x6f`→6 (frame_prologue); `0x32`→6 and `0x22 byte+2==0x35`→6
    (carry_gen + sibling); `0x2e/0x3e byte+2==0x23`→10 (coord_madf, tightly gated on the
    `23 a0 42` coord signature); `0xNb byte+2 in {0x27,0x2f}`→10 (tex_coord_setup, inserted
    **before** the `(byte+2 hi-nibble 2)`=4 compact-move branch); `0x30/0x90/0xb0`→10 standalone
    sampler fallback (resync-only, gated on the texture-variant byte+2 set).
  - **tex_sample companion-gate FIX:** `byte+1==0x80` widened to `(byte+1 & 0xf0)==0x80` so the
    chained-companion forms (0x82/0x84/0x88 before the 2nd..Nth sample op) absorb their 0xb0/0x90
    sampler op — this is what removed the standalone `0xb0/0x90` undecoded leaders.
  - **float-ALU op-select length FIX:** the fused-mul coordinate/matrix op-selects `0x26/0x2e`
    (low-nibble-9) take length from `byte+4 bit1`, not `byte+2 bit1` (the old flat rule
    mis-lengthed them to 8); `byte+2 in {0x18,0x38}`→4 compact accumulate.
  - **0x07 link-vs-barrier FIX:** `byte+1==0x00`→8 (link_save_restore) vs `byte+1 in {0x04,0x14}`
    →6 (threadgroup_barrier / pixel_order) — the old rule mis-lengthed the link op as a 6-byte
    barrier and desynced every non-leaf helper.
  - **`0x54↔0x56` cache-bit relaxation:** the `simd_reduce` length gate now accepts
    `(byte+2 & ~0x02)==0x54` (both 0x54 and 0x56); the `simd_reduce` and `unpack_convert`
    descriptor matches were relaxed to make bit-17 a don't-care so both cache variants NAME.
    A `cache` field was added to `simd_reduce` so the codec still round-trips both variants
    byte-exact. **Applied ONLY to `0xbf/0x3f/0xb7`+`0x17`** — the `0x37` disambiguation and the
    `pack_convert` (`0x97`) fragment-vs-compute split are untouched (verified: relaxing
    `pack_convert` would let it mis-name the fragment `frag_color_pack` `97 .. 54`).

- **Round-trip: PASS.** `roundtrip_test.py` extended with 12 new real single-op vectors (one per
  new descriptor + the 0x54/0x56 cache variants) and 3 new whole-program tokenizations (`h2add`,
  `u64add`, `nonleaf_frame`). All four sections (real asm↔disasm, synth field round-trip, whole-
  program tokenize-to-0-leftover, packed-immediate codec) report **ALL PASS**.

## Part B — encoding tables (host)

`gen_encoding_tables.py` re-rendered `docs/isa/encoding-tables.md`: **68 descriptors, all 68
tabulated, 0 in "Other"** (the 7 new descriptors were slotted into Integer ALU / Conversions-pack /
Memory / Texture / Control-flow families). The byte-0 length-rule appendix was extended with the
EXP-0037/0038 rows.

## Part C — byte0-group census (host)

Corpus: the **same EXP-0036 hex set** (61 extracted stage `_agc.main` programs, 57 unique,
10,110 instruction bytes), tokenized with the merged DB via the identical align-forward resync
tokenizer. Full output in `raw/census.txt`.

### Headline (objective ISA-completeness metric) — EXP-0036 → EXP-0039

| metric | EXP-0036 | **EXP-0039** |
|---|---|---|
| **byte coverage** | 8268/10110 = **81.8%** | 8886/10110 = **87.9%** |
| cleanly tokenized (length known) | 1025/1286 = 79.7% | 1067/1246 = **85.6%** |
| named (matched a descriptor) | 926 (72.0%) | 940 (75.4%) |
| byte0 groups the DB cannot decode at all | 35 | 31 |

### Byte coverage by stage category — EXP-0036 → EXP-0039

| category | EXP-0036 | **EXP-0039** |
|---|---|---|
| render:vertex | 69.7% | **97.9%**  (vary_store closed the varying-emit path) |
| compute:texture | 68.6% | **80.0%**  (companion-gate + coord math) |
| compute:core | 86.9% | **89.6%**  (carry_gen + cache-bit + half_pack) |
| render:fragment | 94.9% | 95.4% |
| compute:function-table | 90.1% | 90.1% |
| mesh | 62.0% | 65.4% |

**26 stages improved, 0 regressed** (per-stage diff vs the committed EXP-0036 census). Biggest
gains: `k_tex_compare`/`k_tex_gather`/`r_cent_vertex` 67→100, `k_tex_msaa` 44→76, `k_quad` 70→100,
`k_subgroup_reduce` 78→100, `r_deriv_vertex` 68→97, `r_basic_vertex` 74→97, `k_int_bitfield` 84→100.
New top-named mnemonics from the merge: `tex_coord_setup` (32), `vary_store` (26), `falu_acc` (28),
`simd_reduce` (19, now naming both 0x54 and 0x56 variants).

### Final still-undecoded byte0 groups (the honest residue)

179 undecoded resync regions remain; **68 of those are resync-operand noise** (leaders
`0x00/0x54/0x60/0x80` — operand bytes reached *after* a genuinely-undecodable op desyncs the walk,
not real opcodes, per the EXP-0036 analysis). The **111 genuine-leader** occurrences are a short
list of **operand sub-fields, not whole instruction families** — exactly the frontier EXP-0037/0038
predicted:

- **Texel-address / uniform-datapath ATOMIC math** — `0x42` (12), `0x92` (6), `0x52`/`0x62`/`0x85`/
  `0xb2`/`0xd2` (1-2 each). The `Xx 81 27/35 …` coefficient/address arithmetic that dominates
  `k_tex_atomic` (still the densest residual stage at 65%). A full bit-decode of the
  address-generation ALU is the follow-up EXP-0037 flagged.
- **VS-select value-compute family** — `0x1a`/`0x21`/`0x20`/`0x2a` (1-2 each). The per-vertex
  `vid==k ? A : B` select/compare chain that *feeds* the `0x57` varying stores. EXP-0037 decoded
  the STORES (vertex is now 97.9%); the value computation is a separate select family it explicitly
  left as a follow-up. Small now, not a whole family.
- **Half-pack 6-byte high-register sibling** — `0x18` (7) / `0x38` (3) with `byte+2==0x24`. The
  `half_pack` 4-byte compute form is now decoded; the 6-byte high-register/vertex sibling
  (`18 84 24 …`, whose exact length bit EXP-0038 did not isolate) is a documented follow-up and is
  deliberately NOT force-lengthed (see below).
- **Control-flow mask sub-ops** — `0x0f` (5). The `0f 82 …` execution-mask push/pop/reconverge
  variable-length forms (a known EXP-0010 follow-up), distinct from the decoded jump/call/return.
- **Uncharacterized `0x07` sub-op** — `0x07` (15) with `byte+2==0x02` (`07 22 02 00`), a distinct
  0x07-family form (not the barrier/link/pixel-order variants). Minor.
- The remaining ~30 count-1/2 leaders (`0x03/0x33/0x2c/0x3c/0x5b/0x1b/0x8c/0x4c/0x4b/0x31/…`) are
  resync landings on operand bytes, not real opcodes.

**Judgment:** the merge closed the two large families the census was missing (the VS varying-emit
store and the texture coordinate/companion math), plus the compute u64-carry / non-leaf-frame /
half-pack / cache-bit gaps. Every remaining gap is an **operand-level sub-field or a resync
artifact — not a whole undecoded instruction family.** The core compute + fragment ISA is
~90-95% byte-decoded; the residual backlog for closing G-13 is the texel-address atomic ALU and the
VS-select value-compute chain (both operand-level), not new opcode groups.

## Regression resolved

Applying EXP-0038's `half_pack` as a **blanket** `byte0==0x18`→4 rule dropped `k_cvt_half` 78→76%:
in this broad corpus the *only* aligned 0x18 leaders are the 6-byte high-register sibling
(`18 84 24 …`, byte+1≠0x05) and operand bytes reached via resync (`18 05 e7 00`, byte+2 a store
opcode) — the blanket rule mis-lengthed the sibling and let the resync walk spuriously NAME operand
bytes as `half_pack`, splitting a `device_store`. **Resolution:** length-gate `half_pack` on the
HW-validated compute shape (`byte+1==0x05` AND `byte+2 & 0xf8 == 0x18`, i.e. the half_alu result
reg). This decodes exactly the encoding EXP-0038 validated (`18 05 18 03` / `18 05 19 03` /
`18 05 1b 07`), never mis-lengths the 6-byte sibling, and never names operand bytes. Result:
`k_cvt_half` 78→80, **0 regressions across all 57 stages**, and overall byte coverage 87.9% (the
0.1% below the blanket's 88.0% was spurious operand-byte naming — the gated number is honest).

## Established facts → docs
- `docs/isa/encoding-tables.md` — refreshed authoritative encoding table (all 68 descriptors).
- (The prose ISA facts these descriptors encode were established in EXP-0037/0038; the orchestrator
  owns any `docs/isa/README.md` prose updates.)

## Follow-ups (unchanged frontier, now smaller)
1. Bit-decode the texel-address / interpolation-coefficient atomic ALU (`0x42`/`0x92` family) —
   the densest residual, worst on `k_tex_atomic` (65%).
2. Decode the VS-select value-compute family (`0x1a`/`0x21`/`0x40`) that feeds the `0x57` stores.
3. Isolate the length bit of the 6-byte high-register `half_pack` sibling (`0x18`/`0x30`/`0x38`,
   byte+2==0x24) and the `0x6f` frame-size field.
4. Length the `0x0f` execution-mask push/pop sub-ops and the `0x07 byte+2==0x02` sub-op.

## Clean-room status
Clean. Only our own OWN-SHADER-derived encoding data was merged; only our own compiled bytes (the
EXP-0036 corpus) were tokenized with the read-only DB. No Apple binary was disassembled. No
`tools/iotrace/`, other `docs/*`, `PROVENANCE`, `ROADMAP`, or `reviews/` were edited; nothing was
committed.
