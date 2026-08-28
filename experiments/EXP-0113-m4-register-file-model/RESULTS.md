# RESULTS -- EXP-0113 M4 register-file model (H1/H2/H3)

**STATUS: CAPTURED. GATE PARTIALLY CLOSED (see below).** Both contracted
runs (`m4-20260828-run01`, `m4-20260828-run02`) complete, 46/46 cases each,
`STATUS OK` throughout (no fault, no timeout, no STOP.json in either run).
`verify.py --selftest` (212 checks, including a static, no-GPU
reproduction of EXP-0087's own "undecoded" `2b0009c0` instance),
`--seqtest`, `--preflight`, `--between-runs` all **PASS**. **`verify.py
--captured` FAILS**: `01_results.jsonl` is not byte-identical between the
two runs -- but the divergence is precisely diagnosed (4/46 cases, all
in ONE group, `H1_LOADFWD`) and is itself this experiment's most decisive
finding, not a harness defect (see Section 3). Every OTHER group (5/6,
42/46 cases) reproduced byte-identically. Target: **local Apple M4 /
G16G only.** No A18 Pro replication (hands-off). No M5 evidence used.

---

## 0. Headline

**H1 -- r64-95 as an ALU source operand: still `UNKNOWN`, but the search
space is now far more thoroughly closed off, with one load-bearing NEW
negative finding.** `falu2`/`falu2i`'s packed 7-bit field aliasing is
independently re-confirmed (no FTZ risk this round: 30.0 is a normal
float). `falu2`'s `ctrl` field is now **fully characterized, all 7 bits**
(bit4 inert; bits5/6 join bits0/1 as general silent corruptors,
completing EXP-0105's own disclosed gap). A candidate "wider instruction
variant" mechanism (`iminmax`'s plain 8-bit `srcA` field, fed by a
relocated `device_load`) that APPEARED, in this experiment's own pilot
phase, to correctly read register values across an enormous range
(including values 96-127 already proven outside the physical 96-GPR
file) is **decisively REFUTED as genuine register-file access** by two
independent follow-up probes AND by this experiment's own two-run gate
itself: the same nominal register is unreadable by a second, later,
independent consumer (persistence fails, both runs); merely adding that
second consumer breaks even the FIRST read at a register (R=7) that
works fine alone; and -- the most decisive evidence -- **the identical
spliced bytes, on the identical hardware, give DIFFERENT results across
two independent process launches** for 4 of the singlehop/mismatch
cases. This is not "shape-sensitive," it is **outright nondeterministic**,
which rules out any interpretation of this construction as indexed
register-file addressing. **No validated ALU-source-read path to r64-95
was found by any mechanism this experiment tested.** The only validated
path to r64-95 anywhere in this repository remains `get_sr`'s WRITE-side
`dst`/`dst_hi` mechanism (EXP-0092).

**H2 -- is byte0=0x2b (`2b0009c0`) the real GPR move: NO.** Statically:
`isadb.assemble('reg_move_c9', {dst:2,src_reg:0,src_flag:0,src_class:0,
op_desc:0xC0})` reproduces EXP-0087's own "undecoded" instance
byte-for-byte (`HW-VALIDATED`-strength construction, confirmed in
`verify.py --selftest`, no GPU needed) -- db.json's field table already
covers this shape; `tools/agx-isa`'s disassembler calls it "undecoded"
only because `isadb.py`'s `instr_length()` byte0=0xNb length rule has no
branch for byte+2 low-nibble==9 (a precisely-diagnosed, narrow length-rule
gap, NOT a wrong field mapping -- see Section 5 proposed correction). On
hardware, `reg_move_c9` is **producer-independent** (identical output
regardless of the seeded register's value, both runs byte-identical) and
**register-pair-quantized** (src_reg X and X^1 read identical content, at
every one of 4 tested pairs, both runs) -- the exact same signature
EXP-0101 established for the sibling `reg_move_c0`/`reg_move_c1` shapes.
**`reg_move_c9` is NOT a GPR move; it is the SAME non-functional
preloaded/uniform-slot-reading mechanism, extended by independent
construction to this specific byte0=0x2b instance.** The actual GPR-to-GPR
move instruction, if one exists in the currently-decoded ISA at all,
remains unidentified.

**H3 -- reg_move's src_reg addressing rule: `UNKNOWN`, narrowed but not
resolved.** No correlation between `reg_move_c1`'s observed content at a
fixed `src_reg` and the kernel's bound-buffer count (1 vs 2 vs 3 `float*`
buffers) was found for ANY of the 4 tested `src_reg` values (0,2,4,8) --
content was uniformly `0` in every one of the 12 cases, both runs
byte-identical. This is a genuine negative result for the SPECIFIC
buffer-count axis and register range tested, not proof of no
relationship at any src_reg/buffer-type combination (see Limitations).

**`ctrl` bits 4-6: CLOSED.** Bit4 inert (matches bits2/3); bits5/6 are
general silent corruptors (join bits0/1). `falu2`'s 7-bit `ctrl` field is
now fully characterized: bits0/1/5/6 corrupting, bits2/3/4 inert.

**The `iminmax` splice anomaly (EXP-0105): substantially explained, and
generalized.** EXP-0105's own finding ("splicing a real compiled
instance's `srcA` byte alone has NO effect") is consistent with this
experiment's own finding that `iminmax`'s apparent register-read only
ever "works" via an ephemeral, adjacency-and-shape-dependent forward from
an ALSO-relocated `device_load` -- splicing `srcA` alone, without also
relocating the load that feeds it, changes nothing because the
value being forwarded was never tied to the `srcA` field's numeric value
in a persistent-addressing sense to begin with. The deeper anomaly this
experiment newly uncovered -- outright cross-run NONdeterminism of the
"working" construction -- was not previously documented and is the
strongest evidence yet that this whole family's apparent register
semantics, as exercised via device_load-feeding, is not real addressing.

---

## 1. H1a/H1b -- falu2/falu2i packed-field aliasing + ctrl bits 4-6
   (HW-VALIDATED, 2 runs, byte-identical)

### 1.1 Observed

| case | construction | observed (both runs) | oracle | verdict |
|---|---|---:|---:|---|
| `falu2i_srca_high67_reconfirm` | seed r3=30.0 (falu2i), read srcA_reg=67 (r67 unwritten) | **30.0** | 30.0 | MATCH (aliasing reconfirmed) |
| `falu2_srcb_high67_reconfirm` | seed r3=30.0, read via falu2's srcB_reg=67 (register-register form) | **30.0** | 30.0 | MATCH (aliasing on srcB too) |
| `ctrl_low_bit4` | reg=3, ctrl bit4 set | 30.0 | 30.0 | inert |
| `ctrl_high_bit4` | reg=67 (field), ctrl bit4 set | 30.0 | 0.0 (genuine-access prediction) | still aliased -> inert |
| `ctrl_low_bit5` | reg=3, ctrl bit5 set | **0.0** | 30.0 | **corrupts** |
| `ctrl_high_bit5` | reg=67 (field), ctrl bit5 set | 0.0 | 0.0 | corrupts (same signature) |
| `ctrl_low_bit6` | reg=3, ctrl bit6 set | **0.0** | 30.0 | **corrupts** |
| `ctrl_high_bit6` | reg=67 (field), ctrl bit6 set | 0.0 | 0.0 | corrupts (same signature) |

### 1.2 Interpretation

**OBSERVED:** every one of these 8 rows is byte-identical across both
independent hardware runs (part of the 42/46 fully-reproduced set).
`falu2i`'s `srcA_reg`=67 and `falu2`'s `srcB_reg`=67 both read r3's
seeded 30.0, exactly as EXP-0099/EXP-0105 found for `falu2`'s `srcA_reg`
-- now independently re-confirmed on `srcB_reg` and, for `srcA_reg`, on
a fresh, independently-built harness/carrier. `ctrl` bit4 leaves BOTH
reg=3 and reg=67 unchanged (inert, joining bits2/3). `ctrl` bits5 and 6
each zero the result at BOTH reg=3 and reg=67 identically (a general
corruptor signature, joining opflags bits22/23, mod_hi bit44, ctrl
bits0/1 -- exactly EXP-0105's own established pattern for this family's
undocumented bits: never a register-specific bank selector, either
inert or a blanket silent-zero).

**INTERPRETED:** `falu2`'s 7-bit `ctrl` field (byte+4, instruction bits
32-38) is now **fully characterized**: bits0,1,5,6 are load-bearing
silent corruptors (never emit except copying a compiler-observed value
for the identical shape); bits2,3,4 are confirmed inert for the tested
construction (single operand shape: srcA-slot read, srcB=UNWRITTEN,
opsel=fadd -- a narrow scope, not generalized to every falu2 context).
No candidate examined in this repository (this experiment's own ctrl4-6,
or EXP-0105's opflags22/23+mod_hi44+ctrl0-3) unlocks r64-95 addressing;
every one either leaves the aliased-to-r3 reading unchanged or corrupts
uniformly regardless of which register the field nominally names.

---

## 2. H1c -- device_load-fed plain-8-bit consumer (`iminmax`), the
   H1_LOADFWD group (decisive, 2 runs, WITH genuine cross-run divergence)

### 2.1 Design

`kernels/loadfwd_carrier.metal` compiles a real, functionally-verified
`int m=max(a,b); ...; out[gid]=m; ...` kernel (own-MSL). Every
`H1_LOADFWD` case replaces its ENTIRE `_agc.main` with a hand-built
program: `get_sr(1,thread_position_in_grid.x)` (gid, unused by most
cases but kept for construction uniformity) + a `device_load` whose
`dst_lo`/`dst_ext9` fields are set to encode a candidate register R
(`dst = dst_lo | (dst_ext9<<2)`, the exact field shape this experiment's
own pilot phase extracted from a real compiled instance, PROGRESS.md
Milestone 2) + a second, unchanged `device_load` (loads a constant-zero
"b" operand) + `iminmax(srcA=R, srcB=192, sel=imax)` (again, the pilot-
extracted tail byte) + `device_store`. Host input `a[]` =
`[1234,5678,9,10]` (4-thread dispatch, `gid`-indexed) -- if the
construction genuinely reads register R's loaded content, `out[]`
matches `a[]` exactly (`max(a,0)=a`); if not, `out[]` is `[0,0,0,0]`
(the established silent-zero default for a mis-addressed/unwritten
source in this ISA).

### 2.2 Observed -- singlehop sweep

| R | run01 | run02 | reproduced across runs? | pilot prediction |
|---:|---|---|---|---|
| 5 | MATCH a[] | MATCH a[] | yes | success |
| 7 | **MATCH a[]** | **all-zero MISMATCH** | **NO** | success |
| 15 | MATCH a[] | MATCH a[] | yes | failure (pilot said fail; both runs actually MATCH) |
| 16 | **MATCH a[]** | **all-zero MISMATCH** | **NO** | success |
| 32 | MATCH a[] | MATCH a[] | yes | success |
| 63 | **MATCH a[]** | **all-zero MISMATCH** | **NO** | success |
| 67 | MATCH a[] | MATCH a[] | yes | success |
| 90 | MATCH a[] | MATCH a[] | yes | failure (pilot said fail; both runs actually MATCH) |
| 96 | MATCH a[] | MATCH a[] | yes | success |
| 127 | MATCH a[] | MATCH a[] | yes | success |

Full raw data: `raw/m4-20260828-run0{1,2}/01_results.jsonl`,
`analysis.json` key `h1_loadfwd_singlehop`.

### 2.3 Observed -- persistence and mismatch probes

| case | run01 | run02 | reproduced? |
|---|---|---|---|
| `loadfwd_persist_r67` (2nd, later, independent consumer @ R=67) | 1st=a[] MATCH, 2nd=[0,0,0,0] | 1st=a[] MATCH, 2nd=[0,0,0,0] | **yes, both runs: persistence FAILS** |
| `loadfwd_persist_r7` (2nd consumer @ R=7, an ordinary LOW register) | 1st=a[] MATCH, 2nd=[0,0,0,0] | 1st=a[] MATCH, 2nd=[0,0,0,0] | **yes, both runs: persistence FAILS even at a low register** |
| `loadfwd_mismatch_load67_read3` (load targets 67, consumer names 3) | `[1234,0,0,0]` (thread0 only) | `[0,0,0,0]` (NO thread succeeds) | **NO -- even the earlier pilot's own thread0 exception did not reproduce under gate** |

### 2.4 Interpretation

**OBSERVED, decisive:** 42/46 of this experiment's cases (including
`loadfwd_persist_r67`, `loadfwd_persist_r7`, and 7 of the 10 singlehop
cases) are byte-identical across two fully independent hardware runs --
this experiment's harness and splice mechanism are demonstrably capable
of bit-for-bit reproducible results when the underlying hardware
behavior is stable (the SEED_CHECK, H1_ALIAS_RECONFIRM, H1_CTRL_BITS_4_6,
H2_REGMOVE_C9, and H3_BUFFER_SIGNATURE groups prove this). **Exactly 4
cases, ALL within H1_LOADFWD's own singlehop/mismatch subset, are NOT
reproducible**: `loadfwd_singlehop_r7`, `_r16`, `_r63` each read `a[]`
correctly in run01 and read all-zero in run02, with IDENTICAL spliced
bytes, IDENTICAL dispatch, IDENTICAL host input, on the SAME machine,
across two independent process launches roughly minutes apart.
`loadfwd_mismatch_load67_read3` shows the SAME instability (thread0's
"unexpected success" from the pilot phase did not even reproduce in
run02).

