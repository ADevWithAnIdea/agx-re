# PRE_REGISTRATION — EXP-0101 M4 synthesis blockers

**Pinned repository revision (per SUBAGENT_BRIEF.md — record and compare
against THIS value, never live `HEAD`):** `0f1af7fa1d3e21a9996c3b49d7d91f6377427225`
(tree dirty with unrelated sibling-experiment untracked artifacts at pin
time — expected and explicitly not a contamination signal per
SUBAGENT_BRIEF.md).

Target: **local Apple M4 / G16G only.** macOS 26.6.2 (build 25G82), Metal 4.
No A18 Pro (hands-off, standing directive). No M5 evidence used anywhere.

## 0. Origin and status of this document

Written **after** an extensive, honestly-disclosed pilot phase
(`PROGRESS.md` Milestones 1–6), matching the standing pattern of every
prior experiment in this family (EXP-0086/0089/0090/0099 all had an
informal pilot before their frozen, gated capture). The pilot phase used
real M4 hardware for: (a) OWN-SHADER compiler census (compile + one
UNSPLICED, unmodified dispatch per kernel — no field mutation), and (b)
field-mutation splice probes that DISCOVERED this pre-registration's
hypotheses, not merely confirmed hypotheses written in advance of any
hardware contact. This is consistent with CODEX's own acknowledged
practice for this project (an "extensive pilot phase" is explicitly
disclosed and accepted in EXP-0099's own PRE_REGISTRATION.md §0) — what
is frozen here, before the two GATED capture runs, is the exact
CASEMATRIX (byte-for-byte, per `casematrix.py`) and its PREDICTED
oracle/`expect_match` for every one of the 29 cases, verified once,
informally, before this document was written (`PROGRESS.md` Milestone 6),
and not altered afterward. No case's hex bytes or oracle were adjusted
after that informal verification.

## 1. Hypotheses under test

### H1 — Blocker 1 mechanism (`device_load` → `falu2`/`falu2i`)

**Claim:** `device_load`'s `extmode` field (db.json: untyped `mod`, byte
offset +3, bits 24–31), NOT `dst_lo`/`dst_ext9` (bits 70–78, EXP-M4-13's
own `dst = dst_lo | (dst_ext9<<2)` formula), determines which register a
later `falu2`/`falu2i` must reference (`srcA_reg`/`srcB_reg`) to read the
loaded value. Formula: `extmode = 2 * target_register` — the SAME formula
EXP-0090 already established (HW-VALIDATED, `finding_5`) for
`device_store`'s ALU-forwarded-store `extmode` field. `dst_lo`/`dst_ext9`
remain a SEPARATE, independently-required field: legality does not track
the target register at all; the one HW-confirmed-valid pair for this
experiment's `addr_mode=0x44`/`ld_format=0x11` (terminal, scalar 32-bit
load) shape is `(dst_lo=1, dst_ext9=1)`, copied verbatim from a compiled
anchor (`analysis/census.py`'s `census_load_add.metal`), not derived from
the target register.

- **Falsifier design (LOAD_FIX group):** relocate the consumer register
  via `extmode` alone (holding `dst_lo`/`dst_ext9` at the known-good
  token) across four increasingly adversarial targets (r7, matching
  EXP-0099's own failed anchor; r3, a low register; r16, the first
  register requiring the FULL 7-bit `srcA_reg` field beyond `falu2`'s own
  4-bit `dst`-nibble range; r20, well past any range prior experiments
  tried). **CONFIRMS H1** if all four read `V_LOAD=-8.5` exactly.
  **REFUTES H1** if any fails to read `V_LOAD` (the formula does not
  generalize as claimed).
- **Falsifier design (LOAD_ADVERSARIAL group):** four named constructions
  that each disturb exactly one of (a) `extmode` alone (mismatched from
  `srcA_reg`), (b) `dst_lo`/`dst_ext9` derived from the target register via
  the OLD naive formula (with `extmode` correctly set), (c)
  `dst_lo`/`dst_ext9` set to an arbitrary `(0,0)` (with `extmode` correctly
  set), (d) `dst_lo`/`dst_ext9` set to `(0,0)` even with `extmode` UNCHANGED
  at its already-correct value. **CONFIRMS H1's "both fields independently
  required" claim** if all four read something other than `V_LOAD` (a
  silent-zero failure, matching this ISA's standing failure signature per
  `docs/isa/register-move-and-liveness.md` §2.5). **REFUTES** if any of
  these "should-fail" constructions unexpectedly reads `V_LOAD` correctly
  (would mean one of the two fields is not actually load-bearing in the
  way claimed).
