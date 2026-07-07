# EXP-0001 Results — raw A18 Pro AGX byte extraction

Clean-room category: **OWN-SHADER** (+ PUBLIC for the disassembler attempt).
All bytes below are the compiled form of MSL **we wrote** (`kernels/*.metal`).

## 1. Extraction works — the method that succeeded

`shdump.m` (public Metal API, our source) → `serializeToURL:` → `agxparse.py`
(our Mach-O parser). Exact chain:

1. `id<MTLLibrary> lib = [dev newLibraryWithSource:src options:opts error:&err]`
2. pick the kernel `MTLFunction`; `newComputePipelineStateWithFunction:` (validates it).
3. `arc = [dev newBinaryArchiveWithDescriptor:…]`;
   `[arc addComputePipelineFunctionsWithDescriptor:cdesc …]`;
   `[arc serializeToURL:…]`.
4. Parse the container: it is a **Metal fat binary** (magic `0xCBFEBABE`) with two
   fat-arch images:
   - **AIR64** (`cputype 0x1000017`) — begins with `MTLB` and contains LLVM
     bitcode (`BC\xC0\xDE` present). This is the portable AIR, *not* machine code.
   - **AppleGPU** (`cputype 0x1000013`) — a real Mach-O (`filetype 13`,
     MH_GPU_DYLIB) with sections `__TEXT,__reflection`, `__TEXT,__compute`,
     `__TEXT,__descriptor`, `__TEXT,__metallib`.
5. The `__TEXT,__compute` section is **itself a nested Mach-O** (also AppleGPU).
   Its `__TEXT,__text` holds the AGX machine code, carved by the symbol table:
   - `_agc.main.constant_program` — the prolog / "constant program" (preamble).
   - `_agc.main` — the main shader program.

`agxparse.py --extract-hex --symbol _agc.main` returns the raw main-program bytes.

## 2. Hard evidence it is AGX machine code, not AIR

- The two images are distinguished by **Mach-O `cputype`**: `0x1000013` = AppleGPU
  (native), `0x1000017` = AIR64 (bitcode). We extract only from the AppleGPU image.
- **`BC\xC0\xDE`** (LLVM bitcode magic) appears **only** inside the AIR64 image; the
  AppleGPU `__text` we extract does **not** contain it.
- The extracted bytes do **not** parse as LLVM bitcode; they are raw, variable-length
  instruction parcels (all lengths even; see §4). The empty kernel's whole main is a
  single 4-byte word `0e000000`.
- Cross-check: the same container, inspected only for *structure*, is consistent with
  the layout the public metal-archive-extractor expects for AppleGPU images.

## 3. Byte samples (extracted `_agc.main`, first bytes / lengths)

| kernel | main len | first ≤32 bytes of `_agc.main` (hex) |
|---|---:|---|
| k00_empty      |  4 | `0e000000` |
| k01_fadd       | 56 | `1ca0100667105400 0001200051010040 4600670044040101 2000510100404600` |
| k02_fmul       | 56 | `1ca0100667105400 0001200051010040 4600670044040101 2000510100404600` |
| k03_iadd       | 60 | `1ca0100667105400 0001200051010040 4600670044040101 2000510100404600` |
| k05_fma        | 72 | `1ca0100667105400 0001200051010040 4600670054040101 2000510100404600` |
| k10_load_store | 36 | `1ca0100667104400 0001200051010040 4600e70056000101 2100110000901100` |

Full hex for every kernel and both regions is in `raw/k*.main.hex`,
`raw/k*.cprog.hex`, `raw/k*.text.hex`. The **constant_program** (prolog) is a fixed
64 bytes for every kernel; kernels that load nothing special share the trivial
prolog `0e000000` + `0600`-padding, while kernels that set up uniforms use the
prolog prefix `030007000200000060000e000000` + padding.

**Determinism:** every kernel's `_agc.main` was byte-identical across **3
independent compilations** (`raw/determinism.txt`, all `STABLE`). Same source →
same bytes. (Note: determinism is checked on the *extracted code*, not the whole
container, which can carry variable metadata.)

**Instruction-length hints (observations, not yet validated on hardware):**
- All region lengths are even → AGX instructions are multiples of 2 bytes
  (parcels), matching the general AGX shape.