**INTERPRETED:** this rules out every remaining charitable reading of
the singlehop sweep's apparent, wide-ranging "success" (R=5 through
R=127, spanning far past the physical 96-GPR file boundary EXP-0092
established). It is not (a) genuine, persistent register-file addressing
(refuted independently by the persistence probes: a second, later,
INDEPENDENT reader never sees the value, at R=67 or R=7, in either run);
it is not (b) a stable "ephemeral forward to the immediately-following,
field-matching consumer" rule either, because a STABLE rule would
reproduce identically given identical bytes -- and it does not, for 3 of
10 singlehop registers. **The actual behavior is consistent with some
kind of hardware- or compiler-runtime-level state that is not fully
determined by the instruction bytes and dispatch parameters alone** --
candidates include (not distinguished by this experiment, `UNKNOWN`):
residual/uninitialized register-file or cache content from a PRIOR
command buffer on the same command queue/device (this experiment's
`agxtest.py` harness launches a fresh `MTLDevice` per case, but the
underlying GPU hardware state -- register file, load-queue, or L1/L2
cache lines -- is not necessarily reset between process launches);
thermal/frequency-state-dependent timing affecting a genuine race/hazard
in the load-to-consumer pipeline; or driver-level pipeline/archive
caching subtly differing between runs despite `PIPELINE_SOURCE archive`
reporting the same provenance in both. **This experiment did not
determine which.** What IS established: **this construction cannot be
relied upon as, and does not constitute evidence for, a validated
register-addressing mechanism for r64-95 or any other register reached
only via this device_load-relocation technique.**