- **`control_dst_nibble_independent_of_srcA`:** a fifth LOAD_ADVERSARIAL
  case testing a NARROWER, orthogonal claim (`falu2`'s own `dst` nibble is
  an independent low-register write target, not required to alias
  `srcA_reg`'s low bits) that a pilot-phase over-theory briefly proposed
  and this case exists specifically to falsify. **CONFIRMS** "independent"
  if it reads `V_LOAD` correctly with `dst` deliberately NOT matching
  `srcA`'s low 4 bits.
- **`fix_extmode_reg7_falu2i` / `adversarial_falu2i_mods_naive_default`:**
  a paired positive/negative case establishing a THIRD required field
  specific to `falu2i` consuming a load-sourced register: `mods` (bits
  40–47) must be `0xC0` (the compiler's own observed value), not the naive
  `isa_helpers` default of `0`. **CONFIRMS** if `mods=0xC0` reads
  `V_LOAD+K_SMALL` correctly while `mods=0` does not.

### H2 — Blocker 2 mechanism (`reg_move`'s `0x00000100`)

**Claim:** the EXP-0087 `byte+2=0x01,op_desc=0x08` compact-move encoding,
at `src_flag=0` ("GPR mode" per its own `db.json` enum label), does NOT
address the general-purpose register file at all for this carrier —
its output is a function of `src_reg` ONLY (quantized in register PAIRS:
`src_reg` and `src_reg^1` read identically), independent of what any GPR
computed by `falu2`/`falu2i`/`device_load` actually holds. `0x00000100`
(the constant EXP-0099 found reproducibly for `src_reg∈{2,3}`) is simply
whatever a fixed, per-kernel PRELOADED/uniform-file slot holds — not a
special sentinel, not a corrupted GPR read, and not dependent on the
producer's value or instruction family.

- **Falsifier design (producer independence):** `move_replicate_baseline`
  (producer writes `V_LOW=30.0` to r2) vs. `move_producer_independence_
  altvalue` (IDENTICAL construction, producer writes `V_ALT=2.0` instead).
  **CONFIRMS H2** if both read the IDENTICAL `0x00000100` (i.e. the output
  does not track the producer's value at all). **REFUTES** if the two
  cases differ (would mean SOME dependence on the GPR's actual content
  exists, contradicting "reads a fixed slot").
- **Falsifier design (producer-family independence):**
  `move_loadsourced_independence` (r2 written by a — this experiment's own
  H1-FIXED, genuinely functional — `device_load` instead of `falu2i`).
  **CONFIRMS H2** if it ALSO reads `0x00000100` (same as the ALU-sourced
  cases). **REFUTES** if it differs (would mean the failure is specific to
  one producer family, not a general "doesn't read GPRs" fact).
- **Falsifier design (register-pair quantization + slot diversity):** four
  `move_srcreg_*` cases (src_reg 0,1 vs 4,5) predicting TWO DIFFERENT
  stable values, each pair-internally identical. **CONFIRMS** the
  pair-quantization claim if 0≡1 and 4≡5 but 0/1 ≠ 4/5. **REFUTES** if any
  pair disagrees internally (quantization claim wrong) or if 0/1 equals
  4/5 (would suggest a coarser, or no, addressing granularity).
- **Positive control (harness capability):** three `move_srcflag1_
  positive_control_*` cases (`src_flag=1`, the documented "uniform/class"
  mode) predicting the LITERAL integers 1, 2, 3 as raw bits.
  **CONFIRMS** the harness/instruction CAN read genuinely different,
  easily-distinguished content when addressing legitimately varies — this
  is what makes the producer-independence findings above meaningful rather
  than "the harness can't detect anything."
- **`move_srcclass_0x21_alu_sourced`:** retests EXP-0087's own
  explicitly-`UNKNOWN` open question (docs/isa/register-move-and-
  liveness.md §1.3, `byte+2=0x21`) against a genuine ALU-computed source.
  **CONFIRMS "not a real move"** if it reads `0x00000100` (the SAME
  uniform value as `src_class=0`) rather than `V_LOW=30.0`.
- **`move_srcreg_8_reads_zero` / `move_opdesc_sweep_zero`:** two
  boundary/extension checks (an out-of-populated-range `src_reg`; an
  `op_desc` value outside the one documented "working" value) predicting
  the standard silent-zero failure signature, extending EXP-0087's own
  byte+2/op_desc sweep (originally done on a uniform-sourced carrier) to
  this experiment's ALU-sourced one.

**H2 is explicitly NOT a "found the fix" hypothesis** — no candidate
construction in this matrix is predicted to successfully read a
GPR-computed value via `reg_move`. The falsifiable content is entirely
about the MECHANISM (fixed-slot read vs. corrupted/partial GPR read),
which is directly actionable for driver guidance ("do not use this
instruction to move computed values; its source operand does not address
the register file this program's other instructions write to") even
though it does not close the blocker.

## 2. Case matrix summary

`casematrix.py::build_cases()` — 29 cases, 4 groups (`SEED_CHECK`,
`LOAD_FIX`/`LOAD_REPLICATE`, `LOAD_ADVERSARIAL`, `MOVE_UNIFORM`). Every
case's oracle is computed independently of any GPU run: `isadb.imm_encode`/
`imm_decode` fixed points for float immediates, literal `MEM_WORDS` values
for `device_load`-sourced values, and `struct.pack`/`unpack` bit-pattern
reinterpretation for the H2 constants (established during the pilot phase
per `PROGRESS.md`, not derived from the gated runs themselves). Every case
round-trips through `isadb.disassemble`/`assemble` at matrix-build time
(`isa_helpers.assert_round_trip`, called inside `casematrix._case`).

## 3. Confirm/refute table (frozen before the two gated runs)

| case name | predicts | confirms | refutes |
|---|---|---|---|
| `fix_extmode_reg7_falu2`, `_reg3`, `_reg16`, `_reg20` | match | H1 formula generalizes across register range | H1 if ANY mismatches |
| `route_load_replicate_fail_route6` | mismatch | H1's account of WHY EXP-0099 failed (plain field mismatch, not "route") | — (a replication of a known result, not new evidence either way) |
| `adversarial_extmode_unchanged_srcA_mismatch` | mismatch | extmode/srcA_reg must agree | H1 if it matches |
| `adversarial_dstfields_naive_formula` | mismatch | dst_lo/dst_ext9 must NOT be derived from the target register | H1 if it matches |
| `adversarial_dstfields_zero_extmode_correct` | mismatch | dst_lo/dst_ext9 is not "don't care" once extmode is right | H1 if it matches |
| `adversarial_dstfields_zero_extmode_unchanged` | mismatch | disturbing dst_lo/dst_ext9 breaks the load EVEN IF extmode was already correct and untouched | H1 if it matches |
| `control_dst_nibble_independent_of_srcA` | match | falu2's dst nibble is independent of srcA's low bits | the pilot-phase over-theory, if it mismatches |
| `fix_extmode_reg7_falu2i` | match | mods=0xC0 is required for a load-sourced falu2i | — |
| `adversarial_falu2i_mods_naive_default` | mismatch | mods is NOT don't-care for falu2i | the mods finding, if it matches |
| `move_replicate_baseline`, `move_producer_independence_altvalue` | BOTH match the SAME oracle | H2 producer-value-independence | H2 if they disagree |
| `move_loadsourced_independence` | match (same oracle as above) | H2 producer-family-independence | H2 if it disagrees |
| `move_srcreg_pair01_r0`/`_r1` | match each other's oracle | H2 pair-quantization | H2 if r0 ≠ r1 |
| `move_srcreg_pair45_r4`/`_r5` | match each other's oracle, DIFFERENT from pair01 | H2 pair-quantization + slot diversity | H2 if r4 ≠ r5, or if pair45 == pair01 |
| `move_srcflag1_positive_control_{1,2,3}` | match literal int 1,2,3 | harness/instrument CAN detect real differences (validates the independence findings) | — |
| `move_srcclass_0x21_alu_sourced` | match (uniform oracle, NOT 30.0) | resolves EXP-0087's open question as "not a real move" | EXP-0087's "maybe it's a real move" possibility, if it reads 30.0 |
| `move_srcreg_8_reads_zero`, `move_opdesc_sweep_zero` | match 0.0 | extends the silent-zero pattern | — |
| `seed_r2_readback`, `unwritten_reads_zero` | match | harness sanity | — |
| `positive_control_deliberate_mismatch`, `_move` | mismatch (deliberately unreachable oracle) | match-detection is not a rubber stamp | — |

## 4. Method

- Carrier: `kernels/carrier.metal` (byte-for-byte identical to
  EXP-0099-m4-lifetime-field-model's own carrier; `CARRIER_LEN=170`,
  `SLOT_OUT=0`, `SLOT_MEM=1`, re-derived fresh by `baseline.py` before
  capture, never assumed).
- Every case: one hand-assembled AGX program (`isa_helpers.py` builders,
  each `tools/agx-isa`'s own `isadb.assemble()`), spliced over the
  carrier's compiled `_agc.main` at offset 0, run via `tools/agxtest.py` in
  its own fresh subprocess, output decoded and compared to the
  independently-computed oracle.
- Two identical, independently-executed gated hardware runs
  (`m4-20260827-run01`, `m4-20260827-run02`); promotion requires
  `01_results.jsonl` byte-identical across both.
- `analysis/census.py` (Blocker 1's compiler-census evidence) is OWN-SHADER
  static analysis + ONE unmodified/unspliced functional dispatch per
  kernel — no field under this experiment's control is varied there, so it
  is NOT part of the two-run splice gate; it is independently re-runnable
  (`python3 -B analysis/census.py --write`) and its own internal assertions
  (11/11 correspondence, both kernels functionally correct) are a hard
  fail if they do not hold.

## 5. Clean-room

Every instruction byte executed in this experiment's gated cases is
assembled from field values passed to `tools/agx-isa`'s own, READ-ONLY
`isadb.assemble()` — never a copied byte string, never derived from
inspecting any Apple binary. The two census kernels
(`kernels/census_load_add.metal`, `kernels/census_multiload.metal`) are
MSL we wrote from scratch for this experiment; the machine code inspected
from them is the compiled OUTPUT of our own source via the public Metal
runtime compiler (`newLibraryWithSource:`), never Apple's compiler binary
itself. `tools/shdump`, `tools/agxtest`, `tools/agx-isa` are read-only
throughout. No SSH, no A18 Pro contact, no M5 contact, no `macvdmtool`.
