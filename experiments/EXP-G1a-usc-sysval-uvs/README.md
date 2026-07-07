# EXP-G1a: USC bind grammar (G1-a) · sysval→uniform (G1-c) · UVS varying linkage (G1-e)

- **Date:** 2026-07-07
- **Clean-room category:** DATA-TRACE (change-one-Metal-parameter byte-diff of our own
  command/control BOs) + OWN-SHADER (compile our own MSL, extract `_agc.main`, splice+render).
- **Phase / question:** objective-1 gaps G1-a (USC binding-word grammar), G1-c (sysval→uniform
  register), G1-e (UVS/varying VS↔FS linkage) — `docs/porting-guide.md` §8.
- **Device:** A18 Pro / G17P, macOS 26.6 (25G5043d), 5 GPU cores. Zero faults, zero reboots.

## Hypothesis
1. **G1-a** — adding a texture / sampler / uniform buffer one at a time will expose a bind-word
   grammar in the USC program `0x10000130000` (tag bytes distinguishing Shader/Uniform/Texture/
   Sampler, and a texture/sampler count↔buffer split field).
2. **G1-c** — the USC uniform-preamble program moves system values / FF datums into uniform
   registers; varying the sysvals read will show which slot holds which datum.
3. **G1-e** — a varying's VS UVS output slot (0x57 store `byte+4=index<<5`, EXP-0037) couples to
   the FS `iter` coefficient index (0x2f `byte+5=slot<<1`, EXP-0029); reordering varyings will move
   the FS output.

## Method (all clean-room legal)
- **`uvar.m`** — parametric OWN draw. Binds N fragment textures / M samplers / K FS uniform buffers /
  J VS uniform buffers and passes a controllable count/order of `float4` varyings VS→FS; `--vout k`
  echoes varying `k` to the render target for pixel readback. `--dump` snapshots every registered BO
  (`kill(SIGUSR1)`) through the existing `tools/iotrace` interposer (DATA-TRACE, arm64e).
- **`analyze.py`** — host-side byte-diff over the captured BO hexdumps (`raw/pick*/`): `diff`,
  `dump`, `multidiff`, `whichbo`. Picks the non-empty copy of each dual-mapped BO.
- **`shdump` + `agxrender`** (repo tools, built on device) — compile our own `vary3/linkA/linkB`
  MSL, extract VS/FS `_agc.main`, and render-readback for HW validation. `scan3.py`/`scan2.py`
  decode the VS `0x57` store slots and FS `0x2f` iter coefficients from **our own** bytes.

No Apple binary was disassembled. The USC uniform-preamble is compiler-generated code: we document
its **descriptor/binding words** (non-copyrightable) and locate — but do **not** transcribe — its ALU
(CLAUDE.md rule 5).

## Procedure
```sh
# device: ~/cleanroom_work/exp_g1a/  (iotrace.dylib reused from exp0024)
clang -arch arm64e -fobjc-arc -framework Metal -framework Foundation -o uvar uvar.m
sh run.sh                         # 25-config sweep (resource counts, sysvals, varyings)
# G1-a re-run with samplers/buffers actually *used* (fixed FS) -> pick2/
# HW validation:
./shdump -o linkA.bin --render --vertex v_main --fragment f_main linkA.metal
./agxrender --archive linkA.bin --source linkA.metal --vertex v_main --fragment f_main --width 4 --height 4
# host:
python3 analyze.py whichbo base tex1
python3 analyze.py dump tex2 10000248000 0x480 0x80
python3 scan3.py                  # VS 0x57 slots + FS 0x2f coefficients
```

## Raw results
- `raw/pick2/` — fixed-harness re-run (G1-a texture/sampler/buffer bind evidence).
- `raw/pick/` — original sweep (G1-c sysval, G1-e varying-count).
- `raw/ana/G1a_bind_grammar.txt`, `G1c_sysval_uniform.txt`, `G1e_uvs_linkage.txt`,
  `G1e_hw_validation.txt` — the decoded tables.
- `raw/shaders/` — our own `vary3/linkA/linkB` MSL + extracted VS/FS `_agc.main` hex.

See `RESULTS.md` for the decoded grammar, slot maps, and HW-validated vs inferred marking.

## Established facts → docs
- G1-a bind grammar (arg-buffer 0x10000248000 tex/samp table + split; buffer table 0x10000100000;
  USC preamble header tags), G1-c sysval-not-preloaded + uniform-slot preload, G1-e UVS slot↔iter
  linkage + count descriptor → `docs/cmdstream/` + `docs/isa/` → `PROVENANCE.md` (DATA-TRACE/OWN-SHADER,
  EXP-G1a).

## Follow-ups
- Exact FS-coefficient ↔ VS-slot offset in perspective mode (coef 0 = 1/W; user comps follow) is
  compiler-scheduled; a linker must assign matching slots — not a byte-addressable remap table.
- The `0x0042XXXX` uniform-data heap base + the code-BO→firmware shader handoff remain kernel items.
