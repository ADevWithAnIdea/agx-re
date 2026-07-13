# EXP-M5-21 — M5 (G17g) GPR machine model, re-measured

**Device:** Apple M5 / T8142 / Apple10 / `AGXAcceleratorG17G`. OWN-SHADER only: compiled our own runtime MSL,
read our own `__GPU_METADATA` FlatBuffer + our own compiled bytes; occupancy correlation via the EXP-M5-13
iotrace interposer (own-process). No Apple binary disassembled. 0 GPU faults, 0 reboots.

## Headline delta — the M5 GPR file is LARGER than A18's: **126 vs 96 (+30)**
The compiler's register footprint grows with the *identical* A18 slope but **caps at 126 GPRs instead of 96**.
Spilling begins later to match. Everything else in the machine model transfers unchanged.

| property | A18 / G17P | **M5 / G17g** | evidence |
|---|---|---|---|
| **GPR footprint cap** | 96 | **126** (+30 DELTA) | metadata field 0 caps; K=96→123, K=98→126 |
| max live 32-bit regs, no spill (HW-proven) | 93 | **123** | K=96 int copy PASS, scratch=0, exact readback |
| **spill threshold** (scratch first appears) | f0=96 | **f0=126 (K=98)** | metadata field 14/41 |
| footprint formula (unspilled) | `round(1.25·K)+3` | **same** (byte-identical every K) | ladder K=8→13/16→23/48→63 |
| half packing | 2 halves/GPR | **same** (half slope 0.75) | 64 halves→50 GPRs |
| uniform file | field 31, ~8 B/uniform | **same** | 2→32, 8→80, 16→144 B |
| occupancy tier cfg `+0x00` bit23 | set ≥~12 (interpolated) | **set f0≥20, clear ≤19** (measured 19│20) | iotrace |
| base cfg `+0x00` | `0x00080000` | **`0x0`** (bit19 dropped; heavy `0x00800000`) | iotrace (== EXP-M5-06) |

## Driver guidance
A register allocator should **target ≤126 GPRs before spill on M5** (vs 96 on A18); 2 independent 16-bit halves
per GPR; spill-to-scratch mechanism identical (later onset); set compute-config `+0x00` bit23 at ~20 GPRs footprint.

## Honest open
**Physical 126 vs 128** not disambiguated: the A18 r96 memory-index hard-fault probe (RT-7) does NOT transfer —
M5 memory is split, so the `m5_load` index-reg byte+5 is inert (the index is carried by `m5_addr_gen`); a full
sweep faulted nothing. Driver-relevant number is firmly **126 (footprint cap)**; by analogy to A18 (cap=physical,
same −3 no-spill gap: 123/126 here vs 93/96 there), 126 is most likely. Follow-up needs the `m5_addr_gen` index map.

## Closes
ROADMAP-M5 §1.4 (machine model re-measured) + REVIEW-M5-OBJ1-04 m-5 (GPR model was inherited-not-measured) —
now measured with a concrete correction (96→126). Doc edits: `docs/isa/README-M5.md` §Machine model,
`docs/capability-completeness-m5.md` row 24, `docs/ROADMAP-M5.md` §1.4.

## Clean-room attestation
Own-shader compile→read-own-metadata + HW copy-correctness + own-process iotrace occupancy correlation.
No Apple binary disassembled/introspected. Every number from a measured run (`raw/measurements.txt`).
