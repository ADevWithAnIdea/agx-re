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
  evidence distinguishes r0..r15, r0..r23, r0..r63, and r0..r95 roles.
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

Primary evidence: EXP-0020, EXP-0174, EXP-0220 through EXP-0225, and EXP-0230.

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
| `falu3.8B` A/B/C | 32 | r0..r15 | r16..r23 gave mixed results and no emitter rule; r24..r95 unknown | EXP-0224 |
| `falu3.8B` destination | 32 | r0..r15 | no direct r16+ recipe is proved | EXP-0224 |
| `iadd2.10B` first/second source | 32 | r0..r23 tested | r24..r95 unknown | EXP-0222 |
| `iadd2.10B` destination | 32 | r0..r23 tested | r24..r95 unknown | EXP-0222 |
| `imad.12B` X/Y source | 32 | r0..r23 tested | r24..r95 unknown | EXP-0225 |
| `imad.12B` destination | 32 | r0..r23 tested | r24..r95 unknown | EXP-0225 |
| `isel10` compare A/B and true/false source | 32 | r0..r23 tested | r24..r95 unknown | EXP-0223 |
| `isel10` destination | 32 | r0..r15 tested | r16..r95 unknown | EXP-0223 |
| `device_load.14B` destination | 32 | r0..r95 | first out-of-file destination behavior is not yet cleanly closed for this form | EXP-0221, EXP-0230 |
| `device_store.14B` data source, even `extmode` | 32 | r0..r95 | half index 192 wraps to r0; other upper codes include aliases and faults and need a complete accepted-set model | EXP-0221 |
| `device_load/store.14B` index source | 32 | r0..r95 | low seven-bit values 96..127 fault; encoded bit 7 is ignored and mirrors the low seven bits | EXP-0221 |
| `fspecial.10B` destination | 32 | r1..r14 tested | r0 and r15..r95 not directly value-proved; descriptor values for r96+ fault/hang | EXP-0161 |
| `fspecial.10B` source | 32 | r1,r2,r3,r5,r7,r9,r14 tested | other physical registers unknown; field geometry alone is not promotion evidence | EXP-0161 |

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
| any set involving r64..r95 | any different GPR | none yet | — | **open** |
| r0..r15 result | r16..r95 | none yet | — | **open** |

The memory instructions separately prove that values can be stored from and loaded into every
physical GPR. They do **not yet** prove a lifecycle-correct GPR→memory→different-GPR transfer edge:
that exact sequence, scratch address space, visibility point, retain/release behavior, and size/
alignment bounds still need a formal test. Do not silently upgrade two independently valid
instructions into a tested transfer path.

## 4. State transitions proved across anchor families

For the tested 32-bit ALU recipes (`falu2`, `iadd2`, `imad`, `isel`, and `falu3`):

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
```

The last block is not yet a complete state machine. Slot assignment/reuse and multi-pending
behavior are Step 3 work.

## 5. Exact Step 2 blockers exposed by this artifact

1. **Top-tier transfer:** find and fully validate low→high, high→low, and high→high copies involving
   r64..r95, or prove that only a particular memory-mediated path exists. The first experiment
   should test `device_store(rS)` followed by `device_load(rD)` with S/D crossing all three tiers,
   complete-state observation, retained/released variants, and exact first-invalid scratch bounds.
2. **Dense role reach:** finish r0..r95 matrices for `iadd2`, `imad`, `isel`, `falu3`, `fspecial`,
   logic, conversion, half, compare, and every alternate/compressed form. Mixed results are not a
   range.
3. **Low-tier exhaustion:** execute the maximum simultaneously live compact operands/results and
   the first over-capacity case while high GPRs remain unused.
4. **Pairs and partial overlap:** close 64-bit pair alignment, odd-pair behavior, overlapping pair
   source/destination cases, and every half-write/half-release alias.
5. **Scratch/spill:** establish the hardware-visible address space, byte capacity, alignment,
   allocation unit, maximum valid access, first invalid access, wrap/fault behavior, and lifetime.
6. **Lifecycle cross-product:** repeat retain, release, read-after-release, redefine-after-release,
   and fan-in/fan-out at tier boundaries and with pending memory/texture producers.
7. **Schema coverage:** add a register-effect row for every discovered instruction form; no family
   may inherit another form's reach without direct equivalence evidence.

These are hardware-discovery questions. Choosing a compiler ABI, allocator, spill policy, or IR is
deliberately outside this document.
