# RT-9 — Descriptors + Tiling, 2nd overlapping red-team pass

**Role:** independent 2nd-pass verifier of the RT-3 *corrections* to `docs/descriptors/` and
`docs/tiling/`. Goal: (a) independently confirm RT-3's corrected facts are right, and (b) hunt
for any remaining hole. Deliberately uses a **different harness and different sizes** than RT-3.

**Device:** Apple A18 Pro / G17P, macOS 26.6. **Method:** HW-PROBE + OWN-SHADER + DATA-TRACE via
the read-only `tools/iotrace` interposer (built `-arch arm64e`). Every claim re-derived from the
RAW backing bytes with our OWN analyzers — the doc's bit positions/formulas are never assumed. No
Apple binary was disassembled. Clean-room per `../../CLAUDE.md`.

## Why the harness is genuinely independent of RT-3
RT-3's `texprobe.m` encoded texel coordinates in 8 bits per channel (`x&0xff`, `y&0xff`), which
**wraps at 256** — so it structurally could not probe textures wider/taller than 256 (384, 500,
1024, 4095…). RT-9's `t9probe.m` uses **tagged, ≥14-bit coordinate encodings** (r32:
`0xA<<28 | y<<14 | x`; rg32/rgba16/rgba32: full 32-bit channels; rgba8: `R=x.lo G=x.hi B=y.lo
A=y.hi`) so every texel in a large texture carries a unique recoverable coordinate. The solver
`t9tiling.py` is a fresh GF(2) implementation that **derives the tile edge T from the
interleave-break point** rather than plugging into the doc formula.

## Pieces
| file | role | runs on |
|---|---|---|
| `t9probe.m` | Tagged large-coordinate texture probe. `--fmt/--w/--h/--type/--mips/--usage/--desconly`. Writes `texel(x,y)=encode(x,y)` in the GPU-optimal (twiddled) layout, binds it (descriptor captured), SIGUSR1-dumps all BOs. | device |
| `t9tiling.py` | Independent GF(2) solver: recovers the bit-permutation from raw bytes, **derives T** from the low-bit interleave depth, reconstructs from the recovered perm (0-mismatch proof), and separately scores the DOC formula. | host |
| `verify_cols.py` | Tests the **corrected** `cols=⌈W/T⌉` + tile-multiple-padding model against raw bytes and prints BO size vs tile-pad vs pow2-pad. | host |
| `t9desc.py` | Descriptor field checker: reads width/height under BOTH 14-bit and 12-bit hypotheses (locates the descriptor by base-VA-in-BO, not by assuming the packing). | host |
| `t9sp.m` | Sampler (`--mode samp`) + PBE/storage-image (`--mode pbe --access …`) descriptor probe. | device |
| `t9sampcheck.py` | Sampler 8-byte descriptor decoder. | host |
| `bcsize2.m` | Block-compressed (BC1/BC7/ASTC) allocation-size probe via `heapTextureSizeAndAlignWithDescriptor`. | device |
| `raw/` | BO `.hex` snapshots (text) per case + `logs/`. `analysis/RT9_evidence.txt` = consolidated run. | — |

## Reproduce (device: `~/cleanroom_work/rt9/`)
```sh
clang -arch arm64e -dynamiclib -o iotrace.dylib iotrace.c -framework IOKit -framework CoreFoundation
clang -arch arm64e -fobjc-arc -framework Metal -framework Foundation -o t9probe t9probe.m
# one case:
IOTRACE_DUMP_DIR=t_384_rgba8 DYLD_INSERT_LIBRARIES=./iotrace.dylib ./t9probe --fmt rgba8uint --w 384 --h 384 --dump
```
Then pull the dump dir and run `python3 t9tiling.py raw/t_384_rgba8 --fmt rgba8uint --w 384 --h 384`
and `python3 verify_cols.py`. See `RESULTS.md` for the full matrix and verdicts.