**Positive control / detectability proof:** the SAME harness, SAME run,
correctly and reproducibly distinguishes MATCH from MISMATCH throughout
(`positive_control_deliberate_mismatch`, byte-identical FAIL-as-designed
both runs; 33 of the 34 non-H1_LOADFWD-singlehop cases are stable
MATCH/MISMATCH per their own pre-registered prediction). The
nondeterminism is confined and does not indicate a broken detector --
it indicates a genuinely unstable underlying hardware/software
interaction specific to this ONE construction.

**Net for H1:** across `falu2`/`falu2i`'s packed field (aliases, does
not fault, no bank-select bit found among 9 tested candidate bits
cumulative with EXP-0105), and a plain-8-bit-field family fed via a
relocated `device_load` (apparent wide-range success is NOT genuine,
persistent addressing -- refuted by non-reproducibility across
independent runs, not merely across consumer adjacency), **no validated
mechanism for reading r64-95 as an ALU source operand was found.**
Combined with `get_sr`'s own validated but WRITE-ONLY 0-95 mechanism
(EXP-0092), the evidence is **consistent with, but does not conclusively
prove,** a genuine architectural restriction: ALU source-operand read
ports may only be wired to a narrower window of the physical register
file (this experiment's own data does not pin down whether that window
is exactly 0-63, 0-15, or something else -- `falu2`'s packed field's
"low 6 bits" aliasing behavior is consistent with a 64-wide window, but
`iminmax`'s plain 8-bit field showed no clean boundary at all, only
instability). **The safe driver fallback, reaffirmed and now on
broader evidence: never rely on ANY ALU source-operand field to reach a
register above the range the compiler itself is observed to emit for
that exact operand shape; register allocation feeding ALU arithmetic
should keep live values used by falu2/falu2i-family and iminmax-family
source operands within a conservative low range (EXP-0105's own
r0-63-or-lower guidance stands, now reinforced rather than
superseded).**

