# RT-7 Results — falsifying the register/uniform machine model + SR/ABI

Red-team verifier. Device: Apple A18 Pro / G17P, macOS 26.6. **Reboots: 0.** All bytes
inspected/spliced/executed are our own compiled MSL (OWN-SHADER + HW-PROBE). Verdict legend:
**CONFIRMED** (survived falsification) · **DISCREPANCY** (doc is wrong; corrected fact + evidence).

---

## TL;DR verdicts
| # | Claim | Verdict |
|---|---|---|
| 1 | 96 addressable 32-bit GPRs; cap exactly 96; r96+ fault/alias | **CONFIRMED (strengthened)** |
| 2 | 16-bit halves packed 2-per-GPR; low/high addressing | **CONFIRMED** |
| 3 | Uniform register file + GPR-vs-uniform select | **CONFIRMED mechanism; DISCREPANCY in the select-bit story** |
| 4a | Spill to scratch above 96; spilled kernels correct | **CONFIRMED** |
| 4b | Occupancy tier bit (launch +0x00 bit23) flips at **~12** GPRs | **UNDER-EVIDENCED** (tier bit exists; the "12" is interpolated, not measured — could not re-pin) |
| 5 | SR-number table (all `get_sr` codes) | **CONFIRMED (no mislabels)**; one nuance on threadgroups_per_grid |
| 6 | Vertex attribute fetch = in-shader software | **CONFIRMED** |

---

## 1. "96 addressable 32-bit GPRs (r0–r95)" — CONFIRMED, strengthened

