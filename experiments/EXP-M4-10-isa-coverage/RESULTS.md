# EXP-M4-10 — ISA parameter-coverage gaps (COVERAGE-GAPS-01 §3, ISA-1..ISA-12)

**Host:** local Apple **M4** (Apple9 AGX ISA, shared with A18 Pro). All work is compile /
extract / splice / run of **our own** MSL on the local GPU (clean-room: no Apple binary is
disassembled). Tools: `tools/agxtest` (own splice+run testbed), `tools/agx-isa` (own DB /
disassembler). Splices execute the archived (spliced) machine code, proven by
`PIPELINE_SOURCE archive`.

**Status after this experiment:** round-trip **GREEN** (`tools/agx-isa/roundtrip_test.py`
ALL PASS); census **97.4%** byte coverage (M4 corpus), up from 97.3% (the fma length fix
below resolved a small corpus desync). DB edits: `isadb.py` length rule (sat/abs fma),
texture variant enum (+3 read codes), device_store data-reg annotation.

Per-gap evidence lives in each sub-dir's `logs/EVIDENCE.txt`.

---

## ISA-1 [HIGH] — High-register (r16–r95) operand-field encodings — CONFIRMED (+1 correction)
Dir: `isa1-highreg/` (kernels + `cpsweep.py`/`idxsweep.py` drivers, `logs/EVIDENCE.txt`).

- **Register operand = `(reg<<1)|is32`**, an 8-bit byte (7-bit reg field) → r0..r127. r0=0x01,
  r15=0x1f, r16=0x21, r31=0x3f, r63=0x7f, r64=0x81, r95=0xbf. **CONFIRMED** for every field I
  could cleanly probe; **no mis-encoding found** in the formula.
- **device_load dst = byte+8**: splicing it (0x51=r40 → 0x11=r8) makes the load write a
  different GPR so the consumer reads stale (out→0); identity re-encode reproduces the value.
- **device_load / device_store index reg = byte+5**: splicing to **0xff (r127) hard-FAULTS**
  (`CMDBUF_ERROR`). This is a fresh, clean **refutation of the old EXP-0006 mod-64 claim** for
  this field — a 6-bit (mod-64) field would alias 0xff→r63 and read fine; it faults, so the
  high bits are real register-select bits. (RT-1a-FIX already swept +5 low → distinct GPRs.)
- **ALU-source r64–r95:** cannot be loaded with a *known* sentinel without register spilling
  (the pressure kernel spills at ~66 live values), so the full-file ALU-source distinctness is
  inherited from the already-committed **EXP-0020** (93–96 live GPRs run correctly) + **RT-7**
  (r96 mem-index faults, r96+ ALU reads 0). No new contradiction.
- **CORRECTION — device_store data register is NOT byte+8.** Two scalar stores of *distinct*
  registers both carried byte+8 = 0x11, and splicing byte+8 was **HW-inert**; the stored value
  tracked **byte+2/+3** instead (amode 0x54: byte+3 low bits = data GPR, `0x02`→reg-x, `0x00`→
  reg-y, `0xff`→fault). device_store is thus **not** field-symmetric with device_load's dst.
  Annotated on the `data_width` field in `isadb.py` (decode/length/census unaffected — the
  field is not load-bearing for tokenization, round-trip stays GREEN). Exact data-reg position
  is amode-dependent and only partially pinned (flagged, not silently "fixed" to a wrong value).

## ISA-2 [MED-HIGH] — saturate / output-clamp — CONFIRMED (native modifier bit)
Dir: `isa2-saturate/` (`logs/EVIDENCE.txt`). **Result: NATIVE, not emulated.**
- `saturate(x)` and `clamp(x,0,1)` compile IDENTICALLY to the EXTENDED float-ALU form with a
  single **output-clamp bit = byte+7 bit1 (0x02)**: fadd `09 05 1c 01 00 c0` (6B) →
  `09 05 1c 01 01 00 00 82` (8B). fp16 mirror: `10 03 1c 02 01 00 00 82`.
- **HW SPLICE PROOF native:** sat_f(0.5+1.0) → 1.0 (clamped); splice byte+7 0x82→0x80 → **1.5**
  (clamp OFF). No following min/max op is emitted — it is one modifier bit on the producing op.
- `clamp(x,lo,hi)` for general lo/hi is DIFFERENT — lowered to explicit fmax/fmin (+12B). Only
  the `[0,1]` case maps to the native bit.
- **DB length fix (this session):** the fma path also carries this tail; the old flat
  `return 8` mis-lengthed saturate-fma (10B) / abs-fma (12B). Unified to `6+2*(byte+4&3)` for
  the 0x09 and 0x10 fma branches (guard low2==0→8). Verified: plain 8 / sat 10 / abs 12.

