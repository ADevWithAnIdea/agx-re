# Apple G13 GPU Architecture Reference

**Source:** https://dougallj.github.io/applegpu/docs.html  
**Author:** Dougall Johnson  
**Based on:** Reverse engineering of Apple G13 GPU (as used in M1 SoC)  
**Caveat:** "likely to have mistakes"

---

## Architecture Overview

The G13 represents Apple's GPU design in the M1 SoC, documented through reverse engineering. The architecture organizes computation around 32 threads per SIMD-group, mirroring Metal's terminology.

---

## Register Organization

Each SIMD-group accesses up to 128 general-purpose registers (r0-r127), with per-thread 32-bit storage.

**Access modes:**
- Full 32-bit (default)
- Low 16-bits (e.g. `r5l`)
- High 16-bits (e.g. `r5h`)
- Register pairs for 64-bit operations (e.g. `r4_r5`)

**Special registers:**
- `r0l` - execution mask stack depth counter
- `r1` - link register
- `u0-u255` - uniform registers (thread-invariant; store buffer addresses, uniforms, etc.)

**Occupancy trade-off:**
- Up to ~104 registers: occupancy is unaffected
- Beyond ~104 registers: thread count decreases linearly in 64-thread increments
- Total register file: ~208 KiB per threadgroup, 24 parallel threadgroups = ~4.875 MiB
- No register spilling until >256 registers are used

---

## Execution Control and Divergence

**Execution mask:** 32-bit value, one bit per thread.
- 1 = thread active
- 0 = thread inactive (deactivated by divergent control flow)

**Divergence mechanism:**
- Uses a hardware stack maintained in r0l
- Stack depth counter allows re-enabling inactive threads when convergence point is reached
- This differs from NVIDIA's per-thread PC approach

**Control flow instructions:**
- `pop_exec` - pop execution mask from stack
- `if_icmp` / `if_fcmp` - integer/float conditional, push mask
- `else_*cmp` - flip mask for else branch
- `while_*cmp` - loop head with mask update
- `jmp_exec_any` - branch if any thread active
- `jmp_exec_none` - branch if no threads active

---

## Instruction Encoding

Variable-length instructions: **2 to 12 bytes**.

The **L-bit** (in the opcode encoding) indicates truncation: unused trailing bytes are omitted to reduce code size.

---

## Arithmetic Instructions

### Integer Arithmetic
- `iadd` - integer add (with optional saturation)
- `imadd` - integer multiply-add (with saturation support)
- `imad` (complex pipeline, sometimes avoided in favor of repeated additions)

### Floating-Point
All FP ops support **free modifiers** on sources (no extra cost):
- Absolute value (`abs`)
- Negate (`neg`)
- Saturate (`sat`) on destinations

**Free conversion:** 16-bit <-> 32-bit on sources and destinations

Instructions:
- `fmadd` - fused multiply-add (primary workhorse)
- `fadd`, `fmul`
- `floor`, `ceil`, `trunc`, `rint` (rounding)
- `rcp` - reciprocal (~6.5 cycle latency)
- `rsqrt` - reciprocal square root (~8.99 cycle latency)
- `log2`, `exp2`

**Instruction latencies (approximate):**
- FADD16: ~2.16 cycles
- FFMA32: ~2.21 cycles
- RECIP32: ~6.5 cycles
- RSQRT32: ~8.99 cycles

### Bitfield Operations
- `bfi` - bit field insert
- `bfeil` - bit field extract (with immediate length)
- `extr` - extract bits
- `shlhi`, `shrhi` - shift high bits

### Bit Manipulation
- `bitop` - arbitrary bitwise operation (AND/OR/XOR/NOT combinations)
- `bitrev` - bit reverse
- `popcount` - population count
- `ffs` - find first set bit

---

## Scalar Architecture

The M1 GPU is **scalar at all bit widths**:
- Operations work on scalar values per lane
- No explicit vector types at the ISA level (vectorization is via SIMD-groups)
- Superscalar execution: more 16-bit ALUs than 32-bit ALUs
- Hardware scheduling (not compiler-managed scheduling)

**Performance characteristic:**
- At low occupancy: F16/I16 significantly faster than F32/I32
- 0.84-cycle penalty for 32-bit register dependencies vs 0.56-cycles for 16-bit

---

## Memory System

### Device Memory (L2/DRAM)
Load/store with format unpacking on load:
- Raw formats: u8, s8, u16, s16, f16, f32, u32
- Packed formats: unorm8 (normalize to [0,1]), snorm8, rgb10a2, etc.

### Stack Operations
Per-thread stack with dedicated instructions:
- `stack_load`, `stack_store` - per-thread stack access
- Masked access patterns for divergent branches

### Shared Memory (Threadgroup)
- `threadgroup_load`, `threadgroup_store`
- ~60 KB threadgroup memory for workgroup-level data sharing
- `threadgroup_barrier` for synchronization

---

## Selection and SIMD Ops
- `icmpsel` / `fcmpsel` - conditional select (compare-and-move)
- `icmp_ballot` - collect comparison results across SIMD-group
- `simd_shuffle` - shuffle data between threads in a SIMD-group

---

## Texture Operations
Separate instruction class for texture sampling (details in full docs). Sampler state and texture descriptors passed via uniform registers.

---

## Register Cache Hints
Cache hints on operand encoding:
- `cache` - hint to retain value in register cache
- `discard` - future reads undefined; allows register reuse
- Used to balance occupancy vs. performance trade-offs

---

## Uniform Buffers vs. Competitors
Apple does **not** have fixed-function hardware for vertex attributes or uniform buffers (unlike ARM Mali, Qualcomm Adreno, etc.). This frees up die area for more ALUs and register file, at the cost of higher shader compiler complexity.

---

## Full Documentation
The complete architecture reference with all instruction encodings, bit fields, and detailed descriptions:
https://dougallj.github.io/applegpu/docs.html