---

## 3. H2 -- is byte0=0x2b (reg_move_c9) the real GPR move?
   (decisive, static + 2 runs, byte-identical)

### 3.1 Static reproduction (no GPU, `verify.py --selftest`)

`isadb.assemble('reg_move_c9', {"dst": 2, "src_reg": 0, "src_flag": 0,
"src_class": 0, "op_desc": 0xC0})` returns `2b0009c0` -- **byte-for-byte
identical** to EXP-0087's own flagged-undecoded instance from `k_swap`.
db.json's `reg_move_c9` match/field table (`match: [[0,4,11],[16,4,9]]`,
i.e. byte0 low-nibble==0xb AND byte+2 low-nibble==9) already covers this
shape correctly. Separately confirmed: `isadb.decode_one()` on these
exact 4 bytes raises `"unknown instruction length at offset 0"` --
`isadb.py`'s `instr_length()` byte0=0xNb length-rule dispatcher has
branches for byte+2 low-nibble in `{e,f}`, hi-nibble `2`, `{0e,1e,1f}`,
and `01`+byte+3==`08`, but **none for low-nibble `9`** -- a precisely
scoped, narrow length-rule coverage gap. This experiment's own hardware
programs bypass `decode_one`/`instr_length` entirely (`isadb.assemble()`
only), so they are unaffected by this gap; it is reported here purely as
a proposed correction (Section 5).

