# EXP-O2D RESULTS — compute/fragment ISA tail

Device: Apple A18 Pro / G17P, macOS 26.6, Metal 4 / Apple9. `✅` = HW-validated (spliced/ran or
end-to-end observed); `◑` = byte-diff-inferred; `⛔` = Metal-rejected (negative result).
Machine-readable encodings: `new_descriptors.json`. Evidence: `raw/`.

---

## 1. Atomic memory-ordering / fence bits

**Ordering is NOT on the `0x67` atomic op — it lives in a separate `0x07` fence, and only two orders exist.**

- ⛔ `atomic_fetch_*_explicit` accepts **only `memory_order_relaxed`**; `seq_cst`/`acquire`/`release`/`acq_rel`
  are **rejected by MSL** ("no matching function"). So the atomic RMW op carries **no ordering field** — it is
  always relaxed. `atomic_thread_fence` additionally accepts `seq_cst` (but still rejects acquire/release/acq_rel).
- ✅/◑ **`atomic_thread_fence(flags, order, scope)` = the `0x07` fence family** (same as EXP-0025 barrier /
  EXP-0029 pixel_order). Diffed against a no-fence baseline (`fencediff.py`, device-memory kernel):
  - **`memory_order_relaxed` → NO fence emitted; `memory_order_seq_cst` → fence emitted.** Ordering = fence *presence*.
  - **`thread_scope_thread`/`_simdgroup`/`_threadgroup` → no device fence; `thread_scope_device` (default) → fence.** Scope *gates* emission.
  - **`mem_flags::mem_device`, seq_cst, device scope → `07 04 54 84 0a 00`** (6 B). byte+3 = **0x84** (device-memory
    fence; the threadgroup_barrier device value is 0x85 — the `0x01` bit is the *added execution barrier* a fence lacks),
    byte+4 = **0x0a** (device memory-class flag).
  - **`mem_flags::mem_texture` → a pair `07 04 54 50 06 00` (acquire) + `07 04 54 d0 06 00` (release)**. byte+4 = **0x06**
    (texture/tile fence flag, = pixel_order), byte+3 bit7 = acquire(0x50)/release(0xd0).
  - `mem_flags::mem_threadgroup` alone (no barrier) → no distinct op (relaxed==seq_cst==tg-scope byte-identical);
    cross-lane threadgroup visibility still needs the **execution barrier** (EXP-0025 `threadgroup_barrier` byte+3=0x61).
  - MSL requires the flag be qualified `mem_flags::mem_device` (bare `mem_device` is undeclared here).

So: **RMW op = ordering-free (always relaxed). Ordering/scope = the `0x07` fence's presence + byte+3 (scope/target)/byte+4 (memory class).**

---

## 2. 64-bit atomic min/max — ⛔ NOT EXPOSED BY MSL

- ⛔ **Every** 64-bit device atomic is rejected: `atomic<ulong>`/`atomic<long>`/`atomic<uint64_t>` with
  add / min / max / and / or / xor / exchange / **load** all fail "no matching function" — under every spelling,
  at the newest MSL language version, tested in isolation (`raw/probe64.txt`). 32-bit `atomic<uint>` works normally.
- **Consequence:** there is **no reachable 64-bit atomic instruction**, so **no width field to decode** from the MSL
  path. The task's premise ("MSL allows `atomic<ulong>` min/max") does **not** hold on this A18 Pro / macOS 26.6.
  **Vulkan `VK_KHR_shader_atomic_int64` (incl. 64-bit min/max) must be emulated** (or routed outside MSL). This
  *confirms* the hypotheses-doc note (64-bit atomic add/min/max not MSL-exposed → Vulkan emulates).
- (32-bit atomic reference, for completeness: uniform-address RMW = `0x67` byte+1=0x11 elected-lane, op at byte+12;
  exchange/cmpxchg = byte+1=0x01.)

---

## 3. bfloat general ALU — ✅ distinct group `0x11` (NOT fp32-lowered, NOT the `0x10` fp16 group)

