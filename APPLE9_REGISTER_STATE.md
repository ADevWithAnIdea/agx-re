# Apple9 G17P register state and access classes

Status: **working Step 2 artifact; not complete**. This file records only direct G17P hardware
results unless a row explicitly says family evidence. It is intentionally independent of NIR,
compiler policy, and register-allocation design.

Machine-readable source: `docs/isa/register-effects.json`. The generated 96-column view is
`docs/isa/register-access-matrix.csv`.

## 1. Architectural state proved so far

- The physical per-thread GPR file contains **96 distinct 32-bit registers, r0..r95**. This is a
  capacity result, not a promise that every instruction can address every register.
- A 32-bit GPR is observably composed of two independently addressable 16-bit halves. Instructions
  may use a half-register descriptor and may preserve, release, or overwrite only one half.
- The 96 GPRs form several **instruction-role-specific access classes**. At minimum, current G17P
  evidence distinguishes r0..r15, r0..r31, r0..r63, and r0..r95 roles.
- An encoding's apparent register-field width does not establish its direct set. For example,
  `n3_mov` accepts all 256 source/half bytes but source numbers 64..127 alias modulo 64.
- Source release occurs after the read. Where destination aliases a released source, the tested
  ALU families publish the destination after release, so the new destination wins.
- A released 32-bit ALU source subsequently reads as zero. `n3_mov` release is half-granular: it
  clears only the selected source half after that half was read.
- A `device_load` result has a pending/publication state. Some adjacent consumers require a
  consumer-side acceptance/forwarding control; later ordinary reads see the landed GPR. Exact
  scoreboard capacity and slot lifetime belong to Step 3 and are not claimed here.
- `device_store` releases its index register. Reusing that register as a second store index without
  redefining it addresses with zero. A just-loaded index can be stale until an intervening
  instruction permits publication.
- `device_load` retains its index register. EXP-0231 distinguished this from release with a
  nonzero index and proved an adjacent device-store/device-load transfer across every GPR tier.

Primary evidence: EXP-0020, EXP-0174, EXP-0220 through EXP-0226, and EXP-0230 through EXP-0238.

## 2. Access classes established by direct G17P experiments

`Direct` below means the exact physical register was independently distinguishable and the role
read or wrote it as predicted. `Unaddressable` means the form cannot name that physical register;
the observed alias/failure is stated. `Tested` is not extrapolated to the rest of a field.

