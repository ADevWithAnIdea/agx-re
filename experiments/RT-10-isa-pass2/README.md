# RT-10 — ISA 2nd-overlapping-pass RED-TEAM verification (tex/subgroup/matrix/RT/fragment + control-flow)

**Role:** independent 2nd pass confirming the JUST-CORRECTED ISA decode (ballot `0x17`, shuffle
gate, `0x0f` exec-mask family, DB = 82 descriptors) is right, and hunting for remaining holes.
Uses DIFFERENT kernels than RT-5 / RT-1b / RT-ISA-FIX. No edits to `docs/`, `tools/agx-isa/`,
`tools/iotrace/`, PROVENANCE, or reviews; nothing committed.

**Clean-room category:** OWN-SHADER (compile our own MSL → extract AGX bytes → splice/run on the
A18 Pro) + PUBLIC (the repo's `tools/agx-isa` decoder, read-only). No Apple binary introspected.

## Method
- Device workspace `~/cleanroom_work/rt10/` (tools copied from the fresh `isafix` build + `rtrun`).
- `kernels/` — 22 fresh MSL kernels (p1 subgroup, p2 control-flow, p3 matrix, p4 RT, p5 big shaders).
- `harness/`
  - `census.py` — resync-tokenizer census (mirrors RT-ISA-FIX `analyze.py`): % bytes tokenized
    (length known) + % descriptor-named, over the repo `tools/agx-isa/isadb.py`.
  - `matrix_test.py` — 0xcf operand splices via `persistrun` (A=i+1, B=j+1, C=500 — different from RT-5).
  - `rt_asselect_test.py` + `rtrun2.m` — builds BOTH a primitive AND an instance acceleration
    structure and splices the rt_intersect byte+4 on each path.
  - `find_rt.py`, `mk_matrix_inputs.py` — locators / input generators.
- `raw/` — extracted `_agc.main` hex (`raw_hex.txt`, `frag_hex.txt`), census logs, splice logs.

## Reproduce (device)
```
# extract compute kernels
for f in k/p1_*.metal k/p2_*.metal k/p3_*.metal k/p4_*.metal k/p5_bigcompute.metal; do
  ./shdump --no-fast-math -o k/$(basename $f .metal).bin "$f"
  python3 agxparse.py k/$(basename $f .metal).bin --stage compute --extract-hex ; done
# big fragment render pair
./shdump --no-fast-math --render --vertex v_main --fragment f_main -o k/p5_bigfrag.bin k/p5_bigfrag.metal
# splices
python3 agxtest.py --source k/p1_bcast.metal --function k --grid 32 --tg 32 --out 0=4 --int --splice _agc.main@0x22=06
python3 matrix_test.py
python3 rt_asselect_test.py
```
Census (host, against the repo DB): `python3 harness/census.py raw/raw_hex.txt raw/frag_hex.txt`.

See `RESULTS.md` for the per-family verdicts.