- ✅ **`bfloat` add/mul/fma are a single native op in byte0 `0x11`** — the bfloat sibling of the `0x10` native-fp16
  ALU group, **reusing the same opsel byte+2** (`0x1c` add / `0x1d` mul / `0x1e` fma) as the `0x10`/`0x09` float groups.
  - `bf_add = 11 02 1c 02 09 00 c0 81` (8 B); `bf_mul = 11 02 1d …`; `bf_fma = 11 02 1e … c0 81` (10 B);
    `bfloat2` packs 2 lanes as byte+1=`0x04`; scalar bfloat byte+1=`0x02`.
  - **HW-VALIDATED:** splicing opsel `0x1c → 0x1d` (at `_agc.main@0x22`) turned `bfloat(1.0)+bfloat(2.0)=3.0`
    (bits `0x4040`) into `bfloat(1.0)*bfloat(2.0)=2.0` (bits `0x4000`) — `raw/validation.txt`.
  - **Not lowered to fp32:** a single `0x11` op does the add (no widen-add-narrow). **Not the `0x10` group:** byte0 differs.
    bfloat carries fp32 range (bf16 = top 16 bits of fp32) ⇒ `bfloat→float` is a free `0x03` widen; `float→bfloat` is a
    `0x11` byte+1=`0x03` rounding convert. Transcendentals go through the fp32 SFU (`bf_rsqrt` = `0xaf` + convert).
- **Length-rule fix (load-bearing):** the current DB lengths ALL byte0 `0x11` as 6 B (from `cvt_f2h`), which
  **desyncs every bfloat kernel**. Corrected rule in `new_descriptors.json` (`0x11`: 6 B convert byte+1=0x03; 8/10 B
  bfloat ALU byte+1∈{0x02,0x04}).

---

## 4. Subgroup tail op-selects

- ✅ **`simd_product` (FLOAT) = the `0xbf` reduce op, byte+1=`0x06`, byte0 bit7=1** (vs `simd_sum`/fadd bit7=0),
  dtype byte+7=`0x12`. **HW-VALIDATED:** splicing byte0 `0xbf → 0x3f` (bit7 clear) flipped a 32-lane product (1.0)
  into a sum (32.0) — `raw/validation.txt`. Full op table = (byte0 bit7, byte+1): `0x00`{and,or} `0x01`{xor,add}
  `0x05`{-,fmin} `0x06`{fadd/sum, **fmul/product**} `0x07`{-,fmax}.
- ✅ **`simd_prefix_exclusive/inclusive_product` (FLOAT) = native `0xbf` scan**: exclusive shape byte+7=`0x32`
  (float; int exclusive is `0x0b`); inclusive = exclusive-scan + a float mul of the lane's own value.
- ⛔/◑ **INTEGER `simd_product` / prefix-product have NO native op** — they lower to a log2(32)-step
  `shuffle(0x47)`+`imul(0x9f)` **tree** (our uint `red_prod`/`pre_*_prod` are large unrolled trees with **zero** `0xbf`
  ops). The reduce unit has a float-mul mode but no int-mul mode.
- ◑ **`simd_shuffle_and_fill_up/down` = `0x47`/`0xc7`, byte+1=`0x06`** (the mode previously labelled "rotate");
  the **fill data is a separate operand** (a preceding `0x67` load). The **modulo/rotate** variant
  `…_and_fill_*(v, fill, delta, modulo)` is the same op with byte+6 `0x4a→0x42` + a tail byte `0x20→0x30` (the modulo).
  byte0 bit7 = direction (fill_up `0x47` / fill_down `0xc7`).
- ◑ **`simd_is_helper_thread()` (fragment)** lowers to a `get_sr`-family read of a **new SR byte1=`0x84`** (helper/active-lane
  flag) `04 84 11 06` + a compare (byte-diff of `f_helper` vs `f_plain`; not spliced).
- ✅ (disambiguation) float `simd_sum` byte0=`0x3f`, `simd_min` byte+1=`0x05`, `simd_max` byte+1=`0x07`, `simd_and`
  (`0x3f`,0x00) / `simd_or` (`0xbf`,0x00) / `simd_xor` (`0x3f`,0x01) — see `raw/mains.txt`.

---

## 5. Tile shader / explicit imageblock

### 5a. Explicit `imageblock<T>` write + slice addressing — ✅ HW-validated
- Explicit `imageblock<T, imageblock_layout_explicit>` is **rejected** ("undefined template"); the working form is
  **`imageblock<GB>`** (implicit layout, `[[color(n)]]`-tagged members). It **compiles as a library** but fails
  *compute*-pipeline creation ("unlowered `air.load.implicit_imageblock`") — it needs a **tile render pipeline**.
- **imageblock write = `0xe7` store / read = `0x67` load, fragment/tile variants byte+1 ∈ {`0x06`, `0x16`, `0x0e`}**
  (`0x16` = `0x06|0x10`, the `0x10` bit marks the first access after a `0x87` tile-setup; `0x0e` = the EXP-0029
  programmable-blend `tile_read`). This generalises EXP-0029's `frag_color_store`/`tile_read`.
