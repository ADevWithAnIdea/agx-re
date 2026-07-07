# EXP-0040: merge objective-2 ISA descriptors (EXP-O2C + EXP-O2D) + re-census

- **Date:** 2026-07-07
- **Clean-room category:** OWN-SHADER (merge our own OWN-SHADER-derived descriptors into the
  read-only ISA DB, then tokenize our own compiled bytes). No Apple binary was disassembled.
- **Phase / question:** ROADMAP G-13 (instruction census) + G-6 (authoritative encoding table).
- **Device state:** host-only work (merge + census over already-extracted OWN-SHADER corpora).
  No device dispatch needed; the underlying encodings were HW-validated in EXP-O2C / EXP-O2D
  (and EXP-0022 / EXP-0023 for the matrix / RT cores they extend).

## Hypothesis
The two staged "objective-2" descriptor sets — **EXP-O2C** (RT completion tail + tensor/matrix
operand decode) and **EXP-O2D** (compute/fragment tail: bfloat ALU, imageblock, subgroup tail,
atomic fences) — can be merged into `tools/agx-isa/isadb.py` keeping the assembler/disassembler
round-trip green, and a re-census over the EXP-0036 corpus **plus** the new RT/tensor/bfloat/
imageblock kernels will (a) not regress the original corpus and (b) name the new instruction
families, leaving only operand-level residue.

## Method (all clean-room OWN-SHADER)
- **Part A — merge (host).** Fold `EXP-O2C-*/new_descriptors.json` and
  `EXP-O2D-*/new_descriptors.json` into `tools/agx-isa/isadb.py`:
  - **Updated in place:** `matrix_mac` (full `0xcf` operand decode — A=byte+5, B=byte+6,
    C=byte+7, dst=byte+8, accum=byte+11 bit0, dtype=byte+1, mode=byte+2, op-enable=byte+10,
    A-sub-descriptor=byte+3) and `rt_intersect` (motion mode byte+2=0x10; AS-select byte+4
    0x8b primitive / 0x1b instance / 0xbb primitive-motion; byte+3 motion time).
  - **7 new descriptors:** `rt_ray_mem` (0x5f, 14B), `rt_transform_test` (0x?2 `27 81 22`, 10B),
    `ray_move` (0x?b byte+2 0x80/0x81, 4B), `bf_alu` (0x11 byte+1 0x02, 8B), `imageblock_store`
    (0xe7 byte+1 0x16, 12B), `imageblock_load` (0x67 byte+1 0x16, 12B), `mem_fence`
    (0x07 `54 84 0a`, 6B device fence).
  - **Refined enums/semantics:** `simd_reduce` (float `simd_product` byte+1=0x06 bit7=1, float
    exclusive-scan byte+7=0x32, fmin/fmax), `simd_shuffle` (shuffle_and_fill byte+1=0x06),
    `get_sr` (SR 0x84 = `simd_is_helper_thread`).
  - **Length-rule fixes:** the **load-bearing** `0x11` bfloat fix (add/mul=8B, fma=10B;
    disambiguate cvt_f2h vs bf_alu on **byte+1**, not byte+2 — they share opsel byte+2==0x1c);
    `0x5f`→14; `0x?2 27 81 22`→10; `0x?b byte+2∈{80,81}`→4; `0xe7 byte+1∈{06,16}`→12;
    `0x67 byte+1∈{06,0e,16}`→12.
  - Regenerate `db.json`, extend `roundtrip_test.py`.
- **Part B — encoding tables (host).** `gen_encoding_tables.py` renders `db.json` into
  `docs/isa/encoding-tables.md` (now 75 descriptors, all tabulated, 0 in Other).
- **Part C — census (host).** `extract_new_hex.py` pulls the new-family `_agc.main` hex out of
  the EXP-O2C/O2D raw dumps into `hex/`; `census.py` runs the EXP-0036 align-forward resync
  tokenizer over the **reused EXP-0036 corpus** (57 unique) **plus** the new families (36 unique:
  RT / tensor / MPP-matrix / bfloat / imageblock-tile), reporting the EXP-0036 subcorpus
  (apples-to-apples vs EXP-0039), the new families alone, and the combined corpus.

## Procedure (re-runnable)
```sh
cd tools/agx-isa
python3 roundtrip_test.py            # ALL PASS (275 real+synth vectors)
python3 isadb.py --json > db.json    # regenerate machine-readable DB (75 descriptors)
python3 gen_encoding_tables.py       # -> docs/isa/encoding-tables.md
cd ../../experiments/EXP-0040-obj2-merge-census
python3 extract_new_hex.py           # -> hex/ (RT/tensor/MPP/bfloat/tile _agc.main)
python3 census.py                    # -> raw/census.txt
```

## Critical merge caveats (honored here)
- **`0x11` bfloat vs `0x11` cvt_f2h** — DO NOT confuse the native bfloat ALU (`bf_alu`, byte+1
  0x02/0x04) with the fp32→fp16 convert (`cvt_f2h`, byte+1 0x03). They SHARE opsel byte+2==0x1c,
  so the disambiguation is byte+1, and the length is length-polymorphic on byte+1.
- **`rt_transform_test` gated on the full `27 81 22` signature** (byte+2/+3/+4), NOT just
  byte+2==0x27 — the compute texel-address / coordinate ALU is also `Xx 81 27 …` (low-nibble-2,
  byte+2==0x27) with byte+3==0x80 / byte+4≠0x22; the loose byte+2-only gate spuriously names that
  compute residual as an RT op (the first census run caught it in k_int_arith/k_cf_switch/…).
  See RESULTS §"Regression / collision resolved".
- **`imageblock_store`/`imageblock_load` match the TILE first-access variant byte+1==0x16**, NOT
  0x06 — byte+1==0x06 stays named `frag_color_store`/`tile_read` (EXP-0029); matching 0x06 would
  duplicate those descriptors. `mem_fence` (byte+3==0x84) is a strictly-more-specific match than
  `threadgroup_barrier` (byte+3 0x61/0x85), so it wins without touching the barrier.
- The EXP-0039 gating caveats are preserved: the `0x37` derivative-vs-quad-reduce byte+2==0x56
  disambiguation and the `pack_convert`↔`frag_color_pack` `0x97` split are untouched; `half_pack`
  stays shape-gated.

See **RESULTS.md** for the numbers and the final undecoded-group analysis.

## Clean-room note
Everything merged is our own OWN-SHADER-derived encoding data; everything tokenized is our own
compiled bytes (the EXP-0036 corpus + the EXP-O2C/O2D-extracted RT/tensor/bfloat/imageblock
`_agc.main`). `census.py` walks a byte stream with the read-only DB. No Apple binary was
disassembled or introspected. `raw/` and `hex/` contain text (hex) only — no binary archives.