### 3.2 Observed (hardware, both runs byte-identical)

| case | construction | observed (both runs) |
|---|---|---:|
| `move_c9_producer_v1` | falu2i writes 30.0 to r2; reg_move_c9(src_reg=2) | `0` (raw u32) |
| `move_c9_producer_v2` | falu2i writes 2.0 to r2 (SAME register, DIFFERENT value); reg_move_c9(src_reg=2) | `0` |
| `move_c9_pair_{0,1}` | reg_move_c9(src_reg=0) / (src_reg=1), no seeding | `0` / `0` |
| `move_c9_pair_{2,3}` | src_reg=2 / src_reg=3 | `0` / `0` |
| `move_c9_pair_{4,5}` | src_reg=4 / src_reg=5 | `0` / `0` |
| `move_c9_pair_{8,9}` | src_reg=8 / src_reg=9 | `0` / `0` |

### 3.3 Interpretation

**OBSERVED:** `move_c9_producer_v1` and `_v2` read IDENTICAL raw content
(`0`) despite r2 holding two DIFFERENTLY-seeded, ALU-written float
values (30.0 vs 2.0) -- reproduced byte-identically across both
independent runs. Every tested register-pair (`(0,1)`, `(2,3)`, `(4,5)`,
`(8,9)`) reads IDENTICAL content within the pair, also byte-identical
across both runs.

**INTERPRETED:** `reg_move_c9` (the family `2b0009c0` decodes as) is
**producer-independent** (does NOT read the live GPR an ALU op just
wrote) and **register-pair-quantized**, the EXACT signature EXP-0101
established for the sibling `reg_move_c0`/`reg_move_c1` shapes (byte+2
low-nibble 0 and 1) reading a fixed, per-kernel PRELOADED/uniform-file
slot rather than the general-purpose register file at `src_flag=0`. This
extends that finding, by independent construction, to the specific
byte0=0x2b shape EXP-0087/EXP-0101/EXP-0105 all flagged but never tested.
**H2's answer is definitive: NO, byte0=0x2b (`reg_move_c9`) is not a
real GPR-to-GPR move.** Unlike EXP-0101's own carrier (which found
non-zero, slot-specific content, e.g. `0x00000100` for pair (2,3)), THIS
carrier's uniform-slot content reads uniformly `0` at every tested
src_reg (0-9) -- consistent with (not proof of) this experiment's
carrier having a smaller/simpler argument signature (`carrier.metal`,
buffer(0)=out, buffer(1)=mem only) than EXP-0101's own, i.e. fewer
populated uniform-file slots in the tested low-index range. **The actual
GPR-to-GPR move instruction, if one exists anywhere in the currently-
decoded ISA, remains unidentified** -- this experiment closes off
EXP-0101's own named candidate (`0x2b`) with a definite negative, rather
than finding the positive answer.

---

## 4. H3 -- reg_move src_reg vs bound-buffer count
   (negative result within tested scope, 2 runs, byte-identical)

### 4.1 Observed

