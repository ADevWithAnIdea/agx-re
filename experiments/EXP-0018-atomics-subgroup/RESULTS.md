# EXP-0018 Results — Atomics + Subgroup/Quad ops (A18 Pro / G17P)

All findings **HW-validated** unless marked *inferred*. SIMD width = **32** (proven 3 ways).

---

## 1. Atomics

### 1a. Structure — NATIVE ops, NOT a CAS/retry loop
The EXP-0012 "CAS/retry loop" reading was a **misinterpretation**. There is **no backward jump**
(`0f 00 54`) in any atomic. What EXP-0012 saw is the compiler's **SIMD-reduction optimization** for
device atomics with a *uniform* address:

1. `simd_reduce` (byte0 `0xbf`) pre-combines the per-lane operands within the SIMD-group,
2. `0a` compare + `0f 05` mask-push **elects one lane** (`simd_is_first`),
3. that lane issues **ONE native RMW** (`67 11 54 …`), `0f 06` reconverges,
4. `simd_reduce`/`simd_shuffle` broadcast the old value back + an `iadd` rebuilds each lane's
   return value (exclusive prefix).

The atomic itself is a **single memory-family instruction** (byte0 `0x67`). Confirmed by
`da_add_idx` (distinct per-lane address → no reduction possible): it emits exactly one `0x67`
atomic op, no loop. `compare_exchange_weak` is likewise a **single** op (byte+12 `0x24`) whose
returned old value feeds a following `icmp` for the bool — again no hardware retry loop.

### 1b. Atomic RMW instruction field map (`atomic_rmw`, elected-lane device form)
`67 11 54 00 00 <addr…> 42 00 00 <OP> 00`  (14 bytes, byte0 `0x67`, byte+1 `0x11`)

| byte | field | meaning |
|---|---|---|
| +0 | opcode | `0x67` (memory family) |
| +1 | mode | `0x11` = device atomic RMW (elected-lane). `0x01` = standalone (exchange/cmpxchg/indexed). `0x02`/`0x03` bit = threadgroup |
| +4 | **base_slot** | buffer slot holding the target base pointer (same slot model as loads, EXP-0012) |
| +5..+11 | address / data regs | *inferred* (byte-diff) |
| **+12** | **operation** | **HW splice-proven** operation selector (table below) |

### 1c. Operation table (byte+12) — which ops are native
All are **native** (single RMW after the reduce optimization). Codes read from the compiler's own
`atomic_fetch_*` kernels:

| op | byte+12 | | op | byte+12 |
|---|---|---|---|---|
| add (int/uint) | `0x20` | | xor | `0x3e` |
| sub | `0x36` | | smax | `0x28` |
| and | `0x22` | | smin | `0x2a` |
| or  | `0x2c` | | umax | `0x38` |
| fadd (float, device only) | `0x26` | | umin | `0x3a` |
| exchange / store | `0x3c` | | compare-exchange | `0x24` |

**HW proof of the op field:** splicing the aggregate kernel's `67 11` byte+12 `0x20`(add)→`0x28`(max)
turned a 1024-thread aggregate from **1024** into **32** (= per-simdgroup reduced count, max-combined);
`0x20`→`0x2c`(or) → **32**. Direct proof byte+12 selects the operation. Bit hints (*inferred*):
bit4 (`0x10`) = unsigned on min/max; bit1 (`0x02`) = min vs max.

### 1d. Device vs threadgroup
Same `0x67` memory family. **Device**: byte+1 bit1 = 0, base_slot = the device buffer slot.
**Threadgroup**: byte+1 bit1 set (`0x02`/`0x03`) + base_slot `0x08` (local) — identical
address-space encoding to EXP-0012 threadgroup load/store. Threadgroup atomics HW-run correctly
(`ta_add_r`/`ta_max_r`); exact op-field position under the barrier-wrapped lowering is *inferred*.

### 1e. Address & data
Address = `buffer[base_slot]` (byte+4) + register index; per-lane **indexed** atomics (`&c[i]`)
set the index-addressing bits (byte+6/+7) and skip the SIMD reduction. Data operand and return
register live in the reg-pack tail (*inferred*). Aggregate/return semantics HW-proven:
`da_add_r` final counter = Σ inputs (528) and per-lane returns are the exact exclusive prefix.

---

## 2. Subgroup / SIMD-group ops — **SIMD width = 32**

Width proven three ways: `threads_per_simdgroup` = 32; `thread_index_in_simdgroup` runs 0..31 and
repeats in a 64-thread threadgroup; `simd_sum(1)` = 32.

### 2a. Reduce & prefix-scan — `simd_reduce` (byte0 `0xbf`/`0x3f`, **8 bytes**, byte+2 = `0x56`)
`<b0> <op> 56 <b3> <src> <b5> <shape> <dtype>`

- **byte0** bits: `[0:3]=111`, `[4:6]=11` const; **bit3 = scope** (1 = SIMD-group, 0 = quad);
  **bit7 = op-class-hi**.
- **operation = (byte0 bit7, byte+1)**: `(1,00)`=or `(0,00)`=and `(1,01)`=add(sum) `(0,01)`=xor
  `(1,02)`=max `(0,02)`=min `(0,06)`=fadd.