- **Slice addressing = byte+5 = (field byte-offset within the imageblock >> 1).** HW-proven with a 3-field imageblock
  `GB{half4 albedo@0, half4 normal@8, float depthv@16}`: the three stores carry byte+5 = `0x00`/`0x04`/`0x08`
  (= 0,8,16 >>1). **byte+7 = slice format** (`0x0e` half4, `0x22` float). This **differs from simple MRT**, where
  `frag_color_store` byte+5 = *render-target index* (`rt<<1`): explicit imageblocks address by **byte-offset**,
  MRT by **RT index**. `img.write(v)` writes the whole struct (one `0xe7` per field) — no auto single-slice isolation.
- ✅ **End-to-end HW:** `iotile` draws X=(0.2,0.4,0.6), then a tile kernel overwrites the imageblock with
  Y=(0.9,0.1,0.4,1.0); readback = `3b33 2e66 3666 3c00` = exactly Y (`raw/validation.txt`).

### 5b. Tile-shader (`dispatchThreadsPerTile`) submission — ✅ mid-render, no separate submit (iotrace)
- **The tile dispatch is embedded in the render-pass control stream — NOT a separate compute submission.**
  draw-only vs draw+`dispatchThreadsPerTile` gave a **byte-identical IOKit call sequence (58 calls, 37 BOs, same
  selectors)** — zero extra ioctl / allocation / command buffer.
- The tile-dispatch record is appended into the render (3D/fragment) control stream: BO `gpu_va 0x58000` (fragment
  control stream) gains the tile-dispatch state record (tile-mem reservation `0x1800`, the tile kernel's USC/pipeline
  words); BO `0x18000` (tiler/USC heap) gains the tile shader's binding; the imageblock output BO `0x10000018000`
  shows the X→Y write. Raw deltas in `raw/tile_cmdstream_diff.txt`.
- Answer to "a mid-render compute record?": **yes** — a compute-style kernel over the tile, recorded **inline in the
  render submission** (bound with `setRenderPipelineState:` + `dispatchThreadsPerTile:` on the render encoder), not a
  distinct compute encoder.

---

## HW-validated vs inferred (summary)

| Finding | Status |
|---|---|
| RMW ops accept only `memory_order_relaxed` (seq_cst/acq/rel rejected) | ✅ compile-probe |
| Ordering = `0x07` fence presence; scope gates it; device fence `07 04 54 84 0a`; texture `…50/d0 06` | ◑ byte-diff (grounded in HW-validated EXP-0025/0029 `0x07` family) |
| 64-bit atomics entirely absent from MSL | ✅ compile-probe (definitive) |
| bfloat ALU = `0x11` group, opsel add↔mul | ✅ splice-validated |
| `0x11` length rule fix (6 B convert vs 8/10 B bfloat) | ✅ (from our extracted lengths) |
| float `simd_product`/scan op-select (`0xbf` byte+1=0x06 bit7) | ✅ splice-validated (product↔sum) |
| int product/prefix = shuffle-tree (no native op) | ✅ opcode-census of our kernels |
| `simd_shuffle_and_fill_*` = `0x47/0xc7` byte+1=0x06; modulo tweaks byte+6/tail | ◑ byte-diff |
| `simd_is_helper_thread` = get_sr SR `0x84` + compare | ◑ byte-diff |
| imageblock write/read = `0xe7`/`0x67` byte+1∈{06,16,0e}; **slice = byte+5 = offset>>1**; fmt byte+7 | ✅ (write landed on HW) + ◑ field decode |
| tile dispatch = mid-render record, no separate submission | ✅ iotrace (identical call seq) |

## Faults / reboots
None. Every splice was fault-contained; the device never wedged; no reboot needed.

## Recommended next
- Splice-validate the fence byte+3/byte+4 scope/flag bits under a real contended race (needs an ordering-sensitive
  multi-threadgroup kernel), and the `simd_shuffle_and_fill` modulo byte and `simd_is_helper_thread` SR `0x84`.
- Resolve the `0x11` byte+1=0x03 6-vs-8-byte convert sub-split (`half()` vs `bfloat()` narrowing).
- Decode the tile-dispatch cmdstream record fields in BO `0x58000` (hand-off to the cmdstream effort — how the tiler
  is told to run a tile kernel between geometry and store).
- 64-bit atomics: confirm whether the *hardware* `0x67` RMW has a width field even though MSL can't reach it
  (would need a hand-built 64-bit atomic encoding — extrapolate-and-test).
