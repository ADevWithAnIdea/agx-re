# EXP-0005 Results — ISA database + float-ALU characterization

Clean-room category: **OWN-SHADER + HW-PROBE** (+ PUBLIC for the applegpu
*shape*). Every byte inspected/spliced/executed is the compiled form of MSL we
wrote. No Apple binary was disassembled or introspected.

Device: Apple A18 Pro / G17P, SoC T8140, macOS 26.6 (25G5043d), Metal 4 / Apple9.

## TL;DR
- **Persistent runner works** (`tools/agxtest/agxrun_persist.m`): one live
  `MTLDevice`, requests over stdin, logs-and-continues past faults. The full
  256-value op sweep — **including 32 contained GPU-hang faults — ran in a single
  process with ZERO reboots.**
  - Crux fix: a library built from *source* has a fixed AIR hash whose native
    code the device **memoizes in-process**, so a later spliced archive is
    ignored. The runner instead loads a **fresh `MTLLibrary` from the spliced
    archive's own bytes** each request (the public hwtestbed's approach), so the
    spliced machine code actually runs. Verified: `1c→1d` flips add→mul, `0xff`
    hangs (contained), the next request recovers — all in one process.
- **ISA database stood up** (`tools/agx-isa/`): schema + 8 descriptors + a
  table-driven **assembler** and **disassembler** + a **round-trip test that
  passes** (`asm(disasm(b))==b`, `disasm(asm(x))==x`, and clean tokenization of
  every real program).
- **Instruction-length rule** determined; it tokenizes all our float shaders with
  **zero leftover bytes**. Key G17P fact: the **first parcel does not encode
  length** (a real difference from G13).
- **Float ALU op-select** located as a **3-bit field at instruction bits [16:19]**
  (low 3 bits of byte +2): `0b100`=fadd, `0b101`=fmul — **HW-validated** across the
  full 256-value sweep, distinguishing operations from operand/modifier bits.

## 1. The ISA database (task 2)

Schema (machine-readable, `tools/agx-isa/isadb.py::DB`, exported to `db.json`):
each descriptor is `{mnemonic, length, match:[(bitstart,width,value)],
fields:[{name,start,width,type,enum?}], semantics, provenance}`; instructions are
little-endian integers so `bit 16 = byte +2, bit 0`. One table drives both the
assembler (fields→bytes) and disassembler (bytes→mnemonic+fields).

| mnemonic | len | provenance |
|---|---:|---|
| `falu2` (fadd/fmul) | 6 | **HW-VALIDATED** (EXP-0003/EXP-0005) |
| `falu3` (fma) | 8 | inferred (byte-diff) |
| `fminmax` | 6 | inferred (byte-diff) |
| `funary` (fmov/neg/abs) | 10 | inferred (byte-diff) |
| `device_load` | 14 | structural (inferred) |
| `device_store` | 14 | structural (inferred) |
| `preamble` | 4 | structural (inferred) |
| `stop` | 4 | inferred |

**8 descriptors; 1 hardware-validated** (`falu2`, the fadd/fmul op-select). The
rest are byte-diff/structural — included so the disassembler can tokenize whole
shaders — and are explicitly flagged as such.

## 2. Instruction-length encoding rule (task 3)

Parcels are 2 bytes; all lengths are even. **On G17P the first parcel does NOT
encode length.** Counter-example from our own shaders:

```
fsub = 09 01 1c 05 00 c8            (6 bytes)
fma  = 09 01 1e 05 81 08 02 c0      (8 bytes)
        ^^^^^ identical first parcel `09 01`, different length
```

So length is a function of the opcode: **byte 0 selects the format/group**, and
for the float-ALU group a **length bit at byte +2, bit 1** extends 6→8 bytes
(fma). Observed byte0→length table (all validated by clean tokenization):

| byte0 | group | length |
|---|---|---|
| `0x0e` | stop/end | 4 |
| low nibble `0xC` (`0x0C`/`0x1C`) | preamble (get_sr-like) | 4 |
| low nibble `0x7` (`0x67`/`0xE7`) | device load / store | 14 |
| `0x09` | float ALU | 6, or **8 if `(byte[+2] & 0x02)`** |
| `0x0b` | float unary | 10 |
| `0x12` | float min/max | 6 |
| `0x9f` | integer ALU | 10/12 — **not solved (follow-up)** |

**Proof (task 3 acceptance):** `tools/agx-isa/agxisa.py tokenize` splits every
one of our real `_agc.main` programs into a clean instruction sequence with **0
leftover / misaligned bytes** (`raw/length_rule.txt`, `raw/roundtrip.txt` §C):

```
fadd  -> preamble device_load device_load fadd  device_store stop   (56B, 0 left)
fma   -> preamble device_load device_load device_load fma device_store stop (72B, 0 left)
copy  -> preamble device_load device_store stop                     (36B, 0 left)
maxf  -> preamble device_load device_load fminmax device_store stop (56B, 0 left)
...  (11 float programs total, all CLEAN)
```