- **byte+7 = datatype / shape**: `0x03` int add/logic reduce · `0x07` int min/max · `0x12` float
  add · `0x0b` **exclusive** prefix-sum · `0x09` inclusive-scan (with byte+3=`0x04`, byte+6=`0x16`).
  Inclusive prefix-sum = exclusive-scan op **+** an `iadd` of the lane's own value.

HW-proven semantics (distinct per-lane input, per-lane read-back): sum, product, min, max, and, or,
xor, float-sum, inclusive & exclusive prefix-sum — all exact over 32 lanes. Op-select splice-proven:
`bf`→`3f` flips or→and; byte+1 `01`→`02` & byte+7 `03`→`07` flips sum→max; byte+7 `0b`→`03` flips
exclusive-scan→full-reduce(broadcast).

### 2b. Broadcast & shuffle — `simd_shuffle` (byte0 `0x47`/`0xc7`, **10 bytes**, byte+2 = `0x56`)
`<b0> <mode> 56 <b3> <src> <b5> <lane> 2c 04 00`

- **byte0** `0x47` = broadcast / shuffle-up; `0xc7` = shuffle-xor / down (**bit7 = direction**).
- **byte+1 = mode**: `0x04` SIMD-group · `0x00` quad · `0x06` rotate.
- **byte+6 = lane index / xor mask, encoded (value << 1)** (HW: `broadcast(v,5)`→`0x0a`,
  quad `broadcast(v,2)`→`0x04`, `shuffle_xor(v,1)`→`0x02`).

HW-proven: `simd_broadcast(0/5)`, `simd_broadcast_first`, `simd_shuffle_xor`, dynamic
`simd_shuffle(v,lane)`, `simd_shuffle_up/down`, `simd_shuffle_rotate_up/down` — all read back exactly.
`shuffle_up` at lane 0 returns the lane's own value (Metal fill behaviour).

### 2c. Ballot / vote / elect — `simd_ballot` (byte0 `0x17`, **10 bytes**)
Produces the 32-bit active-lane predicate mask. HW: `simd_ballot(v>0)` = `0xFFFFFFFF` (all active),
`0x55555555` for alternating predicate; `simd_active_threads_mask` = `0xFFFFFFFF`; `simd_all`,
`simd_any`, `simd_is_first` (lane-0 only) all correct.

---

## 3. Quad ops (2×2, execution width 4)

**Same instruction groups as the subgroup ops, at width 4** (contiguous lanes {0-3},{4-7},…):
- **reduce**: `simd_reduce` with **scope bit3 = 0** → byte0 `0xb7`/`0x37` (e.g. `quad_sum` `b7 01 56
  … 14 03`, `quad_min` `37 02 56 … 14 07`). HW-proven: sum/max/min/and/inclusive-prefix over each quad.
- **shuffle/broadcast**: `simd_shuffle` with **byte+1 = `0x00`** (quad mode). HW-proven:
  `quad_broadcast(0/2)`, `quad_shuffle_xor`, dynamic `quad_shuffle`, `quad_shuffle_up/down`.
- `thread_index_in_quadgroup` = lane mod 4 (HW).

---

## 4. Capability notes (vs Metal / Vulkan)

- **SIMD width = 32** (Apple9). Full permute network present: broadcast(±first), shuffle
  (xor/up/down/**rotate up/down**), reduce (sum/product/min/max/and/or/xor), inclusive & exclusive
  prefix-scan, ballot/vote/elect/active-mask. **Prefix-scan is native** (a single `simd_reduce` op
  with byte+7 shape `0x0b`/`0x09`), not a shuffle-tree lowering — inclusive = exclusive-scan + one add.
- **Float atomics: only `fetch_add` exists.** Float atomic **min/max are NOT exposed by MSL** on this
  toolchain (`_valid_fetch_min_type<device float*>` unsatisfied) — flag for software emulation in Vulkan.
- **64-bit atomics: min/max only.** `atomic_fetch_add` on `atomic_ulong` is **rejected by MSL**
  (`_valid_fetch_add_type<device ulong*>` unsatisfied); only the void 64-bit `atomic_min/max` form exists.
- **Atomics are native single RMW ops** (one `0x67` instruction with an op selector at byte+12),
  **not** CAS/retry loops. Device atomics to a uniform address get a compiler SIMD-reduce optimization
  (reduce → one lane RMW → prefix broadcast) that cuts 32 memory transactions to 1 per simdgroup.
- **Subgroup & quad ops share the same two opcode groups** (`simd_reduce`, `simd_shuffle`); quad is
  just scope-bit=0 / mode=quad. Nothing richer than Metal's surface was observed beyond the rotate
  and active-mask variants (which Metal does expose).

---

## 5. Round-trip status / faults
`tools/agx-isa/roundtrip_test.py`: **ALL PASS** (34 descriptors, 31 HW-validated; 5 new this exp).
No GPU faults or reboots during EXP-0018 — every dispatch returned `STATUS OK`; illegal splices
were not exercised (all splices were valid alternate encodings). No `macvdmtool reboot` needed.

**Recommended next:** decode the shuffle/reduce register-operand bits; pin the threadgroup-atomic
op-field position; map the `0x2c`/`0x24`/`0x1b` elect-lane scaffolding; probe `simd_shuffle_and_fill`
and the 64-bit atomic min/max encoding.
