# EXP-0007 Results — integer ALU family (byte0 `0x9f` and cousins)

Clean-room category: **OWN-SHADER + HW-PROBE** (+ PUBLIC for the applegpu *shape*).
Every byte inspected/spliced/executed is the compiled form of MSL we wrote. No Apple
binary was disassembled or introspected.

Device: Apple A18 Pro / G17P, SoC T8140, macOS 26.6 (25G5043d), Metal 4 / Apple9.

## TL;DR
- **The "0x9f group" is the integer *arithmetic* family** (iadd/isub/imul/imad). Integer ops
  as a whole are **spread over several byte0 groups**, each its own instruction format — the
  same shape as the float side (falu2 / fminmax / funary are distinct groups), *not* one
  unified op-select like a single falu2.
- **Length rule (task 1): byte +1 bit 0.** For the integer arithmetic groups (`0x9f`/`0x1f`
  add-sub, `0xa7` shift/bitfield): **10 bytes** (2-source) when `b1&1==1`, **12 bytes**
  (3-source multiply-add / bitfield) when `b1&1==0`. HW-validated: splicing iadd's `b1` bit0
  faults (the stream is re-length'd into the following store). `agxisa.py tokenize` splits
  every single-instruction integer `_agc.main` we compiled (**26** kernels,
  `raw/dump_alu_all.log`) with **0 leftover bytes**; `roundtrip_test.py` §C embeds 14
  representative ones (all clean) and the 11 float programs still tokenize.
- **Integer immediate (task 3): a plain 8-bit `(K<<1)` inline field** — HW-validated for
  K∈{0..255} (all pass); K≥256 / negative fall back to a materialized form. This is **NOT**
  the float minifloat.
- **0 reboots.** ~4000 dispatches across all sweeps/validations; illegal encodings produced
  *contained* `CMDBUF_ERROR`, the persistent runner logged-and-continued.

## 1. Group → operation map (task 2)

| group `byte0` | length | operation(s) | op-select | provenance |
|---|---|---|---|---|
| `0x9f` / `0x1f` | 10 | **iadd / isub** (`a ± b`) | `b0 bit7` = srcA-negate | **HW-validated** |
| `0x9f` / `0x1f` | 12 | **imul / imad** (`a*b [+c]`) | 3-source mul-add form | **HW-validated** (behaviour) |
| `0x0b` | 10 | **iand / ior / ixor** | `b2[0:4]` + `b4`/`b5` srcB-invert | HW (op toggles) / byte-diff |
| `0x02` | 6 | **imin/imax/umin/umax** | `b4[0:3]` sel | **HW-validated** |
| `0xa7` | 10 / 12 | **ishr** / **bitfield-extract** | (multi-instr for reg shifts) | byte-diff |
| `0x27` | 8 | **popcount** / unary reduce | `b0` | byte-diff |
| `0x12` | 14 | **integer compare → select 0/1** | `b4` cond, `b6` sign | byte-diff |

Notes: `imul`==`umul` byte-identical (low 32 bits are sign-agnostic); `imul` is emitted as the
`imad` 12-byte form with addend `c=0`. Bitwise ops share `byte0 0x0b` with the float unary
group. Compare shares `byte0 0x12` with float min/max (disambiguated by length: `byte+2`
low-nibble `0x0d` ⇒ 14-byte compare).

### Integer 2-source arithmetic (`0x9f`/`0x1f`, 10-byte) — the primary target
Canonical `out=a+b` (nofast) = `9f 01 56 00 02 08 00 a8 17 05`. HW-validated bit roles
(byte offsets within the ALU instruction):

| field | location | meaning | status |
|---|---|---|---|
| group id | `b0[0:7] == 0x1f` | integer add/sub group (`0x9f`, `0x1f`) | HW (tokenizes) |
| **srcA negate** | `b0 bit7` (`0x80`) | `1`=+srcA (add), `0`=−srcA → `a+b`→`b−a` | **HW-validated** (signed) |
| **length bit** | `b1 bit0` | `1`=10B 2-src, `0`=12B mul-add | **HW-validated** (fault-on-splice) |
| **arith enable** | `b2 bit1` | must be 1 to store a result (256-sweep: `a+b` iff set) | **HW-validated** |
| **dst reg** | `b3` = `(reg<<1)\|size` | destination register (dstc relocation sweep) | **HW-validated** |
| srcB immediate | `b4:b5:b6bit0` | `(K<<1)` when srcB is an 8-bit immediate | **HW-validated** |
| srcA/srcB regs | `b7:b8:b9` tail | packed source register descriptors | located (byte-diff) |

Op-select finding: **there is no single 3-bit integer op-select** like the float group. In
the b0 sweep of iadd, changing `b0` mostly yields no-store/fault/srcA-passthrough; the only
clean transitions were `0x9f→a+b`, `0x1f→b−a` (srcA negate). Subtract is add-with-negate plus
operand commute — the same strategy the compiler uses for float `fsub` (EXP-0006). So the
integer arithmetic "op" is add, parameterised by per-source negate; multiply is the separate
12-byte form. `b2` is not an op-select (256-sweep: it only gates the store via bit1).

### min/max sel field (`0x02` group) — fully HW-validated
6-byte `02 01 1e 05 <sel> c0`. `sel` = `b4[0:3]`: **bit0 = min(1)/max(0), bit1 = signed(1)/
unsigned(0), bit2 = 1 (integer-enable)**. Values: `umax=0x04 umin=0x05 imax=0x06 imin=0x07`
(float `fmin/fmax` are the same byte with bit2=0). All four validated on mixed-sign inputs;
splicing `imin`→`umin` (clear bit1) on hardware flips signed→unsigned min. `raw/imin_b4.log`,
`raw/intval.log`.

### bitwise logic (`0x0b` group) — op-select located
`b2[0:4]` + the `b4/b5` srcB-descriptor select the truth-table. HW: sweeping `b2` on the
`ixor` base cleanly toggles **`b2` low-nibble `0x6`→XOR, `0x7`→OR** (`raw/ixor_b2.log`,
`raw/ior_b2.log`); AND vs OR is carried in `b4/b5` (`b4=0,b5=0` for AND vs `b4=2,b5=8` for
OR/XOR — a per-source invert). All of iand/ior/ixor compute correctly unmodified
(`smoke.py`). Full truth-table decode is a follow-up.

## 2. Length rule (task 1) — HW-validated + tokenization proof
`byte+1 bit0` selects 10 vs 12 for the arithmetic groups (contrast the float group's
`byte+2 bit1`). Evidence:
- **Byte-diff:** every 10-byte int op has `b1=0x01`; every 12-byte op (`imul`, `imad`, `ibfe`)
  has `b1=0x00`; only `b1` differs in the otherwise-identical iadd/imul prefix.
- **HW splice:** clearing iadd's `b1` bit0 → `CMDBUF_ERROR` (the GPU now reads 12 bytes,
  eating 2 bytes of the following store) — `raw/intval.log` "LENGTH BIT".
