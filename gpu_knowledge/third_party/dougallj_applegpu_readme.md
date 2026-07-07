# dougallj/applegpu - Apple G13 GPU Architecture Docs and Tools

**Source:** https://github.com/dougallj/applegpu  
**Documentation:** https://dougallj.github.io/applegpu/docs.html  
**License:** BSD-3-Clause  
**Author:** Dougall Johnson  
**Language:** Python (39.8%), HTML (53.8%), C++ (3.8%)

---

## Project Overview

Reverse engineering work on the Apple G13 GPU architecture as used in the M1 chip. The project includes:

- **Disassembler** - converts binary GPU code into readable assembly instructions
- **Assembler** - generates GPU bytecode from assembly syntax, supporting instruction creation for testing
- **Emulator** - instruction execution simulation via a CoreState object
- **Hardware Tests** - runs actual GPU code on Apple Silicon by injecting custom shaders into Metal binary archives, then compares emulated vs real hardware execution

## Methodology

The project employs a comparative testing approach:
1. Inject custom shaders into Metal binary archives (overwriting shader code in existing `.metallib` files)
2. Execute on actual GPU hardware via Metal API
3. Execute on emulator
4. Compare state afterwards to validate correctness

This dual-execution strategy (real hardware + emulator) enables rapid identification of implementation errors. Tests run on-device (Apple Silicon required for hardware tests).

The documentation is generated from instruction descriptions in `applegpu.py` using `genhtml.py`.

---

## G13 Architecture Summary

### Thread Model
- 32 threads per SIMD-group (matching Metal's terminology)
- 128 general-purpose registers (r0-r127) per thread, 32-bit storage each
- Register access modes: full 32-bit, low 16-bits (suffix `l`), high 16-bits (suffix `h`)
- Register pairs for 64-bit operations
- Memory instructions can use up to four contiguous registers

### Special Registers
- **r0l** - tracks the execution mask stack (divergence control)
- **r1** - link register (return address)
- **u0-u255** - uniform registers (thread-invariant values like buffer addresses)

### Execution Control & Divergence
- 32-bit execution mask: one bit per thread (1=active, 0=inactive)
- r0l maintains a stack depth counter for re-enabling inactive threads
- Instructions: `pop_exec`, `if_*cmp`, `else_*cmp`, `while_*cmp`
- Conditional branches: `jmp_exec_any`, `jmp_exec_none`

### Instruction Encoding
Variable-length instructions (2-12 bytes). The L-bit indicates instruction truncation (omitting unused bytes to conserve code space).

### Instruction Categories

**Move:**
- `mov` (16/32-bit immediate)
- `get_sr` (special register reads)

**Arithmetic:**
- `iadd`, `imadd` (with saturation support)
- `convert`

**Bitfield/Bit Manipulation:**
- `bfi`, `bfeil`, `extr`, `shlhi`, `shrhi`
- `bitop`, `bitrev`, `popcount`, `ffs`

**Floating-Point:**
- `fmadd`, `fadd`, `fmul`
- `floor`, `ceil`, `trunc`, `rint`
- `rcp`, `rsqrt`, `log2`, `exp2`
- Free modifiers: absolute value, negate, saturate (no cost)
- Free conversion between 16-bit and 32-bit on sources and destinations

**Flow Control:**
- `ret`, `stop`, `call`, `jmp_*`

**Execution Mask Stack:**
- `pop_exec`, `if_icmp`, `if_fcmp`, `while_*`, `else_*`

**Selection:**
- `icmpsel`, `fcmpsel`

**SIMD Operations:**
- `icmp_ballot`, `simd_shuffle`

**Memory:**
- `device_load`, `device_store` (with optional unpacking: unorm8, snorm8, fp16, fp32, rgb10a2, etc.)
- `stack_load`, `stack_store`
- Texture operations
- `threadgroup_load`, `threadgroup_store` (shared/cooperative memory)

**Synchronization:**
- `threadgroup_barrier`

### Register Cache Hints
Cache hints (`cache`, `discard`) on operands influence register file behavior:
- `discard` - makes future reads undefined, frees register for reuse
- Balances occupancy against performance

---

## Key Resources

- **GitHub repo:** https://github.com/dougallj/applegpu
- **Architecture docs:** https://dougallj.github.io/applegpu/docs.html
- **Also mirrored at:** https://github.com/geohot/applegpu (George Hotz fork)
