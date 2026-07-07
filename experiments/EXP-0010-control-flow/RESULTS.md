# EXP-0010 Results — control flow + program structure/termination

Clean-room category: **OWN-SHADER + HW-PROBE** (+ PUBLIC for the applegpu *shape*).
Every byte inspected/spliced/executed is the compiled form of MSL we wrote. No Apple
binary was disassembled or introspected.

Device: Apple A18 Pro / G17P, SoC T8140, macOS 26.6 (25G5043d), Metal 4 / Apple9.
**Reboots: 0.** All faults (illegal jumps, mis-length splices, the jump-to-self infinite
loop) were *contained* `CMDBUF_ERROR`/`HANG`; the persistent runner logged-and-continued.

## TL;DR
1. **Preamble = `get_sr(thread_position_in_grid)`** (byte0 low-nibble `0xC`, 4B). HW-validated.
2. **Buffer base pointer** is preloaded into a **uniform/binding slot** and selected by
   `device_load` **byte+4** (0=buffer0, 1=buffer1, …). HW-validated. It is **not** in the
   code (EXP-0001), **not** the constant_program (E5), **not** the Metal binding index.
   **Scalar uniforms** (`constant int&`) are preloaded into a **uniform register** read
   directly by the ALU (no load at all).
3. **`0e000000` is not a required terminator** — corrupting it (even to a load opcode) is a
   no-op. Program extent is bounded by **pipeline metadata** (the `_agc.main` length); the
   final **store** is the last effective instruction.
4. **Predication, not branches, for simple divergence.** `if/else`, ternary, and early
   `return` compile to a **compare → per-lane execution mask** + masked ops / a **select**;
   no jump is emitted. HW-validated by moving the compare bound and inverting the condition.
5. **Loops use a real backward JUMP**: `0f 00 54 <off6> 00` (10B), `off6` = **signed
   little-endian byte-relative offset** (a `-44` back-edge). HW-validated.

## 1. Program structure: preamble + constant_program + uniform/pointer load

### Preamble = get-special-register (E1, HW-VALIDATED)
Every non-empty `_agc.main` begins with a 4-byte instruction whose byte0 low nibble is `0xC`
(`0c/1c/2c/3c a0 10 06`). For `gidonly` (`out[gid]=gid`) the whole program is
`0ca01006` + store + stop, and the baseline output is `[0..7]` — i.e. the preamble
**materializes `thread_position_in_grid` into the GPR the store reads**. Splicing it:

| splice | out | meaning |
|---|---|---|
| baseline `0ca01006` | `[0,1,2,3,4,5,6,7]` | reads global lane id |
| byte0 `0c→00` | `[0]*8` | opcode gone → 0 |
| byte0 `0c→1c/2c/3c` | `[0]*8` | **SR-select nibble** picks a *different* special register (=0 for a 1-threadgroup grid) |
| byte1 `a0→00` / byte2 `10→ff` | `CMDBUF_ERROR` | SR-index / dest fields, illegal → fault |
| byte3 `06→00` | `[0]*8` | required low control bits |

→ **`get_sr`**: `d = special_register[sr_sel]`; `sr_sel` (byte0 high nibble) selects which
lane SR; `sr_sel=0` = `thread_position_in_grid`.

### constant_program is NOT the buffer-base load (E5, HW-VALIDATED negative)
`_agc.main.constant_program` is a fixed 64-byte region with **two variants**:
- kernels that do a `device` **load**: `03 00 07 00 02 00 00 00 60 00` + `0e000000` + `0600…` pad
- kernels with no load (only stores / gid): `0e000000` + `0600…` pad

The `0300…6000` prefix does **not** scale with buffer count (copy1 = add2 = scalaradd). And
splicing it (cp[0], cp[8], cp[0:4]→`0e000000`) on `copy1` is a **no-op** — the load still
returns the correct data. So the constant_program does **not** materialize buffer base
pointers; the prefix is advisory (prefetch/preload hint, present iff a load exists). Exact
role = follow-up.

### Buffer base pointer = preloaded uniform slot, selected by device_load byte+4 (E7, HW-VALIDATED)
On `add2` (`out=a+b`, a=buffer1, b=buffer2), sweeping the two `device_load` (0x67, 14B)
instructions:
- load-a = `67 10 54 00 **01** 01 20 00 51 01 00 40 46 00`  (byte+4 = `0x01`)
- load-b = `67 00 44 04 **02** 01 20 00 51 01 00 40 46 00`  (byte+4 = `0x02`)