| instruction form and role | width | direct set | known outside behavior | evidence |
|---|---:|---|---|---|
| `n3_mov.compact4` source | 16 | r0..r63, both halves | physical r64..r95 unaddressable; S=64..127 reads `r[S mod 64]`, all codes execute | EXP-0230 |
| `n3_mov.compact4` destination | 16 | r0..r15, both halves | r16..r95 unaddressable by the four-bit destination nibble | EXP-0174 |
| `falu2.6B` source A | 32 | r0..r63 | physical r64..r95 unaddressable in this form; high descriptor space aliases rather than selecting them | EXP-0220 |
| `falu2.6B` source B, GPR class | 32 | r0..r63 | same compact-form bound | EXP-0220 |
| `falu2.6B` destination | 32 | r0..r15 | r16..r95 unaddressable by this form | EXP-0220 |
| `falu3.8B` A/B/C, canonical retained FP32 FMA, materialized GPR | 32 | r0..r63 | physical r64..r95 unaddressable; encoded R=64..127 reads `r[R & 63]`; unresolved pending-load inputs are a separate class | EXP-0224, EXP-0236 |
| `falu3.8B` destination, canonical retained FP32 FMA | 32 | r0..r15 | r16..r95 unaddressable by the four-bit destination nibble | EXP-0224, EXP-0236 |
| `iadd2.10B` first source, canonical register form | 32 | r0..r31 | r32..r95 cannot be named by the seven-bit `reg<<2` selector; alternate extension forms remain unknown | EXP-0222, EXP-0232 |
| `iadd2.10B` second source, canonical register form | 32 | r0..r63 | r64..r95 cannot be named by the eight-bit `reg<<2` selector; alternate extension forms remain unknown | EXP-0222, EXP-0232 |
| `iadd2.10B` destination, G17P | 32 | r0..r95 | r96 is the first invalid destination and faults; r127 also faults rather than wrapping. The G17P r95 result differs from inherited M4/G16G evidence | EXP-0222, EXP-0232 |
| `imad.12B` X source, canonical low-32 form | 32 | r0..r63 | r64..r95 cannot be named by the eight-bit `reg<<2` selector; alternate forms remain unknown | EXP-0225, EXP-0233 |
| `imad.12B` Y source, canonical low-32 form | 32 | r0..r31 | r32..r95 cannot be named by the eight-bit `reg<<3` selector; alternate forms remain unknown | EXP-0225, EXP-0233 |
| `imad.12B` destination, canonical low-32 G17P form | 32 | r0..r95 | r96 is the first invalid destination and faults; r127 also faults rather than wrapping | EXP-0225, EXP-0233 |
| `isel10` compare A/B and true/false source, canonical 10B form | 32 | r0..r63 | physical r64..r95 unaddressable; encoded R=64..127 reads `r[R & 63]`, and all canonical source codes execute | EXP-0223, EXP-0234 |
| `isel10` destination, canonical 10B form | 32 | r0..r15 | r16..r95 unaddressable by the four-bit destination nibble | EXP-0223, EXP-0234 |
| `ilogic.10B` semantic A/B source, canonical XOR form | 32 | r0..r63 | encoded R=64..127 reads and releases `r[R & 63]`; physical r64..r95 is neither read nor released | EXP-0226, EXP-0235 |
| `ilogic.10B` destination, canonical XOR form | 32 | r0..r15 | r16..r95 unaddressable by the four-bit destination nibble | EXP-0226, EXP-0235 |
| `device_load.14B` destination | 32 | r0..r95 | first out-of-file destination behavior is not yet cleanly closed for this form | EXP-0221, EXP-0230 |
| `device_store.14B` data source, even `extmode` | 32 | r0..r95 | half index 192 wraps to r0; other upper codes include aliases and faults and need a complete accepted-set model | EXP-0221 |
| `device_load/store.14B` index source | 32 | r0..r95 | low seven-bit values 96..127 fault; encoded bit 7 is ignored and mirrors the low seven bits | EXP-0221 |
| `fspecial.10B` destination, canonical FP32 direct-round form | 32 | r0..r95 | byte values 0..191 select `r[v >> 1]`; r96 is first invalid and the upper descriptor region faults/hangs | EXP-0161, EXP-0237 |
| `fspecial.10B` source, canonical FP32 direct-round form, materialized GPR | 32 | r0..r63 | byte values 0..255 select and release `r[v >> 2]`; the field has no representation for physical r64..r95 | EXP-0161, EXP-0237 |
| `cvt_f2i.10B` destination, canonical FP32-to-signed-I32 form | 32 | r0..r95 | byte values 0..191 select `r[v >> 1]`; r96 is first invalid and 192..255 fault/hang by the complete EXP-0168 sweep | EXP-0168, EXP-0238 |
| `cvt_f2i.10B` source, canonical FP32-to-signed-I32 form, materialized GPR | 32 | r0..r63 | byte values 0..255 select and release `r[v >> 2]`; the field has no representation for physical r64..r95 | EXP-0238 |

The CSV contains one cell per physical r0..r95 for each row. `?` is deliberately present wherever
the experiment did not establish the answer; Step 2 cannot be checked while any discovered role
still has such cells.

## 3. Transfer graph proved so far

The transfer graph is stricter than an addressability inference: each edge must be an executed
sequence with correct complete-state and lifecycle behavior.

