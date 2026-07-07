# EXP-0039: merge the W2 descriptors (EXP-0037 + EXP-0038) + re-run the byte0 census

- **Date:** 2026-07-07
- **Clean-room category:** OWN-SHADER (merge our own OWN-SHADER-derived descriptors into the
  read-only ISA DB, then tokenize our own compiled bytes). No Apple binary was disassembled.
- **Phase / question:** ROADMAP G-13 (instruction census) + G-6 (authoritative encoding table).
- **Device state:** host-only work (merge + census over the already-extracted EXP-0036 corpus).
  No device dispatch was needed; the underlying encodings were HW-validated in EXP-0037/0038.

## Hypothesis
The two staged "W2" descriptor sets — EXP-0037 (vertex varying store `0x57` + texture coordinate
math) and EXP-0038 (u64 carry `0x32`, non-leaf frame `0x6f`/`0x07`, half pack `0x18`, `0x54↔0x56`
cache bit) — can be merged into `tools/agx-isa/isadb.py` keeping the assembler/disassembler
round-trip green, and re-running the EXP-0036 byte0 census over the same corpus will convert the
flagged undecoded groups into named/lengthed ops, materially raising byte coverage with **no
per-stream regression** and a short, honest residue.

## Method (all clean-room OWN-SHADER)
- **Part A — merge (host).** Fold `experiments/EXP-0037-*/new_descriptors.json` and
  `experiments/EXP-0038-*/new_descriptors.json` into `tools/agx-isa/isadb.py`: 7 new descriptors
  (`vary_store`, `tex_coord_setup`, `coord_madf`, `carry_gen`, `frame_prologue`,
  `link_save_restore`, `half_pack`), the length-rule additions, and the `0x54↔0x56` cache-bit
  match relaxation (applied ONLY to `simd_reduce` `0xbf/0x3f/0xb7` and `unpack_convert` `0x17`;
  the `0x37` derivative-vs-quad-reduce disambiguation and the `pack_convert`↔`frag_color_pack`
  `0x97` split are deliberately left intact). Regenerate `db.json`, extend `roundtrip_test.py`.
- **Part B — encoding tables (host).** `gen_encoding_tables.py` renders `db.json` into
  `docs/isa/encoding-tables.md` (now 68 descriptors, all tabulated).
- **Part C — census (host).** Re-run the EXP-0036 align-forward resync tokenizer (`census.py`,
  identical harness) over the **same** EXP-0036 hex corpus (61 extracted stage `_agc.main`
  programs, 57 unique) with the merged DB, so the coverage delta is attributable purely to the
  merge. Full output in `raw/census.txt`.

## Procedure (re-runnable)
```sh
cd tools/agx-isa
python3 roundtrip_test.py            # ALL PASS
python3 isadb.py --json > db.json    # regenerate machine-readable DB (68 descriptors)
python3 gen_encoding_tables.py       # -> docs/isa/encoding-tables.md
cd ../../experiments/EXP-0039-w2-merge-census
python3 census.py                    # -> raw/census.txt (reuses the EXP-0036 hex/ corpus)
```

## Critical merge caveats (verified by the source experiments; honored here)
- The masked-reduce gate (bit-17 = byte+2 bit1 = source cache/last-use hint, don't-care) is
  applied ONLY to the `0xbf/0x3f/0xb7` reduce leaders and the `0x17` unpack — **NOT** to `0x37`
  (whose `byte+2==0x56` disambiguates quad-reduce from the fragment derivative) and **NOT** to
  `pack_convert` `0x97` (whose `byte+2==0x54` is genuinely the fragment `frag_color_pack`, a
  different op — relaxing it would mis-name fragment streams).
- `0x05`=psel and `0x06`=reconverge are NOT stores (no store descriptor added for them); the only
  vertex varying-store leader is `0x57`.
- `half_pack` (`0x18`) is length-gated on the HW-validated compute shape (`byte+1==0x05`,
  `byte+2` = half_alu result reg, high-nibble 1) rather than blanket `byte0==0x18` — see RESULTS
  §"Regression resolved".

See **RESULTS.md** for the headline numbers and the final undecoded-group analysis.

## Clean-room note
Everything merged is our own OWN-SHADER-derived encoding data; everything tokenized is our own
compiled bytes (the EXP-0036 corpus). `census.py` walks a byte stream with the read-only DB. No
Apple binary was disassembled or introspected.