Splicing **load-a byte+4 `0x01 → 0x02`** makes it read **buffer b** → `out = b+b`
(`[20,40,…,160]`); `0x00` reads buffer0 (the zero out-buffer) → `out = 0+b`. So `device_load`
selects its buffer **base pointer by a slot index at byte+4** (0/1/2 = the bound buffers).
The base pointer itself is preloaded into that slot by the driver/command-stream, *outside*
the shader — matching EXP-0001's "binding index resolved outside the code."

**Scalar uniforms** (`constant int& n`): `scalaradd` (`out=a+n`) emits **one** load (for `a`)
and an `iadd` (`9f 01 56 00 02 18 00 a8 17 04`) whose second source is `n` — so a scalar
uniform is preloaded into a **uniform register** and read directly by the ALU, with **no**
`device_load` at all.

## 2. Program termination (E4) — corrects the old stop hypothesis

Splicing the trailing `0e000000` of `copy1` to **anything** — `0x00`, `0xff`, `0x67` (a
14-byte load opcode), or the payload → `ff` — is a **no-op**: the output stays
`[11,22,…,88]` and never faults. So:
- **`0e000000` is not a strictly-required terminator**; the HW does not execute past the last
  real instruction even when the trailing word is a valid opcode → **program length is
  out-of-band (pipeline/section metadata), not an in-band stop token.**
- The **final `device_store` is the last effective instruction**. Bit-flipping its opcode
  (`e7→e6`) faults; flipping its address/dest bits (byte+3/+4/…) writes to the wrong place
  or nothing (`[0]*8`, or `[11,55,0,…]` when the stride bit moves).
- After a *predicated* block the compiler emits a `0f 06 04 …` reconverge word before the
  stop (seen in `eret4`); that is a mask/reconverge op, distinct from end-of-shader.

## 3. Conditional execution: PREDICATION for simple divergence (E2/E3)

G17P does **not** branch for a simple divergent `if`/ternary/early-return — it **predicates**
via a per-lane execution mask. Two producers seen:
- **`0x0a`** (6B) — integer compare that sets the **execution predicate** (control flow:
  return/break/continue). Compare bound at **byte+3**; condition **sense** in byte0/byte+1.
- **`0x02`** (6B) — compare feeding a **select** (also the iminmax group; disambiguated by
  operands). Bound also at byte+3.

**`eret4` = `if(gid>=4) return; out=7`** (main `0ca01006 0a012282 14220f0554211c07 <store> 0f0604010000 0e`):
baseline `[7,7,7,7,0,0,0,0]` (lanes 0-3 store, 4-7 masked off — **all 8 lanes are dispatched**;
the store simply executes under the mask). Splicing the compare **immediate at main[7]**:

| main[7] | out | active lanes |
|---|---|---|
| `0x80` | `[7,7,0,0,0,0,0,0]` | gid<2 |
| `0x82` (orig) | `[7,7,7,7,0,0,0,0]` | gid<4 |
| `0x84` | `[7,7,7,7,7,7,0,0]` | gid<6 |
| `0x8e` | `[7]*8` | all |

**Condition inversion (HW-proof of the requested "which path appears"):** splicing the compare
**opcode byte main[4] `0x0a → 0x02`** flips the sense → `out = [0,0,0,0,7,7,7,7]` (lanes 0-3
now return, 4-7 store). This is the exact mirror path.

**`dsel5` = `out=(a>5)?100:200`** compiles branchlessly to `compare(0x02,6B)` + **select(0x16,4B)**
+ one store — **no jump**. Moving the compare immediate (main[21]) monotonically flips the
chosen value (`0x80`/`a>1` → all-100-except-a=0; `0x8e`/`a>7` → all-200). The grid variant
`gsel4 = (gid<4)?111:222` is `compare(0x02)` + **select(0x05,4B)** + one store, likewise
branchless. So both select opcodes (`0x05`, `0x16`) are 4-byte conditional selects.

### The compare/select vs branch decision
Simple divergent bodies (assign / single store / ternary) → **predication** (mask + select,
no jump). Only loops (and larger skips) emit a real jump.

