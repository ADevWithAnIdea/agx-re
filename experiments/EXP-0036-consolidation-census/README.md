# EXP-0036: final ISA consolidation + encoding tables + byte0-group census

- **Date:** 2026-07-07
- **Clean-room category:** OWN-SHADER (compile our own MSL, extract & tokenize our own compiled bytes)
- **Phase / question:** ROADMAP G-6 (authoritative encoding table in `docs/`) + G-13 (instruction census)
- **Device state:** Apple A18 Pro / G17P, macOS 26.6, runtime `newLibraryWithSource:` (Command Line Tools).

## Hypothesis
The per-experiment instruction descriptors staged by EXP-0030/0031/0033/0034/0035 can be merged into
one machine-readable DB (`tools/agx-isa`) that (a) keeps the assembler/disassembler round-trip green,
(b) renders into a self-contained human-readable encoding table in `docs/`, and (c) tokenizes a broad
corpus of our own shaders well enough to give an objective "how complete is the ISA" number — with the
remaining undecoded byte0 groups being the concrete last gaps.

## Method (all clean-room OWN-SHADER)
- **Part A — merge (host).** Fold the 5 staged `new_descriptors.json` into `tools/agx-isa/isadb.py`,
  apply the 6 EXP-0033 length-rule corrections, resolve the cross-experiment corrections (0x43 = the
  generic call/frame marker, re-scoped from mesh; get_sr SR#=byte1; 0x97/0x17 pack-vs-fragpack/ballot
  gated by byte+1/byte+2), regenerate `db.json`, and extend `roundtrip_test.py`.
- **Part B — encoding tables (host).** `gen_encoding_tables.py` renders `db.json` into
  `docs/isa/encoding-tables.md` (per-instruction bit-field tables grouped by family).
- **Part C — census (device).** Compile a broad OWN-MSL corpus (`corpus/`, ~53 kernels / 61 stages
  spanning int/float/half arithmetic, conversions, control-flow+loops+calls, memory/atomics/threadgroup,
  textures/samplers/gather/compare, subgroup/quad, matrix, a vertex+fragment render set, a mesh pipeline,
  and a `visible_function_table` call), extract every stage's `_agc.main` with `shdump`+`agxparse`, and
  tokenize each with the merged DB (`census.py`, an align-forward resync tokenizer). This is clean-room
  because only our own MSL is compiled and only our own compiled bytes are inspected.

## Procedure (re-runnable)
```sh
# device: build harnesses + corpus, extract every stage's _agc.main -> hex/
scp tools/shdump/{shdump.m,agxparse.py} experiments/EXP-0036-*/{census_extract.py,run_census.sh} \
    experiments/EXP-0036-*/corpus/*.metal  user@DEVICE:~/cleanroom_work/exp0036/...
ssh DEVICE 'cd ~/cleanroom_work/exp0036 && bash run_census.sh'   # -> hex/*.hex
scp 'user@DEVICE:~/cleanroom_work/exp0036/hex/*.hex' experiments/EXP-0036-*/hex/

# host: merge is already in tools/agx-isa/; verify + regenerate + census
cd tools/agx-isa && python3 roundtrip_test.py          # ALL PASS
python3 isadb.py --json > db.json                       # regenerate machine-readable DB
python3 gen_encoding_tables.py                          # -> docs/isa/encoding-tables.md
cd ../../experiments/EXP-0036-consolidation-census && python3 census.py   # -> raw/census.txt
```

## Raw results
- `hex/` — the extracted `_agc.main` of every corpus stage (text hex only; no Apple blobs).
- `raw/census.txt` — the full byte0-group census.
- `corpus/` — our own MSL. `run_census.sh` / `census_extract.py` / `census.py` — the harness.

See **RESULTS.md** for the analysis and the headline numbers.

## Clean-room note
Everything compiled is our own MSL; everything inspected is our own compiled bytes. `agxparse.py` walks
the public Mach-O container format. No Apple binary was disassembled or introspected.
