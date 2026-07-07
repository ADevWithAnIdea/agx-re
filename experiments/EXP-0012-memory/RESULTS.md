# EXP-0012 Results — memory access family (device / threadgroup / constant)

Clean-room category: **OWN-SHADER + HW-PROBE** (+ PUBLIC for the applegpu *shape*).
Every byte inspected/spliced/executed is the compiled form of MSL we wrote. No
Apple binary was disassembled or introspected.

Device: Apple A18 Pro / G17P, macOS 26.6 (25G5043d), Metal 4 / Apple9.
**Reboots: 0. Faults: 0.** All six HW validations returned `STATUS OK`.

## TL;DR
1. **ONE opcode pair, all address spaces.** `0x67` = load, `0xe7` = store, **14B**,
   cover **device, threadgroup AND constant**. The address space is a bit in **byte+1**
   (`0x02` = threadgroup); constant reads are **byte-identical to device** reads. The
   vtx/frag candidates 0x07/0x87/0x97/0xa7 are *not* threadgroup memory.
2. **Element addressing; no in-instruction offset.** Effective byte address =
   `index_GPR * element_size`. There is **no immediate/displacement/scale field** in the
   load/store. `a[i+k]`, `a[i*s]` are computed by a **prior integer ALU op on the index**
   (in *element* units); the load then consumes the result GPR. `a[gid+1/+2/+4]`,
   `a[gid*2/*4]` all share a **byte-identical** `0x67` load.
3. **Access size = byte+12** (address element-size class), **data width = byte+8**.
   `+12` bits[1:4] = k → `2^(k-1)` bytes (`0x42`=1B/8b, `0x44`=2B/16b, `0x46`=4B/32b,
   `0x48`=8B/64b). HW: splicing `+12` rescales the address stride to 1/2/8 bytes.
4. **Vector width = byte+5** (count of consecutive 32-bit words). A `float4`/`int4`
   is **one** load + **one** store moving 4 words (not 4 instructions). HW: splicing
   `+5` `04→01` truncates the copy.
5. **Sign vs zero extension:** signed sub-32 → correct sign-extend (`-1`,`-128`);
   unsigned → zero-extend (`255`,`128`). The **load fetches the sub-word; sign-extension
   is a following ALU shift** (the compiler emits `0xa7` shifts for signed char/short),
   not an in-load flag. Byte+3 bit1 selects the unsigned/zero-extend load variant.
6. **base_slot (byte+4)** re-confirmed for device *and* constant; threadgroup uses `0x08`
   (a local descriptor, not a buffer). **Scalar `constant int&`** stays a preloaded
   uniform register read directly by the ALU (no load), per EXP-0010.

## Device load/store 14-byte field map (HW-VALIDATED, EXP-0012)

Aligned across the kernel family (`raw/memfields.log`); `[HW]` = splice-validated here.

```
        +0  +1  +2  +3  +4  +5  +6  +7  +8  +9 +10 +11 +12 +13
copy1   67  10  44  00  01  01  20  00  51  01  00  40  46  00   i32 scalar
ld_char 67  10  44  00  01  01  20  00  61  01  00  40  42  00   i8  -> +8=61,+12=42
ld_shrt 67  10  44  00  01  01  20  00  41  01  00  40  44  00   i16 -> +8=41,+12=44
ld_long 67  10  44  00  01  02  20  00  59  01  00  40  48  00   i64 -> +5=02,+12=48
vec3    67  10  44  00  01  03  20  00  5d  01  00  40  40  00    .3 -> +5=03
vec4i   67  10  44  00  01  04  20  00  57  01  00  40  40  00    .4 -> +5=04
off1    67  00  44  00  01  80  20  00  51  01  00  40  46  00   (index from ALU)
```
| byte | field | meaning | status |
|---|---|---|---|
| +0 | opcode | `0x67` load / `0xe7` store | match |
| +1 | space + index | **bit1 (`0x02`) = threadgroup** (else device/constant); higher bits = index GPR | **[HW] space (M5)**; reg inferred |
| +2 | amode | addressing-mode byte (`0x44`/`0x54`) | inferred |
| +3 | extmode | **bit1 (`0x02`) = unsigned/zero-extend load** (sub-32) | inferred (M3) |
| +4 | **base_slot** | preloaded buffer-base uniform slot (0=buf0,1=buf1,…) | **[HW] (E7, M6)** |
| +5 | **count** | # consecutive 32-bit words = **vector width** (1/2/3/4); bit7 = index-GPR-high | **[HW] (M4)** |
| +6..+7 | addr | index / addressing tail | inferred |
| +8 | **dst/data width** | destination(load)/data(store) reg + **data width** (`51`=32b,`41`=16b,`61`=8b,`59`=64b) | **[HW] width (M2)**; reg inferred |
| +9..+11 | tail | register/address tail | inferred |
| +12 | **elem_size** | **address element size** bits[1:4]=k → `2^(k-1)` B (`42`=1,`44`=2,`46`=4,`48`=8) | **[HW] (M2)** |
| +13 | 0x00 | — | inferred |