**(a) Cap is exactly 96 (metadata).** Fine `__GPU_METADATA` field-0 (GPR footprint `f0`) sweep over
K=60..256 (`raw/t1_meta_sweep.txt`): `f0` grows then **caps at exactly 96 and never exceeds it** — no
K ever produced 95, 97, 100, or 128. A kernel with **f0=93, scratch=0** (K=72) and even **f0=96,
scratch=0** (K=62) run correctly (n=1 copy exact-matches). So the usable file is exactly 96×32-bit.
(The old `maxreg_ls = byte+8>>1` heuristic is contaminated by width bits and reports >96 — ignore it;
byte+8's register sub-field is **not** `>>1`, docs already mark it ⏳.)

**(b) r96+ alias-or-fault — answered on two operand paths (`raw/t1c_regmap_K94.txt`,
`raw/t1d_alu_confirm.txt`, `raw/t1f_alias_decisive.txt`):**
- **As a memory index** (`device_load` byte+5, the RT-1a HW-validated GPR selector): r0..r95 → **OK**,
  r96..r127 → **hard FAULT** (`CMDBUF_ERROR`), a clean r95/r96 boundary. This is a *register-index-range*
  fault, not memory OOB: uninitialized registers r0..r95 read **0** (→ `a[0]=0`, OK), yet r96 faults —
  so r96 is qualitatively out of the file.
- **As a float ALU source** (`falu2` srcA byte+1, bit39=0): r0..r127 all **OK**, but r96..r127 read **0**
  (no fault). Successfully read live values from **r64** and **r66** (7-bit srcA addressing works up to
  r95), and **r64 ≠ r0** (r0 read 0 while r64 read the live value) ⇒ r0..r95 are **96 distinct** entries,
  no mod-64 aliasing.
- **No aliasing to live data was ever observed**: across every sweep, r96..r127 never returned a known
  live register's value. → r96+ does **not** alias meaningful data; it **faults** on memory-index use and
  **reads 0** on ALU-source use.

**Corrected/added fact for docs:** the "r96+ faults" expectation is **confirmed for the memory-address
path** (hard fault at exactly r96), and refined for the **ALU path** (out-of-range source reads 0, does
not fault, does not alias). This also gives positive evidence that **96 is a hard boundary**
(silicon faults at r96), addressing the docs' open "⏳ whether 96 is hard silicon or a policy cap."

## 2. "16-bit halves packed 2-per-GPR" — CONFIRMED

`raw/t2_half_sweep.txt` (fresh cyclic-FMA kernel, independent of EXP-0020): `float` vs `half` footprint —
**64 halves → f0 = 50** (exactly EXP-0020's number), ratio ≈ **0.60** across K, and **96 halves → 74**.
Impossible if a half owned a full GPR (that needs ≥64 for 64 halves). `half` also spills far later than
`float` (float spills at K=80/f0=96; half stays f0≤96 to K≈128), consistent with 2/GPR.

**Low-half addressing (splice, `raw/t2b_half_lowhalf.txt`):** in `out=x+y`, set x raw bits = `0x00003C00`
(float32 ≈ 2.15e-41 ≈ 0; low half `0x3C00` = half 1.0). 32-bit srcA → out = 0+100 = **100**; splicing the
srcA **size bit** (byte+1 bit0) 1→0 (16-bit) → out = **101** = half(`0x3C00`)=1.0 + 100. ⇒ the `0x09`
32-bit form's size bit reads the **low** halfword — HW-confirmed, as the docs claim.

## 3. Uniform register file + GPR-vs-uniform select — CONFIRMED mechanism; **DISCREPANCY** in the select-bit story

There **is** a uniform register file and a source operand selects GPR-vs-uniform (mechanism CONFIRMED:
`a[gid]+p.k` reads the **runtime** uniform — vary the bound value, out tracks it: 7→7, 55→55, 1000→1000).
But the docs' RT-1a-FIX account of *which encoding* is the uniform source is **wrong/overstated**:

**Two valid uniform-source forms coexist — one per operand position** (`raw/t3c_uniform_form.txt`,
`raw/t3d_falu2uni.txt`; the two are commutation variants — `a+p.k` puts the uniform in srcB,
`p.k+a` / fast-math puts it in srcA):

| form | example bytes | select bit(s) (splice-proven) | uniform index |
|---|---|---|---|
| **uniform as srcB** | `09 01 0c 0d 00 c2` | **byte+2 bit4 + byte+5 bit1** (toggling *either* → GPR read=0; bit39 irrelevant) | byte+3 |
| **uniform as srcA** (`falu2_uni`) | `09 0d 14 01 80 c0` | **bit39 = byte+4 bit7** (toggling → GPR read=0; byte+2 bit4 / byte+5 bit1 irrelevant) | byte+1 |

Both forms HW-read a runtime uniform. **The current compiler emits the *srcB* form (`09 01 0c 0d 00 c2`)
for the exact RT-1a kernel `struct P{float k}; a[gid]+p.k` (no-fast-math).** The documented `falu2_uni`
form only appears when the uniform is srcA (operand order `p.k+a`, or fast-math commuting `a+p.k`).

**→ DISCREPANCY:** `docs/isa/README.md` states falu2_uni (bit39) *"supersedes the earlier byte-diff guess
'float uniform-select ~ byte+2 bit4 / byte+5 bit1', which was **wrong**."* That is incorrect — the
byte+2-bit4/byte+5-bit1 form is **not wrong**; it is the valid **uniform-srcB** encoding (HW-confirmed:
reads the runtime uniform, and its select IS byte+2 bit4 + byte+5 bit1, bit39 having no effect). The docs
should describe **both** forms, not dismiss one. RT-1a-FIX's HW validation of `falu2_uni` is correct *for
the srcA case*; only the "supersedes / was wrong" framing is the error.

**Uniform count (open):** only *referenced* uniforms occupy uniform registers (on-demand allocation /
Dynamic Caching), so sweeping the index only surfaces the one bound uniform (`raw/t3b/t3c`). The index
field is 7-bit (≤128), consistent with the docs; exact file size remains ⏳ (not falsifiable with these
kernels). Runtime-uniform + the `constant_program` datapath are otherwise as documented.

## 4. Spill + occupancy tier

**(a) Spill-to-scratch — CONFIRMED** (`raw/t1_meta_sweep.txt`): scratch appears exactly when `f0` hits 96
and grows with pressure (K=104→400 B, 128→576, 192→896, 256→1280); **all spilled kernels compute
correctly** (n=1 copy exact). Scratch byte size is in `__GPU_METADATA` (field 41/14). As documented.

**(b) Occupancy tier bit "flips at ~12 GPRs" — UNDER-EVIDENCED (could not re-pin).** Via a SIGUSR1
launch-descriptor capture (`cfgcap.m` + the existing `iotrace.dylib`), I confirmed a **bit23-flipping
config-like word exists** (clear at low footprint, set at f0=20). **But the exact ~12 boundary could not
be reliably reproduced:** the one bit23-flipping location I found by value-diff (va `0x10000000000`
+`0x5298`) is **inconsistent with EXP-0020's own captures** — it reads *clear* for f0=8..14 and only sets
at f0=20 (`raw/t4_tierbit_readcfg.txt`), whereas EXP-0020's on-device capture has f0=14 **set**
(`0x00880000`). So `0x5298` is not the true CDM launch-descriptor config word; correctly reading launch
+0x00 needs full CDM-record decoding (out of this harness's clean reach without touching `tools/iotrace`).
**Caveat worth flagging in docs:** EXP-0020's own `config_correlation.txt` only spans **f0=8 (clear)** and
**f0=14 (set)** — the "clear ≤11 / set ≥12" boundary is an **interpolation** between those two points, not
a measured 11-vs-12 transition. The tier bit is real; its precise "~12 GPR" threshold is not directly
evidenced.

## 5. SR-number table — CONFIRMED (no mislabels)

**Compute codes read off from the compiler (`raw/t5a_sr_readoff.txt`)** — every documented code matches
what the compiler emits for the corresponding builtin (`out[0]=builtin` ⇒ single `get_sr`, byte1 read):
tpig.x/y/z `0xa0/a1/a2`, tpit.x/y/z `0xa4/a5/a6`, thread_index_in_tg `0xa7`, tgroup_pos `0x9c/9d/9e`,
threads_per_tg `0x98/99/9a`, threadgroups_per_grid `0xa8/a9/aa`, simd_lane `0x82`, simd_group `0x85`;
threads_per_simdgroup **folded to `mov_imm 0x20` (=32)**. All CONFIRM.

**HW-splice validation of the distinctive ones (`raw/t5b_sr_hwsplice.txt`, grid=128 tg=64):** splicing the
*value* `get_sr` byte1 makes the output become that SR's value — `0xa0`→tpig(0..127), `0xa4`→pos_in_tg(0..63),
`0xa7`→tidx(0..63), `0x98`→threads_per_tg(=64), `0x9c`→tgroup_pos(0/1), `0x82`→lane(0..31),
`0x85`→simd_group(0/1). All CONFIRM.

**Graphics codes read off (`raw/t5e_graphics_readoff.txt`):** **vertex_id `0xdd`**, **instance_id `0xd8`**
(VS), **front_facing `0xc5`**, **simd_is_helper_thread `0x84`** (FS) — all present as the compiler's
`get_sr` byte1 (FS ones use suffix byte2=`0x11`). vertex_id/instance_id independently re-confirmed by the
attribute step-function test (§6, `dd`↔`d8`). front_facing `0xc5` baseline renders back-facing (0.25),
consistent with EXP-0031's both-windings HW validation.

**Nuance (not a mislabel) — threadgroups_per_grid `0xa8`:** raw `get_sr 0xa8` spliced alone returns
**threads_per_threadgroup**, tracking `tg` exactly (`raw/t5c_tgpg_disambig.txt`); the *builtin*
`threadgroups_per_grid` is get_sr `0xa8` **+ a `device_load` + a divide** (visible as `24 a8 10 06 … 67 10 44`
in read-off), and the real builtin computes correctly (grid/tg → 256/64=4, 192/64=3; `raw/t5d`). So `0xa8`
is the code the compiler uses for that builtin (correct), but it is **not a direct SR value** — a driver
emitting a bare `get_sr 0xa8` and expecting the threadgroup count would get threads_per_threadgroup. Worth
a one-line clarification in the docs; **no code is mislabeled.**

## 6. Vertex attribute fetch = in-shader software — CONFIRMED

`raw/t6_attr.txt` (our `attrdump` harness varying a real `MTLVertexDescriptor`, diffing the extracted VS
AGX bytes). Every descriptor knob moves **specific VS bytes** — impossible if fetch were fixed-function:

| descriptor change | VS byte delta |
|---|---|
| stride 32→64 | imad stride immediate @10 `8000`→`0001` |
| attr1 offset 16→12 | 2nd load offset @39 `0402`→`8401` |
| fmt0 float3→uchar4Normalized | load width @24 `5d`→`61` (32b→8b) + added normalize/convert ALU (`a70756`/`1b`) |
| fmt1 float4→half4 | load width @38 `11`→`09` (half) + half→float converts |
| step perVertex→perInstance | index **get_sr @1 `dd`→`d8`** (vertex_id→instance_id) |

⇒ stride/offset/format/step are compiled **into** the VS; the attribute table supplies only the base
pointer (uniform `base_slot 0x03`). Fully reproduces EXP-0031's finding independently.

---

## HW-validated vs inferred
- **HW-validated (dispatch/splice/render observed):** 96 cap + correctness (§1a); r96 mem-fault / ALU-read-0
  / r64≠r0 (§1b); half 2/GPR + low-half splice (§2); uniform runtime-read + both select-bit sets (§3);
  spill correctness (§4a); all compute SR splices + graphics SR read-off (§5); every attribute knob (§6).
- **Inferred / observed-by-read-off (not per-value HW-spliced):** the full compute SR *number* set beyond the
  7 splice-checked (read off from the compiler); graphics SR *values* (codes read off; front_facing prior
  EXP-0031 HW). **Not resolved:** exact uniform-register file size; exact occupancy-tier threshold (§4b).

## Recommended doc edits (for the orchestrator)
1. **§ machine model / uniform:** correct the "byte+2 bit4 / byte+5 bit1 … was wrong / superseded" text —
   it is the valid **uniform-srcB** encoding; document **both** forms (srcB = byte+2 bit4 + byte+5 bit1;
   srcA `falu2_uni` = bit39), selected by operand position/commutation. (DISCREPANCY.)
2. **§ machine model / registers:** add that **r96+ faults on the memory-index path** and **reads 0 on the
   ALU-source path** (never aliases), i.e. 96 behaves like a hard silicon boundary.
3. **§ machine model / occupancy:** soften "clear ≤11 / set ≥12" to a tier bit whose exact threshold is
   **interpolated** between the only two measured points (f0=8 clear, f0=14 set); not directly measured.
4. **§ SR / ABI:** note `threadgroups_per_grid` is `get_sr 0xa8` **+ load + divide** (raw 0xa8 =
   threads_per_threadgroup), not a direct SR read.

## Clean-room status
Clean. Only our own MSL compiled; only our own compiled bytes / our own archive's `__GPU_METADATA`
inspected/spliced/executed. Reused OWN-SHADER tools (`shdump`/`agxparse`/`agxrun`/`agxrun_persist`/
`agxisa`) and EXP-0031's `attrdump.m` (copied, not edited); the existing `iotrace.dylib` used read-only
for the tier-bit capture attempt. Did **not** edit `docs/`, `tools/agx-isa/`, `tools/iotrace/`,
PROVENANCE, reviews/. Did not commit. `raw/` holds text logs only; `.bin` archives stayed on-device under
`~/cleanroom_work/rt7/`.