- **Tokenization (acceptance):** `agxisa.py tokenize` splits all 26 single-instruction integer
  `_agc.main` programs (`raw/dump_alu_all.log`) with **0 leftover**; the 14 embedded in
  `tools/agx-isa/roundtrip_test.py` §C additionally re-serialize byte-exact. Example:
  `iadd -> preamble load load iadd2 store stop (60B, 0 left)`.

Full byte0 → length table now in `tools/agx-isa/isadb.py::instr_length`:
`0x67/0xe7`=14 (load/store, was mis-keyed as low-nibble 0x7 which collided with `0xa7`/`0x27`
— now fixed); `0x02`=6; `0x12`=6 or 14; `0x9f/0x1f/0xa7`=10/12 (b1 bit0); `0x27`=8.

## 3. Operand & immediate encoding (task 3) vs the float form
- **dst = `b3`, `(reg<<1)|size`** (HW: dstc sweep relocates the result to reg N as `b3`
  steps by 2). This differs from the float `falu2` where dst is `b0[4:8]` — integers put dst
  in its own byte, and there is room for far more than 16 registers.
- **srcA / srcB** live in the `b7:b8:b9` tail (24 bits) — byte sweeps show `b7` gates srcA and
  `b8` gates srcB (mis-set → the source reads 0, so `a+b` degenerates to `a` or `b`). The
  `(reg<<1)` low-bit-size convention is consistent with dst and the float model, but the exact
  srcA/srcB bit widths are **located, not yet fully bit-decoded** (follow-up).