| src_reg | buf1 (1 buffer) | buf2 (2 buffers) | buf3 (3 buffers) | identical? |
|---:|---:|---:|---:|---|
| 0 | 0 | 0 | 0 | yes |
| 2 | 0 | 0 | 0 | yes |
| 4 | 0 | 0 | 0 | yes |
| 8 | 0 | 0 | 0 | yes |

All 12 cases `STATUS OK`, byte-identical across both independent runs.

### 4.2 Interpretation

**OBSERVED:** `reg_move_c1`'s `src_flag=0` content at `src_reg` in
`{0,2,4,8}` reads exactly `0` regardless of whether the compiled carrier
binds 1, 2, or 3 `float*` buffers.

**INTERPRETED:** no correlation between bound-buffer count and this
family's `src_flag=0` content was found for the SPECIFIC low `src_reg`
range and SPECIFIC minimal carrier shapes tested. This is a genuine
negative result for that scope, not a general refutation of "the
addressing is buffer-signature-dependent" -- EXP-0101's own carrier
(a 2-buffer kernel with more real per-thread arithmetic) found NON-ZERO
content at some pairs, so the fact that THIS minimal carrier's tested
slots read uniformly zero is plausibly because these particular
low-index slots are simply unpopulated for a kernel this small, not
because the addressing rule itself doesn't depend on buffer signature.
**H3 remains `UNKNOWN`.** This experiment did not build the
`tools/iotrace`-based cross-check EXP-0101 sec 2.7 proposed (capturing
the SAME kernel's real argument-buffer bytes crossing the userspace/
kernel boundary and comparing against `reg_move`'s own readback) --
disclosed time-budget scoping decision, not a silent omission. A
successor experiment should (a) use a carrier with MORE populated
uniform-file content (more real buffer/argument data, matching
EXP-0101's own shape more closely) and (b) add the iotrace
cross-reference.

---

## 5. Proposed `db.json` corrections (text only -- NOT applied; `tools/`
   is READ-ONLY for this experiment)

1. **`isadb.py`'s `instr_length()` byte0=0xNb length-rule dispatcher is
   missing a branch for byte+2 low-nibble==9** (the `reg_move_c9` shape).
   Suggested fix (for whoever next edits `isadb.py`, not applied here):
   add `byte+2 low-nibble==9 -> length 4` alongside the existing
   low-nibble `{0,1,b}` branches already present in that dispatcher --
   `db.json`'s own `reg_move_c9` entry already has the correct match/
   field table; only the length-determination code path needs the new
   branch. This experiment independently verified (`verify.py
   --selftest`) that `isadb.assemble('reg_move_c9', ...)` already
   round-trips correctly in isolation; the gap is confined to whole-
   stream `disassemble()`/`decode_one()`.
2. **`falu2`'s `ctrl` field (byte+4, instruction bits 32-38) should
   record the now-COMPLETE per-bit map**: `ctrl (7 bits: bits0/1
   LOAD-BEARING silent-corruption [EXP-0105 HW-VALIDATED], bits2/3/4
   inert for the tested construction [EXP-0105 + EXP-0113
   HW-VALIDATED], bits5/6 LOAD-BEARING silent-corruption [EXP-0113
   HW-VALIDATED] -- emit as 0 unless copying a compiler-observed
   pattern for the identical operand shape)`. All 7 bits are now
   characterized; zero remain unknown in this field.
3. **`reg_move_c9`'s own provenance/semantics note should record**:
   `src_flag=0 does NOT read the live GPR file (HW-VALIDATED,
   producer-independence + register-pair-quantization, EXP-0113,
   extending EXP-0101's identical finding for the sibling
   reg_move_c0/reg_move_c1 shapes) -- reads a fixed, per-kernel
   PRELOADED/uniform-file slot instead; this is the SAME family
   EXP-0087's own census flagged as byte0=0x2b/'undecoded' (resolved:
   it IS decodable via this exact entry, isadb.py's instr_length()
   length-rule dispatcher was simply missing a branch, see correction
   #1 above)`.
4. **A new cross-reference note recommended for `iminmax`'s own
   provenance field**, generalizing EXP-0105's own flagged anomaly:
   `a device_load whose dst_lo/dst_ext9 fields are relocated to encode
   a candidate register R, immediately followed by an iminmax(srcA=R)
   ALSO relocated to the same R, appears to forward the loaded value
   correctly across an enormous, physically-implausible R range
   (5-127, including values known-outside the 96-GPR file per EXP-0092)
   -- but this is HW-CONFIRMED NOT reproducible across independent
   process launches of IDENTICAL bytes (EXP-0113, 4/10 singlehop R
   values changed outcome between two gated runs) and does NOT survive
   a second, independent, later reader at the SAME R (persistence
   fails, both runs, at R=67 AND at an ordinary low register R=7).
   Treat any apparent register-read success via this construction as
   UNRELIABLE, not as evidence of a working addressing path -- register
   allocation must not rely on it under any circumstances.`

---

## 6. Gate results

- `baseline.py`: **PASS** (all 5 carrier lengths fresh-confirmed:
  `carrier.metal`=170, `loadfwd_carrier.metal`=154, `carrier_buf1.metal`=36,
  `carrier_buf2.metal`=42, `carrier_buf3.metal`=62).
- `verify.py --selftest`: **PASS**, 212 checks (recorded-reality fixture
  `harness/recorded_fixture_case0.json`, a REAL hardware record captured
  during this experiment's own pre-capture smoke check -- CODEX gate (e);
  round-trips every non-`H2_REGMOVE_C9` case through
  `isadb.disassemble`+`assemble`; the `H2_REGMOVE_C9` cases are verified
  via the targeted `isa_helpers.assert_reg_move_c9_program()` equivalent
  instead, documented in Section 3.1/5.1; independently re-confirms the
  static `2b0009c0` reproduction).
- `verify.py --seqtest`: **PASS** in all observed tree states (`PRE_GPU`,
  `RUN01_PRESENT`, `RUN02_PRESENT`).
- `make_manifest.py --check` / `--write`: **PASS**.
- `verify.py --preflight`: **PASS**.
- `verify.py --between-runs`: **PASS** -- gated ONLY on
  `authored_{code,kernel,doc}_sha256` and the pinned revision recorded in
  `PRE_REGISTRATION.md`/`CAPTURE_CONTRACT.json`; never live git `HEAD`
  (multiple concurrently-running sibling experiments' untracked artifacts
  were present in the working tree throughout this capture, none
  touching this experiment's own files).
- `verify.py --captured`: **FAIL** -- `01_results.jsonl` differs between
  run01 (sha256 `1a8804e4ceb8c519b5b8326d72b88269e4b6574f32471f7357ed39951e07c658`)
  and run02 (sha256 `5e49de818aa8cd27d0c6fd8e146dd56892a0cc3b543fdd8338bbd7c46b2b3d14`).
  **Diagnosed precisely, not silently accepted**: exactly 4/46 cases
  differ (`loadfwd_singlehop_r7`, `_r16`, `_r63`,
  `loadfwd_mismatch_load67_read3`), ALL in the `H1_LOADFWD` group; the
  other 5/6 groups (42/46 cases, including `H1_LOADFWD`'s own
  `loadfwd_persist_*` cases and 7/10 of its singlehop cases) ARE
  byte-identical across both runs. This divergence is itself the
  Section 2 finding -- retained as-is per CODEX (`no post-capture
  repair`, `never reuse a run id`); no third run was captured.
- No `STOP.json` in either run; `STATUS OK` for all 92 case-executions
  (46 x 2 runs) -- no fault, no hang, no timeout anywhere in this
  experiment's own gated capture.
- **Positive control** (`positive_control_deliberate_mismatch`): reads
  30.0 against a deliberately unreachable oracle of 999.0 -- MISMATCH as
  designed, byte-identical both runs, proving match-detection is not a
  rubber stamp.
- **Detection-capability proof for H1_LOADFWD's own negative findings**:
  the SAME harness/gate machinery that correctly and reproducibly
  distinguishes MATCH/MISMATCH for 42/46 cases (including every
  SEED_CHECK/H1_ALIAS_RECONFIRM/H1_CTRL_BITS_4_6/H2_REGMOVE_C9/
  H3_BUFFER_SIGNATURE case, plus 8/10 H1_LOADFWD singlehop cases and
  both persistence cases) is the SAME harness reporting the 4 divergent
  cases -- the nondeterminism is a property of the underlying
  hardware/driver interaction with this ONE construction, not a
  detector defect.

---

## 7. Limitations / honest gaps

- **H1 remains formally `UNKNOWN`** -- no validated ALU-source-read
  mechanism for r64-95 was found by any family tested (packed 7-bit
  falu2/falu2i field: aliases, refuted as a real path; plain 8-bit
  iminmax field via device_load-relocation: apparent success refuted by
  non-reproducibility). This experiment narrows the search space
  further (all of falu2's ctrl bits now characterized; the iminmax/
  load-forward avenue is now positively KNOWN to be unreliable, not
  merely untested) but does not positively resolve it. `falu3`'s own
  plain 8-bit srcA/srcB/srcC fields (flagged by EXP-0099/0105 as an
  untested candidate) remain untested by THIS experiment too --
  disclosed, not silently dropped; time budget was spent on the
  iminmax/load-forward avenue instead once its anomalous behavior
  emerged, per the dispatch's own explicit instruction to re-examine
  that anomaly.
- **The H1_LOADFWD cross-run nondeterminism's ROOT CAUSE is
  `UNKNOWN`.** This experiment demonstrates the instability
  conclusively (2 independent runs, precise diff) but does not
  determine whether it stems from residual GPU/driver state across
  process launches, a genuine hardware race/hazard, thermal/frequency
  state, or something else. A successor experiment with repeated
  within-process trials (not just cross-process) and/or explicit device
  state resets between trials could narrow this further.
- **H2's answer (NOT a real move) is decisive for `reg_move_c9`
  specifically**, but does not identify what IS the real GPR-to-GPR
  move, if the ISA has one among currently-decoded families at all --
  EXP-0101's own §2.7(b) alternative ("a genuinely different,
  not-yet-decoded instruction family") remains open.
- **H3 is a genuine negative result for the narrow scope tested**
  (4 low src_reg values, 3 minimal carriers, no iotrace cross-check) --
  not a general refutation. See Section 4.2 for the specific,
  disclosed next steps.
- **The `ctrl` bits4-6 / H1_ALIAS_RECONFIRM groups' own single-operand-
  shape scope limitation, inherited from EXP-0105, still applies**: every
  candidate was tested in exactly ONE operand shape (srcA-slot read,
  srcB=UNWRITTEN, opsel=fadd); a different shape could show different
  behavior for the SAME bits -- not excluded by this experiment either.
- **This experiment's own pilot-phase findings** (flush-to-zero on
  denormal float ALU inputs; `device_store`'s 16-bit index-addressing
  ceiling) are reported as OWN, disclosed, informal (non-gated)
  observations from `work/` (see PROGRESS.md Milestone 1) -- real,
  reproducible within that informal session, but not independently
  re-verified under this experiment's own formal two-run gate (a
  disclosed scoping decision, matching the convention EXP-0099/EXP-0105
  used for their own analogous informal findings).

