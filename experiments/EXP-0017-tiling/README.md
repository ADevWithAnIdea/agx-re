# EXP-0017: Texture tiling / twiddle order + lossless compression (G17P, Apple9)

- **Date:** 2026-07-06
- **Clean-room category:** HW-PROBE (known pattern in → raw layout out) + DATA-TRACE
  (our own process's GPU BOs via the read-only `tools/iotrace` interposer) + OWN-SHADER
  (our MSL compute/render). **No Apple binary was disassembled or introspected.**
- **Phase / question:** ROADMAP Phase 4 — `docs/tiling/` (texture memory layout: twiddle
  order + lossless compression). Follows EXP-0015 (descriptors), which flagged the
  large-texture bits (word1 bit27 / word3 bit31) + secondary VA @desc+0x10 as the entry
  point to this experiment.
- **Device:** A18 Pro / G17P, macOS 26.6, Command Line Tools (runtime MSL). SIP off.

## Hypothesis
2-D textures in the GPU's optimal (private) layout are stored twiddled (Morton/Z-order)
in fixed tiles; the mapping is a bit-permutation of (x,y); it scales with bytes-per-pixel;
mip levels are packed after the base; and lossless compression, when enabled, adds an
auxiliary metadata buffer pointed to by the secondary VA at descriptor+0x10.

## Method (how we read the raw layout — reproducible)
1. **Write a known pattern.** `texprobe.m` creates a 2-D texture in the optimal layout
   (`newTextureWithDescriptor:`, `StorageModeShared` so the backing BO is CPU-mapped and
   thus captured), then GPU-writes, via a compute image-store, `texel(x,y) = encode(x,y)`
   — for `r32uint`, `value = 0xA5A5<<16 | (y<<8) | x` (a distinctive tag + coordinates).
2. **Capture the raw backing bytes.** The texture is bound into the Tier-2 argument buffer
   (a tiny read kernel) so its **descriptor** is captured, and `kill(SIGUSR1)` triggers the
   `tools/iotrace` interposer to snapshot every registered GPU BO to text hex.
3. **Anchor on the descriptor, decode the map.** `twiddle.py` finds the texture descriptor
   by matching the known dims (`width-1`/`height-1` fields) + 2-D type, reads the exact
   base VA (`word2 | word3[0:11] << 4`), locates the backing BO, and maps element index
   `e = (offset-base)/bpp → texel (x,y)` by decoding each element's stored value. Because we
   start at the exact base, only real texels are read (no false positives). It prints the
   physical element-index grid and **solves (x,y)→e as a GF(2) bit permutation** (exact
   formula). Controls: a **buffer-backed linear** texture (`--linear`) must come out
   row-major; that validates the method distinguishes linear from twiddled.
4. **Compression.** Render a known per-pixel pattern into a render-target texture
   (`--render --usage rt`); the descriptor exposes the layout flags + secondary (aux) VA.
   `--noise` (incompressible) vs the smooth gradient, and `--split` (compressible left /
   incompressible right) characterize the aux metadata. `--mips` writes every level with a
   level-tagged value; `mipmap.py` recovers per-level offsets.

Everything is our own MSL and our own resources whose VAs we print; iotrace logs only DATA
bytes crossing the userspace↔kernel boundary of our own process. Clean per `../../CLAUDE.md`.

## Procedure (device: `~/cleanroom_work/exp0017/`)
```sh
sh run.sh     # matrix: twiddle order (sizes/NPOT), bpp scaling, linear ref, mips, compression sweep
sh run2.sh    # focused: compression trigger sweep, entropy (gradient/noise), mip packing
# single case:
IOTRACE_DUMP_DIR=caps/x DYLD_INSERT_LIBRARIES=./iotrace.dylib ./texprobe --fmt r32uint --w 64 --h 64 --dump
python3 twiddle.py caps/x --fmt r32uint --w 64 --h 64
```

## Files
- `texprobe.m` — parametric probe harness (compute write / render / mip / linear / compression).
- `twiddle.py` — descriptor-anchored twiddle analyzer + GF(2) bit-perm solver.
- `mipmap.py` — per-level offset analyzer.
- `run.sh`, `run2.sh` — device drivers.
- `raw/analysis/` — twiddle.py / mipmap.py output per case (inferred maps).
- `raw/twiddle_raw_*.txt`, `raw/compress_*.txt`, `raw/mip_*.txt`, `raw/linear_*` — curated raw hexdumps.

## Results
See `RESULTS.md`. Headline: optimal 2-D layout is **pure Morton/Z-order** (x on even bits,
y on odd), padded to next-pow2 per axis, byte offset `= morton(x,y)·bpp` (bpp-independent
twiddle). Mip levels pack consecutively, each a pow2-padded Morton plane. Lossless
compression is gated on **absence of ShaderWrite + size ≥ one 16×16 tile**; its aux buffer
sits immediately after the image (secondary VA = base + image size), sized `image_bytes/128`
(1 state byte per 8×4-texel block), holding per-block compression-state codes.