## 4. Loops & the backward JUMP (E6, HW-VALIDATED)

`prodloop = s=1; for i<n: s=s*3+1; out=s` (data-dependent, not closed-formed) runs a real
loop: baseline `out=[1,4,13,40,121,364,1093,3280]` for `n=[0..7]` (exact). Its `_agc.main`
contains, in order: `0a…` compare (loop condition → predicate), `0f 05 54 …` / `0f 01 54 …`
execution-mask ops, the body (`9f…` mul, `0a…` recompare), then the **backward jump**

```
main[106]:  0f 00 54  d4 ff ff ff ff ff  00
            └op┘└sub┘ └── off6 = 0xffffffffffd4 = signed -44 ──┘
```

followed by `0f 06 04 02 00 00` / `0f 06 04 01 00 00` reconverge words, then the store. So:
- **`0x0f` is the control-flow / execution-mask group**; sub-opcode in byte+1 (`00`=jump,
  `05`/`01`=mask push/else, `06`=pop/reconverge). The **jump is `0f 00 54 <off6> 00`, 10B**.
- **`off6` is a signed little-endian byte-relative offset** (here `-44`, a backward edge).

Splice-and-observe on the jump offset:

| splice off6 | result | interpretation |
|---|---|---|
| `d4ffffffffff` (orig, -44) | `[1,4,13,…]` OK | live loop back-edge |
| `000000000000` (0, → self) | **HANG** (contained) | infinite loop — proves it is the taken back-edge |
| `+8` (forward) | `CMDBUF_ERROR` | jumps into mid-instruction → fault |
| `-22` (half) | `CMDBUF_ERROR` | off an instruction boundary → fault |

→ **Loop model:** a compare sets the per-lane execution mask; the body runs masked; a
**backward `0f 00` jump** re-executes while lanes remain active; `0f 06` pops/reconverges the
mask on exit. This is an execution-mask + relative-jump loop (conceptually G13-like: a mask
plus a `jmp`-while-active), but the **encodings are G17P-specific** (byte0 `0x0f`, 10-byte
`0f 00 54 <off6> 00`). Fixed-count loops (`for i<10`) are fully **unrolled** (no jump);
`break`/`continue`/early-return over a simple body are **predicated** (compare `0x0a` + mask).

## 5. ISA database + round-trip
`tools/agx-isa/` updated (all HW-validated fields flagged; inferred fields marked):
- **length rule** extended: `0x0a`→6, `0x05`/`0x16`→4, `0x0f`→10 when byte+1==0 (jump; other
  0f sub-ops left UNKNOWN so they are never mis-tokenized).
- new descriptors **`icmp_pred`** (0x0a), **`sel`** (0x16), **`psel`** (0x05), **`jump`**
  (0x0f/00); **`preamble`→`get_sr`** with an `sr_sel` field; **`device_load`** gains the
  HW-validated **`base_slot`** field (byte+4); **`stop`** semantics corrected (non-required).
- `roundtrip_test.py`: added the 5 CF instructions (A) and the `gsel4`/`dsel5` whole programs
  (C). **`python3 roundtrip_test.py` → ALL PASS.** DB now 20 descriptors, **11 HW-validated**.

## 6. Faults / reboots
**Reboots: 0.** Across all of E1–E7 (~1000+ dispatches, incl. the deliberate jump-to-self
infinite loop and dozens of illegal-jump/mis-length splices) only *contained*
`CMDBUF_ERROR`/`HANG` occurred; the persistent runner's per-request watchdog killed+restarted
the child on the hang and continued. `macvdmtool` was never needed.

## 7. Clean-room status
Clean. Only our own MSL was compiled and only our own compiled bytes were spliced/executed.
`gen_kernels.py`, `gen_diff.py`, `dump_cf.py`, `cf_probe.py`, `run_experiments.py`,
`e7_base.py`, `solve_lengths.py`, `segment_cf.py` are our own tools; reused OWN-SHADER tools
`shdump`, `agxparse.py`, `intprobe.py`, `agxrun_persist`, `persistrun.py`. The only
third-party input is the *public* MIT applegpu (design reference / execution-mask *concept*,
read only). `raw/` holds text logs only; the `.bin` archives stay on the device under
`~/cleanroom_work/exp0010/`.
