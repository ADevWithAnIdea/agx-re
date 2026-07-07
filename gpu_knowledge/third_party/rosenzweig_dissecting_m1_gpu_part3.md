# Dissecting the Apple M1 GPU, Part III

**Source:** https://alyssarosenzweig.ca/blog/asahi-gpu-part-3.html  
**Author:** Alyssa Rosenzweig  
**Also mirrored at:** https://rosenzweig.io/blog/asahi-gpu-part-3.html

---

## Summary

Part III focuses on the AGX2 ISA characteristics, register file/occupancy model, and compiler design methodology informed by the hardware architecture.

---

## Register File and Thread Occupancy

**256 half-word registers per thread.**

Occupancy trade-off (from analysis of Metal's `maxTotalThreadsPerThreadgroup`):
- Up to ~104 registers: occupancy unaffected
- Beyond ~104 registers: thread count decreases linearly in **64-thread increments**
- Total register file capacity: approximately **208 KiB per threadgroup**
- Across **24 parallel threadgroups**: ~4.875 MiB total register file

**No register spilling until exceeding 256 registers.**

This is unusual compared to competitors - Apple provides a very large register file before spilling is needed, trading die area for reduced memory traffic.

---

## ISA Characteristics (AGX2)

- **Scalar arithmetic** with vectorized I/O
- **16-bit types** natively supported
- **Free conversions** between 16/32-bit values (no instruction cost)
- **Free floating-point modifiers:** absolute value, negate, saturate on any source/destination

### Superscalar Execution
No explicit register spilling until >256 registers are used, and the hardware executes multiple operations per cycle from different pipelines.

---

## Architecture Differences from Competitors

Apple **omits fixed-function hardware** for:
- Vertex attribute fetch (competitors: Mali, Adreno have dedicated hardware)
- Uniform buffers (competitors have dedicated hardware paths)

Design choice rationale:
- Allows "more arithmetic logic units (or register file!) onto the chip"
- Shifts compilation overhead to shader code generation rather than dedicated silicon
- Reduces die area for fixed-function blocks; increases programmable compute

---

## Compiler Design Methodology

Shader compiler pipeline (architecture-aware):

```
NIR translation
  → SSA intermediate representation
  → Instruction combining optimization
  → Register pressure-conscious scheduling
  → Register allocation
  → Post-allocation scheduling (maximize ILP without GPU-specific leakage)
  → Binary packing
```

**Key design decisions mirroring hardware:**
1. Scalar-only sources prevent compiler complexity (no vector packing decisions)
2. SSA form enables register pressure estimation
3. Post-allocation scheduling maximizes instruction-level parallelism

---

## Notes on MacOS-Specific Challenges

"The IOGPU interface with the kernel...is made aware of graphics state like surface dimensions and even details about mipmapping," requiring substantial reverse-engineering work for native driver support.

The kernel interface is unusually stateful compared to typical GPU kernel interfaces, which complicates writing an independent open-source driver.