| source set | destination set | sequence | granularity | status |
|---|---|---|---:|---|
| r0..r63 | r0..r15 | two retained `n3_mov` half copies | 32 | proved by EXP-0174 plus full source-reach closure in EXP-0230 |
| r0..r63 | r0..r15 | one `n3_mov` | 16 | proved |
| r0..r95 | r0..r95 | `device_store` to bound scratch, then `device_load` | 32 | proved as a tier/boundary cross-product by EXP-0231; dense endpoint reach comes from EXP-0221/0230 |
| any set involving r64..r95 | any different GPR | direct GPR-only instruction | — | **open; memory fallback above is proved** |

EXP-0231 tested the previously missing composition directly. An adjacent store/load at scratch byte
3200 was exact at gaps 0, 1, 4, and 16 in every low/middle/high direction. The store released its
nonzero index, the load retained its nonzero index, and the source remained live. This proves the
transfer edge, not the complete scratch resource: capacity, alignment envelope, concurrent-lane
addressing, and first-invalid behavior remain open.

## 4. State transitions proved across anchor families

For the tested 32-bit ALU recipes (`falu2`, `iadd2`, `imad`, `isel`, `ilogic`, `falu3`, the
canonical materialized-source `fspecial` direct-round form, and canonical materialized-source
`cvt_f2i`):

```text
read retained source     : value is consumed; source remains unchanged
read released source     : value is consumed; source becomes 0 after the read
released source == dst   : result publication follows release; dst contains the new result
retain fan-out           : later consumers see the retained value
```

For `n3_mov`:

```text
dst.half(hd) = src.half(hs)
other destination half is preserved
release=0: source half is preserved
release=1: selected source half becomes 0 after the read
```

For memory:

```text
device_load              : creates a pending result, then publishes it to the named GPR
adjacent accepting use   : may consume/forward the pending value with a form-specific control
non-accepting adjacent use: may consume stale state or drop the load, depending on consumer
device_store index read  : consumes then releases the index GPR
device_load index read   : consumes and retains the index GPR
device_store -> load     : same-address device scratch is visible with zero intervening ops
```

The last block is not yet a complete state machine. Slot assignment/reuse and multi-pending
behavior are Step 3 work.

## 5. Exact Step 2 blockers exposed by this artifact

1. **Direct top-tier transfer capability:** the memory-mediated low↔mid↔high fallback is proved by
   EXP-0231. Continue looking for a direct GPR-only move involving r64..r95 so the hardware
   capability and performance alternative are known; do not treat the fallback as proof none exists.
2. **Dense role reach:** the canonical b32 `iadd2` register form, canonical low-32 `imad`, canonical
   retained FP32 `falu3`, canonical `isel10`, canonical XOR `ilogic`, and canonical FP32-to-signed-
   I32 `cvt_f2i` forms are closed. Finish r0..r95 matrices for alternate `fspecial` and conversion
   forms, half, compare, other logic forms, and every alternate/compressed form. Mixed results are
   not a range.
3. **Low-tier exhaustion:** execute the maximum simultaneously live compact operands/results and
   the first over-capacity case while high GPRs remain unused.
4. **Pairs and partial overlap:** close 64-bit pair alignment, odd-pair behavior, overlapping pair
   source/destination cases, and every half-write/half-release alias.
5. **Scratch/spill bounds:** EXP-0231 proves one device-memory scratch word at byte 3200 and an
   adjacent 32-bit round trip. Establish byte capacity, alignment, allocation unit, maximum valid
   access, first invalid access, wrap/fault behavior, per-lane addressing, and lifetime.
6. **Lifecycle cross-product:** repeat retain, release, read-after-release, redefine-after-release,
   and fan-in/fan-out at tier boundaries and with pending memory/texture producers.
7. **Schema coverage:** add a register-effect row for every discovered instruction form; no family
   may inherit another form's reach without direct equivalence evidence.

These are hardware-discovery questions. Choosing a compiler ABI, allocator, spill policy, or IR is
deliberately outside this document.