## ISA-3 [MED] — per-operand abs/neg on 2-/3-source forms — CONFIRMED (encodings pinned)
Dir: `isa2-saturate/` (misc kernels + EVIDENCE). Byte-diff for all placements; negate splice-proven.
- **falu2** (6B): srcB-slot negate = **byte+5 bit3**; srcA-negate via operand commute; abs → 10B
  extended (byte+4=0x02), abs-enable **byte+8** (bit0 slotB / bit1 slotA).
- **fma** (8B): multiplicand negate = **byte+7 bit3**; addend negate = **byte+4 bit4**; addend
  abs = **byte+4 bit3**; src-abs → 12B (byte+4=0x83).
- **HW SPLICE PROOF:** add 5+3=8 → splice byte+5 0xc0→0xc8 → −2 (operand negated).

## ISA-4 [MED] — immediate encodings — CONFIRMED minifloat / CORRECTION integer
Dir: `misc/kernels/immf_*`,`immi_*` (byte-diff).
- **minifloat** (float-ALU imm) = byte+1 8-bit code, matches `roundtrip_test.py`'s sweep
  (1.0→0xb1 … 30→0xff); negate = byte+2 bit3; 255 & 256 compile identically (both out of range).
- **integer immediate = multi-byte little-endian (K<<1) from byte+5.** **CORRECTION:** it stays
  **INLINE at least to 65536** (immi_256/512/1024/65536 all keep the 46-byte length) — refuting
  the doc's "K≥256 materializes to a register". Negatives switch op byte0 (0x9f→0x1f)/sign path.

## ISA-5 [MED] — atomic op-codes — CONFIRMED (DB matches splice evidence)
Dir: `isa5-atomics/` (`logs/EVIDENCE.txt`, splice sweeps). All 12 op-codes splice/byte-diff
proven; the DB `atomic_rmw`/`atomic_mem` enums match EXACTLY:
add 0x20, sub 0x36, and 0x22, or 0x2c, xor 0x3e, smax 0x28, smin 0x2a, umax 0x38, umin 0x3a,
fadd 0x26, exchange 0x3c, cmpxchg 0x24, add_indexed 0x60. **Sign-straddle proven** (init=1,
v0=−1): smax→1, umax→0xFFFFFFFF, smin→−1, umin→1 ⇒ signed≠unsigned. fadd is float add (3.0f).
byte+12 selects the op in both the elected-RMW (0x54) and standalone (0x56) forms. No change.

## ISA-6 [MED-HIGH] — non-2D texture coord/index operands — CONFIRMED (+3 DB enum codes)
Dir: `isa6-texcoord/` (`logs/EVIDENCE.txt`, `texsplice.py`). op+2 dim codes & op+3 index all
splice-proven (value read back). **DB additions (this session)** — the READ-path variant enum
lacked these HW-confirmed codes, now added to `isadb.py`:
- `0x03` read 2D-array (const layer; op+3=(layer<<3)|3)   `0x37` read cube (face=(face<<1) imm)
- `0xc3` read cube-array (face imm + op+3=(array<<3)|3)
Index decode (splice-proven): array layer = op+3>>3; 3D z = coord-imm byte&0x7f; cube face =
imm>>1; MSAA sample = imm>>1; wrong dim-code silently reads base slice / 0 (robustness, no hang).

## ISA-7 [MED] — subgroup/quad dtypes — DEFERRED
Not re-probed this run. The reduce-dtype enum was already red-team-fixed (RT-5: int=0x03).
dtypes beyond int32/float and full shuffle-lane range remain byte-diff-inferred. Enumerated as
an open item; no evidence of mis-encoding surfaced in census.

## ISA-8 [MED] — matrix half-datapath accumulate byte — DEFERRED
`0xcf` fp32 datapath is splice-proven (committed); the fp16/bf16 accumulate-enable byte remains
uncharacterized (RT-10). Not addressed this run — enumerated as open.

## ISA-9/10/11/12 — DEFERRED (unchanged)
- ISA-9 (rt_intersect sub-fields splice-inert), ISA-10 (control-flow offset field widths),
  ISA-11 (half/bf16 op-set breadth), ISA-12 (SFU range-reduce sub-fields) — all remain as
  documented `⏳`/inferred in `docs/isa/`; no new probing this run. Flagged for a later pass.

---

### DB / doc changes made
- `tools/agx-isa/isadb.py`: (1) fma length now `6+2*(byte+4&3)` in the 0x09 & 0x10 groups
  (sat/abs fma 10/12B); (2) texture variant enum +0x03/0x37/0xc3 read codes; (3) device_store
  `data_width` field annotated INERT + index_reg mod-64-refutation note.
- `docs/isa/README.md`: saturate native bit, ISA-3 abs/neg map, ISA-4 integer-immediate stays
  inline, ISA-1 store-data-reg correction, ISA-6 read codes (see doc diff).
- Regenerated `db.json`, `encoding-tables.md`, `agx3.xml`; re-ran census + round-trip (GREEN).