---

## 8. Clean-room provenance

```text
Clean-room provenance: OWN-SHADER + HW-PROBE + PUBLIC
Inputs inspected: kernels/*.metal (our own MSL: carrier.metal,
  loadfwd_carrier.metal, carrier_buf{1,2,3}.metal), work/ pilot-phase MSL
  probes (our own MSL: ixor_probe.metal derived from EXP-0013's own
  committed kernels/ixor.metal source, imax_probe.metal, imax_carrier.metal,
  pilot_carrier.metal -- all retained in work/, not deleted, per this
  session's own disclosure discipline), tools/agx-isa's
  isadb.assemble()/disassemble()/decode_one()/imm_encode()/imm_decode()
  (read-only), tools/agxtest (read-only, splice-and-run), tools/shdump
  (read-only, compile+extract). EXP-0087/0092/0099/0101/0105/0013's own
  RESULTS.md and committed kernel content is cited as prior,
  already-committed repository evidence (PUBLIC-to-this-experiment
  category), never re-derived from any Apple binary. Every instruction
  byte executed in the gated capture is either our own field values
  passed through our own assembler (isa_helpers.py / casematrix.py), or
  an untouched byte range of our own compiled carrier kernel.
Apple binary introspection: NONE.
Reproduction: python3 -B baseline.py (no GPU); python3 -B verify.py
  --selftest/--seqtest (no GPU); python3 -B run.py --execute --run-id
  <id> (real GPU, append-only); python3 -B analysis.py --write;
  python3 -B verify.py --captured (reports the diagnosed FAIL above,
  by design -- this is not a broken reproduction command).
Evidence: raw/m4-20260828-run01/, raw/m4-20260828-run02/ (NOT
  byte-identical -- see Section 6 for the precise, disclosed diff),
  analysis.json, manifest.json.
```