- **Integer immediate = `(K<<1)`, 8-bit unsigned inline** at `b5` (+`b6 bit0` for the 9th
  scaled bit). HW-validated `out==a+K` for **all K∈{0,1,2,5,…,255}**; K≥256 and negative K
  are not inline-representable (compiler materializes them). Worked splices in
  `raw/intval.log` "INTEGER IMMEDIATE". Contrast the float srcB immediate (8-bit *minifloat*,
  EXP-0006) — the integer form is a **plain scaled integer**, low bit = immediate/flag.
- **Signedness** is not in the add form (two's-complement add/sub are sign-agnostic); it
  appears where it matters: min/max (`b4 bit1`, HW-validated) and compare (`b6`, byte-diff).

## 4. Three-source / fused forms (task 4, noted not fully solved)
- **imad** (`a*b+c`) and **imul** share the 12-byte `0x9f` mul-add form (`imul` = `imad` c=0);
  the srcC descriptor occupies the extra `b7:b11` bytes (`imul` c=0 vs `imad` c=reg differ at
  `b7/b9/b10`). Behaviour HW-validated (smoke); field bit-packing byte-diff only.
- **ibfe** (`extract_bits`) uses the 12-byte `0xa7` form; **ibfi** (`insert_bits`) and the
  **shifts** (`<<`, `>>`) are **multi-instruction lowerings** (`0x2b` stage + `0x27`/`0x9f`
  stage) — noted for a dedicated follow-up.

## 5. ISA database + round-trip
`tools/agx-isa/`:
- `instr_length` extended with the integer groups (byte0 table above); float rule unchanged.
- New descriptors: **`iadd2`, `imad`, `iminmax`** (HW-validated) + `iunary`, `ishift`, `ibfe`,
  `icmpsel` (inferred/structural, so whole shaders tokenize & disassemble). 16 descriptors
  total, **5 HW-validated** (float `falu2`/`falu2i` + int `iadd2`/`imad`/`iminmax`).
- `roundtrip_test.py` extended: 17 real integer instructions (A), 3 synthesized integer cases
  (B), 14 whole integer programs tokenizing with 0 leftover (C). **`python3 roundtrip_test.py`
  → ALL PASS.** `db.json` regenerated.

## 6. Faults / reboots
- **Reboots: 0.** Across the full sweep campaign (~15 byte-sweeps of 256 + the validation
  batches, ~4000 dispatches) only *contained* `CMDBUF_ERROR` faults occurred (illegal opcode
  bytes and mis-length'd splices); the persistent runner logged each and continued. The
  `macvdmtool` reboot fallback was never needed.

## 7. Recommended next experiment
- Full bit-decode of the integer srcA/srcB register descriptors (`b7:b9` tail / `b6:b11` in
  the 12-byte form) + confirm the 64-GPR aliasing for integer sources.
- The bitwise truth-table (`b2[0:4]` + `b4/b5` source-invert) — enumerate all 16 LUT2 codes.
- The multi-instruction shift and bitfield-insert lowerings (`0x2b`/`0x27` stages).
- Integer→float and float→int conversions, and the `0x0b`-group disambiguation.

## 8. Clean-room status
Clean. Only our own MSL was compiled and only our own compiled bytes were spliced/executed.
`gen_kernels.py`, `intprobe.py`, `dump_alu.py`, `smoke.py`, `intsweep.py`, `intval.py` are our
own tools; reused OWN-SHADER tools `shdump`, `agxparse.py`, `agxrun_persist`, `persistrun.py`
from EXP-0001/0005/0006; the only third-party input is the *public* MIT applegpu (design
reference, read only). `raw/` holds text logs only; the `.bin` archives stay on the device
under `~/cleanroom_work/exp0007/`.
