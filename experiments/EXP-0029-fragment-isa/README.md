# EXP-0029: Fragment-shader ISA cluster (interpolation, output/epilog, tilebuffer, pixel ordering)

- **Date:** 2026-07-07
- **Clean-room category:** OWN-SHADER (+ PUBLIC for the ISA DB used to tokenize)
- **Phase / question:** ROADMAP gap G-4 (fragment pipeline is the biggest ISA gap);
  capability backlog #2 (interpolation), #5 (programmable blend / tilebuffer), #7 (raster order groups).
- **Device:** Apple A18 Pro (G17P), macOS 26.6 (25G5043d). Workspace `~/cleanroom_work/exp0029/`.

## Hypothesis
The fragment stage uses instruction groups compute never emits (EXP-0008 saw the leaders
`0x2f/0x3f/0xaf`, `0x05/0x06/0x57`, `0x07/0x87/0x97`, deriv `0x37`). We expected: a varying
**interpolate** op with a mode field (perspective / flat / centroid / sample); a **colour store**
to the tilebuffer with a render-target index; a **tilebuffer read** for programmable blending
(EXP-0019 found blend is in-shader); and a fragment **pixel-ordering** primitive (the compute
interlock analogue from EXP-0025) for raster-order-groups.

## Method (clean-room legal — OWN-SHADER + HW-PROBE)
1. Write minimal `[[vertex]]`+`[[fragment]]` MSL (`kernels/*.metal`) that isolates one feature
   each, changing a single qualifier/attribute between variants for clean differential compilation.
2. Compile on-device with `tools/shdump --render` (and `scripts/shdump_ext.m` for MRT/depth pipelines
   that need >1 colour attachment); extract the fragment `_agc.main` bytes with `agxparse.py`.
3. Tokenize + byte-diff (`scripts/frag_tok.py`, `scripts/tok.py`) to locate the new groups' lengths
   and fields.
4. **HW-validate** by splicing a field byte into the archive and rendering with
   `tools/agxtest/agxrender.m` (extended in `scripts/agxrender_ext.m` with a `--clear` option),
   observing the read-back pixel (`scripts/splice_render.py`).

Everything inspected is the compiled form of MSL **we wrote**. No Apple binary was disassembled.

## Procedure (reproduce)
```sh
# on device, in ~/cleanroom_work/exp0029 (tools built there):
clang -fobjc-arc -framework Metal -framework Foundation -o shdump shdump.m
clang -fobjc-arc -framework Metal -framework Foundation -o shdump_ext shdump_ext.m
clang -fobjc-arc -framework Metal -framework Foundation -o agxrender_ext agxrender_ext.m
bash extract_all.sh          # compile + extract fragment/vertex hex for the interp/output kernels
bash run_validations.sh      # all HW renders + splices -> raw/validations.log
# host-side analysis:
python3 scripts/frag_tok.py                      # fragment tokenizer (0 leftover on interp/output kernels)
python3 ../../tools/agx-isa/roundtrip_test.py    # DB round-trip incl. the new fragment descriptors -> ALL PASS
```

## Raw results
- `raw/*.frag.hex`, `raw/*.vert.hex` — extracted AGX bytes (OWN-SHADER).
- `raw/tokenization.txt` — every fragment kernel tokenized with the updated DB.
- `raw/validations.log` — all HW renders + splice-and-observe outputs.

See `RESULTS.md` for the analysis and the validated encodings (folded into `tools/agx-isa/`).

## Follow-ups
- Full bit-decode of the `iter` byte+8 location bits and the perspective-W coefficient addressing.
- Depth-store (`0xd7 14`) splice validation (needs a readable depth attachment).
- ROG stale-read splice proof (needs overlapping-fragment geometry).
- Fragment texture-sample / derivative groups (`0x18/0xb0/0x37`) still only partly tokenized.