- `0e000000` (4 bytes) terminates every `_agc.main` and is the *entire* body of the
  empty kernel → strong hint it is the **program-stop / end** instruction.
- A fixed 4-byte word `1ca01006` opens every non-empty `_agc.main` → likely a fixed
  preamble (e.g. thread-index / setup). To be confirmed in Phase 1.

## 4. Minimal-pair diffs (differential compilation) — `raw/diffs.txt`

All diffs are over the extracted `_agc.main`. Bytes are at fixed offsets because
each pair keeps identical MSL shape and changes exactly one thing.

| pair | change | bytes that move | delta |
|---|---|---|---|
| **op change** k01 vs k02 | `a+b` → `a*b` (float) | **1 byte @ 0x22** | `1c → 1d` (xor `01`, bit 0) |
| **immediate** k06 vs k07 | `a+1.0f` → `a+2.0f` | **1 byte @ 0x13** | `b1 → c1` (xor `70`, bits 4–6) |
| **operand swap** k12 vs k13 | `a-b` → `b-a` (fsub) | **2 bytes @ 0x08 and 0x16** | `00↔01` at each (bit 0), complementary |
| **binding index** k08 vs k09 | write `buffer(0)` → `buffer(1)` | **none** | main, prolog **and** `__descriptor` all byte-identical |

Readings:
- **Op-select is a tiny field.** float add vs mul flips a single bit in one byte
  (`1c`→`1d`) at a fixed position — the ALU operation selector.
- **Float immediates use a compact encoding, not IEEE-754.** 1.0 vs 2.0 changes one
  byte in bits 4–6 (`b1`→`c1`), i.e. an exponent-like field of a packed float
  immediate — *not* the 32-bit words `3f800000`/`40000000`. This matches AGX's
  known small-float-immediate style and is a concrete Phase-1 lead.
- **Source-operand selectors are localized single bits.** Swapping the two operands
  of a non-commutative op flips one bit in each of two positions (0x08 and 0x16),
  and the flips are complementary — the two source-register fields exchanging.
- **Buffer *index* is not in the shader code.** Writing `buffer(0)` vs `buffer(1)`
  (single-buffer kernels) produced an **identical** metallib — same `_agc.main`,
  same prolog, and even the same `__TEXT,__descriptor` bytes. The compiler assigns
  the one referenced buffer a fixed uniform slot; the Metal binding index is
  resolved outside the AGX instruction stream (at bind time / argument table). This
  is a first-class *negative* result and a flag for later cmdstream tracing.

Supplementary (structure, not single-field): **int add vs float add** (k03 vs k01)
and **int add vs int mul** (k03 vs k04) differ in length and in many bytes — the
integer ALU path uses different opcodes/encoding than the float path (expected;
`raw/diffs.txt`).

## 5. Public applegpu (G13) disassembler on A18 bytes — `raw/applegpu_attempt.txt`

Running dougallj/applegpu's G13/M1 disassembler on our extracted A18 `_agc.main`:
- Most 2-byte parcels return **`<disassembly failed>`**.
- The few that "decode" are **nonsense** for the source (e.g. `st_tile`,
  `fcmpsel …, 0.53125`, `fmul16.sat`, `iter`, `st_var` for a plain `a+b` or copy
  kernel) — false decodes from a mismatched table.
- The single "clean" decode, `0e000000 → iadd r0l,0,0`, is a **false friend**: in
  A18 this word is the program terminator (§3), not an integer add.

Conclusion: **the A18 Pro AGX ISA does not match G13**, confirming the ROADMAP
premise empirically. applegpu is reusable only as a *structural template* and for
its ISA-agnostic testbed, not as a decoder to extend.

## 6. Clean-room status

Clean. Everything inspected is the compiled form of our own MSL. Tools are ours
(`shdump.m`, `agxparse.py`, `bytediff.py`); the only third-party code used is the
public MIT applegpu disassembler, applied to our own bytes. No Apple binary was
disassembled or introspected. No Apple blob is committed — `raw/` holds only
hex/text; the `.bin` archives remain on the device under `~/cleanroom_work/`.