## HW validations (`raw/mem_probe.log`)

### M1 — element addressing, load has NO offset field  (`off1: out=a[gid+1]`)
Prior `0x9f` iadd computes `gid+k`; its immediate is `(k<<1)` (EXP-0007) at `main[9]`.
Baseline `out = a[1..8] = [10,20,…,80]`. Splicing **only** the iadd immediate:

| `main[9]` | k | out |
|---|---|---|
| `0x00` | 0 | `[0,10,20,…,70]` = a[gid] |
| `0x02` | 1 | `[10,20,…,80]` |
| `0x04` | 2 | `[20,30,…,90]` = a[gid+2] |
| `0x08` | 4 | `[40,50,…,110]` = a[gid+4] |

The **load bytes are byte-identical** for `off1`/`off2`/`off4`/`str2`/`str4` (only the
prior ALU changes) → the offset is an ALU-computed **element index**; the load has no
displacement/scale of its own. Offset units are **elements** (the ALU add is `k<<1`).

### M2 — access size = +12 (address scale) + data width = +8  (`copy1`, splice load)
`a[i] = 0x1122330(i+1)` (low byte distinct). Splicing the load byte **+12**:

| +12 | stride | out (per 4 lanes) |
|---|---|---|
| `0x46` (orig,4B) | word i | `w0,w1,w2,w3,w4,w5,w6,w7` |
| `0x42` (1B) | byte i | `w0,w0,w0,w0,w1,w1,w1,w1` (aligned 32-bit read, stride **1 byte**) |
| `0x44` (2B) | 2·i | `w0,w0,w1,w1,w2,w2,w3,w3` (stride **2 bytes**) |
| `0x48` (8B) | 8·i | `w0,w2,w4,w6,0,0,0,0` (stride **8 bytes**, OOB→0) |

So **+12 scales index→byte address** (element size). Splicing **both +8=`0x61` and
+12=`0x42`** (the full `ld_char` form) makes a **true 8-bit byte load**:
`out = [0x01,0x33,0x22,0x11,0x02,0x33,0x22,0x11]` (individual bytes zero-extended) →
**+8 sets the data width landed in the register.** → confirms **element addressing**.

### M3 — sign vs zero extension  (`ld_char` vs `ld_uchar`, bytes `01 02 7f 80 81 fe ff 00`)
- `ld_char` (signed): `out = [1,2,127,-128,-127,-2,-1,0]` — sign-extended (uses `0xa7` shifts).
- `ld_uchar` (unsigned): `out = [1,2,127,128,129,254,255,0]` — zero-extended.
- Splicing `ld_uchar` load to the "signed" byte pattern (`+3→00,+5→01`) → `[0]*8`
  (breaks the load) → the extension is **not** a clean in-load sign toggle; **signed
  sub-32 loads are sign-extended by a following ALU shift**, unsigned use the
  zero-extend load variant (byte+3 bit1). Behavior HW-validated; mechanism inferred.

### M4 — vector width / count = +5  (`vec4i: int4 copy`, 8×int4)
One `0x67` load (`+5=04`) + one `0xe7` store move 4 words. Baseline `out = 1..32`.
- Splice **load +5 `04→01`** → `[1,2,3,4]` repeated → only 1 of 4 components fetched.
- Splice **store +5 `04→01`** → each lane stores 1 word (partial `int4`s).
→ **+5 = component/word count = vector width;** one instruction moves N words.