The two integer kernels (byte0 `0x9f`) are the only ones not covered — the
integer-ALU length is a noted follow-up, out of scope here.

## 3. Float ALU op map (task 4) — HARDWARE-VALIDATED

Canonical kernel `out[gid] = a[gid] + b[gid]`; the float ALU instruction is
`09 05 1c 01 00 c0` at `_agc.main` offset `0x20` (op byte at `0x22` = instruction
offset **+2**). We swept that byte through all 256 values on the real GPU
(`opsweep.py`, `raw/opmap.txt`), dispatching each with probe vectors
`a=[2,3,8,7]`, `b=[4,6,2,5]` and matching outputs against candidate ops.

**The op-select is the low 3 bits of byte +2 = instruction bits [16:19] (width 3).**

| op-byte low3 (bits[16:19]) | result | evidence | status |
|---|---|---|---|
| `0b100` (4) | **fadd** `d=a+b` | out `[6,9,10,12]` for **all 8** values `0x04,0x0c,…,0x3c` | **HW-VALIDATED** |
| `0b101` (5) | **fmul** `d=a*b` | out `[8,18,16,35]` for **all 8** values `0x05,0x0d,…,0x3d` | **HW-VALIDATED** |
| `0b111` (7) | illegal op | **all 32** values with low3=7 → contained GPU-hang fault | HW-observed (fault) |
| others (`000/001/010/011/110`) | no store / zero out | `[0,0,0,0]` (bit 1 set desyncs length; bit 2 clear disables) | HW-observed (no-op) |

Bit decomposition **within byte +2**, all from the sweep:
- **bit 0 (instr bit 16)** = add(0)/mul(1) — the EXP-0003 bit, now shown to be
  bit 0 of a wider field. **HW-VALIDATED.**
- **bit 1 (instr bit 17)** = length/form bit (6-byte 2-source vs 8-byte fma);
  setting it in the 2-source kernel desyncs the stream → zero output.
- **bit 2 (instr bit 18)** = arithmetic-enable (must be 1 for fadd/fmul).
- **bits 3-5** = **don't-care for the operation** — all 8 combinations still
  produced fadd/fmul (that is how we bounded the field width to 3 bits).
- **bits 6-7 set** → op degenerates to **srcA passthrough** (output = `a`),
  a different source-addressing/move mode (24 values, `fmov_a` rows).

Compiler-canonical encodings are `0x1c` (fadd) / `0x1d` (fmul); their low3 are
`0b100`/`0b101`. Only add/mul are hardware-*validated* here; sub/min/max/fma live
in **different** instruction formats (byte0 `0x12` for min/max, the negate
modifier for fsub, byte0 `0x09`+lenbit for fma) — recorded in the DB as inferred,
not claimed as 2-source op-select values. `fdiv` is a multi-instruction macro,
not a single ALU op (excluded).

## 4. Round-trip test (task acceptance)
`tools/agx-isa/roundtrip_test.py` → **ALL PASS** (`raw/roundtrip.txt`):
- (A) `asm(disasm(bytes)) == bytes` for 14 real own-shader instructions.
- (B) `disasm(asm(fields)) == fields` for 5 synthesized encodings.
- (C) 11 whole real `_agc.main` programs tokenize with 0 leftover and re-serialize
  byte-exactly.

## 5. Faults / reboots
- **Reboots: 0.** All 32 illegal-op probes (op low3=`0b111`) produced *contained*
  `CMDBUF_ERROR` (`kIOGPUCommandBufferCallbackErrorHang`); the persistent runner
  logged each, refreshed its command queue, and continued. No watchdog timeout
  (true wedge) occurred, so the `macvdmtool` reboot fallback was never needed.
- Confirms EXP-0003's fault-containment for the illegal-ALU-op class, now at
  scale (256 dispatches) and in a single persistent process.

## 6. Recommended next experiment
**Operand/register-field depth** for `falu2`: resolve the bit-layout and width of
`dst` / `srcA` / `srcB` (currently whole-byte fields) by sweeping register
indices in a controlled kernel. Then: the packed non-IEEE float **immediate**
encoding, source **modifiers** (neg/abs) width, the **integer ALU** family
(byte0 `0x9f`) length+op map, and **fma/3-source** field decode.

## 7. Clean-room status
Clean. Only our own MSL was compiled and only our own compiled bytes were
spliced/executed. `shdump.m`, `agxparse.py`, `agxrun_persist.m`, `persistrun.py`,
`opsweep.py`, and the `agx-isa` DB/asm/disasm are our own tools; the only
third-party inputs are the *public* MIT applegpu (design reference, read only).
`raw/` holds text logs only; the `.bin` archives stay on the device under
`~/cleanroom_work/exp0005/`.