### M5 — threadgroup memory = `0x67`/`0xe7` with byte+1=`0x02`  (`tg_copy`, `tg_rot8`)
`tg_copy` (identity roundtrip through `threadgroup int tile[]`): `out = a` ✓.
`tg_rot8` (`out=tile[(lid+1)&7]`): `out = [20,30,40,50,60,70,80,10]` ✓ (rotate-by-1).
Both emit a **threadgroup store `e7 02 …`** and **threadgroup load `67 02 …`** (byte+1
=`0x02`, base_slot byte+4=`0x08`, local address = lid-derived) alongside the device
load/store (byte+1=`0x00`/`0x10`). Splicing the **threadgroup store or load byte+1
`0x02→0x00`** (i.e. "make it device") → `out = [0]*8` for both kernels → **byte+1 bit1
is the threadgroup address-space selector.**

### M6 — constant reads = device reads  (`const_copy: constant int* a`)
`constant int* a` array indexing compiles to a **byte-identical** `0x67` device_load
(`6710440001012000510100404600` == `copy1`). Baseline `out = a` ✓. Splicing its
**base_slot +4 `0x01→0x00`** → `out = [0]*8` (reads the zero out-buffer) → constant
reads use the **same encoding + base_slot** mechanism as device; the device/constant
distinction is **not in the shader ISA** (it's which buffer the base slot points at).

## Addressing model (summary)
- **Element addressing.** address = `index_GPR * element_size(+12)`; index is a GPR.
- **No immediate offset / displacement / built-in scale** in the load/store. `a[i+k]`
  and `a[i*s]` are prior integer ALU ops on the index, in **element** units.
- **Access size** (element, address scale) at **+12** (1/2/4/8 B); **data width**
  landed in the register at **+8**; **vector width** (word count) at **+5**.
- **Sign extension** for signed sub-32 = a following ALU shift (not the load); unsigned
  = zero-extend load variant (byte+3 bit1).

## Atomics (noted, not solved — for a later experiment)
`atomic_fetch_add` (`atomic_add.metal`) does **not** use `0x67`/`0xe7`. It compiles to a
new op **byte0 `0xbf`** plus an execution-mask **retry loop** (`0x0a` compare, `0f 05`
push / `0f 06` reconverge) around a special `67 01 …` access (byte+1=`0x01`) — i.e. an
LL/CAS-style loop. Recorded in `raw/dump_mem.log`; full decode deferred.

## ISA database + round-trip
`tools/agx-isa/` updated:
- **`device_load` / `device_store`** promoted from structural to **HW-VALIDATED** with
  the full byte-aligned field map (space +1, base_slot +4, count/vector-width +5, data
  width +8, element-size +12); each field flagged HW vs inferred.
- length rule unchanged (`0x67`/`0xe7` = 14B keyed on byte0 → covers all address spaces).
- `roundtrip_test.py`: added 7 memory instrs (32/8/64-bit, vec4 load+store, threadgroup
  load+store) and 4 memory programs (`mcopy32`/`mload64`/`mvec4`/`moff1`).
  **`python3 roundtrip_test.py` → ALL PASS.** DB now **12 HW-validated** descriptors.

## Faults / reboots
**Reboots: 0. Faults: 0.** ~70 dispatches (baseline + splices) all `STATUS OK`;
`macvdmtool` never needed.

## Clean-room status
Clean. Only our own MSL was compiled and only our own compiled bytes were
spliced/executed. Our own tools: `dump_mem.py`, `memfields.py`, `mem_probe.py`,
`kernels/*.metal`; reused OWN-SHADER tools `shdump`, `agxparse.py`, `intprobe.py`,
`agxrun_persist`, `persistrun.py`. Third-party input = the *public* MIT applegpu
(table *shape* only, read-only). `raw/` holds text logs + extracted hex only; the
`.bin` archives stay on the device under `~/cleanroom_work/exp0012/`.
