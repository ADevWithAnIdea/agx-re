# EXP-0139 — PRE-REGISTRATION (frozen before the gated runs)

**Frozen:** 2026-08-28. **Target:** local **Apple M4 / G16G** only (macOS 26.6.2,
25G82, Metal 4). The A18 Pro is HANDS-OFF; no SSH anywhere; no M5 evidence used
or produced. **Contract:** `CAPTURE_CONTRACT.json` (authored blob hashes, raw
schema, timeouts, safety budgets, case-matrix hash).

## 1. Question

`docs/evidence-classification.md` §2 says a family is **emittable** only when
every field an emitter must fill is `hardware-run` or `isolated-byte-diff`.
Only **5 of 170** instructions clear that bar today. Integer ALU is the single
largest blocked family: **16 instructions, 137 blocking fields**, computed from
`tools/agx-isa/validation.json` against `db.json`:

| instr | blocking / total | instr | blocking / total |
|---|---|---|---|
| `iadd2` | 12 / 14 | `isel10` | 10 / 10 |
| `ibfe` | 16 / 16 | `isel10_c` | 10 / 10 |
| `ibfe_mesh_attr` | 3 / 3 | `isel8` | 8 / 8 |
| `ibfins` | 12 / 12 | `isel_reg` | 9 / 9 |
| `ibitcount` | 1 / 8 | `isel_reg8` | 7 / 7 |
| `icmp_pred` | 6 / 8 | `ishift` | 9 / 9 |
| `icmpsel` | 12 / 12 | `iunary` | 1 / 3 |
| `imad` | 15 / 15 | `iminmax` | 6 / 7 |

**The question:** for how many of those 137 fields can an emitter choose an
arbitrary value and get documented behaviour — proven by running values the
compiler would never choose, on real hardware, against a host-computed oracle?

## 2. Hypotheses (falsifiable, one per arm)

**H1 (`ibitcount.tail`).** `tail` is a pure marker: the family computes
correctly for a nonempty set of `tail` values, and `tail = 0x04` is not
uniquely required. *Refuter:* every value other than `0x04` breaks the result
(then `tail` is a hard constant and must be documented as one).
*Pre-registered falsifier case:* `tail = 2`, which EXP-0129 observed degrading
the GPR read — predicted `mismatch`.

**H2 (`iunary.operand`).** db.json's 40-bit `operand` blob is not one field: in
the 8-byte `byte0 == 0x27` space it is the SAME five one-byte sub-fields
`ibitcount` already names — `dst` (reg<<1), `op_enable`, `src` (reg<<2),
`srcdesc`, `tail`. *Expected observation:* on a program that tokenizes as
`iunary` and NOT `ibitcount` (byte+1 = 0x2d), setting operand byte 2 to `r<<2`
returns `popcount(r_r)` for every seeded r, and setting operand byte 0 to
`r<<1` relocates the result exactly as `ibitcount.dst` does. *Refuter:* the
per-byte meanings do not transfer (then `operand` really is a distinct,
undecoded coefficient word and stays `tokenization-only`).

**H3 (`iadd2`).** Building on EXP-0128's HW-VALIDATED register-mode rule
(`srcA = 0xA8` is a fixed read of **r0**; `srcB_imm = 4N` selects r*N* for
N = 0..15; subtract polarity is `rN − r0`; `dst` is a full 7-bit field), the
remaining 12 fields are either inert modifiers or carry the scattered operand
number. *`dst` model (the strong one):* `dst = (reg<<1)|size`; the sum lands in
the store's register **r6** iff the effective register is 6, where "effective"
applies EXP-0112's aliasing rule `r(R mod 64)` for R ∈ [64,112]; otherwise r6
keeps its `mov_imm` sentinel (99). This simultaneously **re-tests EXP-0112's
aliasing claim on a different instruction family**. *Refuter:* the sentinel
survives at dst = 12/13, or aliasing does not reproduce at dst = 140/141.
*Pre-registered falsifier:* `lenbit = 0` selects the 12-byte form, so the
instruction over-consumes the following `device_store`'s first two bytes —
predicted `mismatch`.
EXP-0128's own **disclosed failed refuter** (`srcB_reg_hi = 8` did NOT corrupt)
is respected: this experiment does not re-assert `srcB_reg_hi` as a register
bit; it sweeps all 128 values against a 16-register seed table so that, if the
field does select a register, the observed sum decodes *which* one.

**H4 (`ibfe`).** `offset` (6 bits) and `width` (6 bits) are literal, encoded
operands: `o = (a >> offset) & ((1<<width)−1)`, with `width = 0` and
`width ≥ 32` meaning "no mask". This is the **bare-instruction** test EXP-0102
explicitly recommended as its own follow-up ("independently assemble a bare
`ibfe` with an explicit width=32 field and splice-execute it") — EXP-0102 could
only characterise the *compiler-emitted sequence* for `extract_bits` with
runtime operands, not the raw instruction. *Refuter:* the hardware masks the
offset mod 32 (NIR's assumption), or `width = 32` is not the same as
`width = 0`.

**H5 (`ishift.shamt`).** `shamt` byte = `n << 2`; `o = a >> n` arithmetic.
*Refuter:* non-multiple-of-4 bytes still shift, or the mapping is not `n<<2`.

**H6 (`iminmax.sel`).** db.json's corpus-derived map
`0=fmax 1=fmin 4=umax 5=umin 6=imax 7=imin` is the real hardware map.
*Refuter:* any of the six disagrees with its host-computed oracle.
**Special handling mandated by the dispatch:** this family is flagged
UNVALIDATED and EXP-0113 saw run-to-run nondeterminism (4/46 cases). Every case
in this experiment — not just `iminmax` — is therefore dispatched **twice
inside one process** and the whole capture is repeated in a **second process
launch**; `rep_agree` and the run01/run02 diff are both reported. Disagreement
is a FINDING, not noise.

**H7 (`isel_reg8`, extrapolate-and-test).** `isel_reg8` appears **nowhere** in
our own compiled corpus. db.json says it "adopts the isel8 field layout".
Constructing it by rewriting the `isel8` anchor's byte+2 from `0x0f` to `0x25`
should produce an instruction the hardware accepts. *Refuter:* it faults, or it
is a no-op. Either way the result is first-class (`CLAUDE.md` Methodology).

**H8 (the remaining families: `ibfins`, `imad`, `icmpsel`, `icmp_pred`,
`isel8`, `isel10`, `isel10_c`, `isel_reg`).** For each, every db.json field is
swept densely on a live carrier. No semantic model is pre-registered where none
exists; those cases are pre-registered `predict = "unknown"` and the honest
outcome (`ok` = inert at that value / `silent_zero` / `wrong_value` / `fault`)
IS the result. **A field that is inert across its whole encodable range is a
`hardware-run` result** ("an emitter may choose any value") and is reported as
such; a field that breaks the result at some values is reported with the exact
breaking set.

## 3. Variables

- **Independent:** exactly one db.json field of exactly one instruction, per
  case. Nothing else in the program changes.
- **Controlled:** carrier source (hash-frozen), input vectors, dispatch shape,
  register seeds, timeouts, the read-only tool revisions.
- **Dependent:** the 32-bit output words read back from the carrier's own
  `device_store`, plus the command-buffer status.

## 4. Method

**Carriers.** Two styles, both authored by us:

- **SYNTH** (`kernels/carrier_dag.metal`): `_agc.main` is entirely replaced by a
  program assembled from `tools/agx-isa` field rules —
  `mov_imm` × 16 (seeding r0..r15 with distinct values, **every immediate in
  0..127**: EXP-0128 proved 128..255 silently zero and, with `iadd2`'s N=0
  self-read, produced two real GPU hangs) → the instruction under test →
  `device_store` → `stop`. Used for `iadd2`, `ibitcount`, `iunary`, i.e. exactly
  where a prior experiment already HW-VALIDATED enough of the operand map to
  build the instruction from scratch. **This is generation, not replay.**
- **NATURAL** (`kernels/ialu_probes.metal`): our own compiled MSL kernel is left
  intact and exactly ONE instruction is overwritten in place at an offset
  resolved at run time by tokenizing the carrier. Used where the operand map is
  still `corpus-correlation`/`untested`, because building from scratch there
  would conflate "the field is inert" with "I guessed the operand map wrong".
  The field is live on the output path **by construction**: the carrier's own
  `device_store` reads that instruction's result (checked per carrier in the
  pilot, `PROGRESS.md` M1).

**Anchors are never hard-coded**; `harness/anchors.py` resolves
(function, mnemonic, occurrence) → offset by tokenizing `_agc.main`, and the
resolved bytes are recorded in `raw/<run>/01_anchors.json`.

**Coverage** (FIELD-SWEEP-PROTOCOL §3.3): every field of width ≤ 8 is swept
**densely over all 2^w values**; wider fields get `{0,1,2,3,max,max−1,max−2}`,
every power of two, every `2^k − 1`, 24 evenly spaced interior points, and the
asymmetric values `0x55/0xAA/0x5A5A/0xA5A5` — never only 0/1.

**Oracles** are host-computed and independent of the GPU, and are labelled per
case: `model` (an independent computation of what the mutated field should
produce under the pre-registered semantic model) or `baseline` (the unmutated
carrier's own MSL semantics, computed in Python from the source we wrote).

**Outcome taxonomy** is exactly FIELD-SWEEP-PROTOCOL §4:
`ok | silent_zero | wrong_value | fault | hang | undecodable`. **Silent zeros
are recorded as results**, never as skipped cases.

## 5. Known confounders (and what is done about them)

1. **Metal in-process code memoization** — a library built from source has a
   fixed AIR hash whose native code the device memoizes, so a later spliced
   archive would be silently ignored. Mitigated by using `agxrun_persist`, which
   loads a fresh `MTLLibrary` from each spliced archive's own bytes
   (`newLibraryWithURL:`). Verified live in the pilot: the `dst` sweep flips
   from sentinel to sum exactly at dst = 12/13 and back at 14.
2. **A field whose value cannot reach the output proves nothing** (EXP-0129 lost
   its fragment arm this way). Every carrier's liveness was checked in the pilot
   before freezing; carriers that failed the check are not used.
3. **`mov_imm` is 7 bits** — 128..255 silently zero. `verify.py --selftest`
   hard-asserts every seed immediate is ≤ 127.
4. **Register aliasing / faults** — r(R mod 64) for R ∈ [64,112], faults at
   126/127 (EXP-0112). Folded into the `dst` model rather than avoided, so the
   sweep tests it.
5. **`iminmax` nondeterminism** (EXP-0113) — double dispatch in-run + a second
   gated run; `rep_agree` recorded per case.
6. **Our disassembler is not the authority.** A mutated instruction is often
   undecodable by `tools/agx-isa`; that is recorded, never treated as a build
   error. The hardware decides what the bytes mean.
7. **Compiler revision drift** — anchors are resolved at run time and their
   bytes hashed into the capture, so a moved anchor is visible, not silent.

## 6. Expected observations / stopping rules

- H1..H7 each have an explicit refuter above. Pre-registered `predict`
  (`match` / `mismatch` / `unknown`) is frozen in the case matrix, whose
  sha256 is in `CAPTURE_CONTRACT.json` and re-derived by both runs.
- **Safety:** per-arm hang budget **2** → that arm STOPS and is reported
  PARTIAL; global budget **6** → the run aborts. `macvdmtool` is never used.
- A capture is valid if the authored blob hashes match the contract; repo
  `HEAD` moving because a sibling experiment landed is not contamination.

## 7. Out of scope (named, not silently dropped)

- **`ibfe_mesh_attr`** — a fragment/mesh-stage packed-attribute source mode.
  There is no anchor in any compute kernel we can author, and this harness is
  compute-only. Reported `untested` with the reason; a mesh/fragment carrier
  (`tools/agxtest/agxrender.m`) is the named follow-up.
- **A18 Pro replication** — hands-off by user directive.
- Anything about M5.

## 8. Clean-room provenance

```
Clean-room provenance: HW-PROBE + OWN-SHADER
Inputs inspected: kernels/*.metal (authored by us) and the AGX machine code
  compiled from them by the public runtime API; tools/agx-isa/db.json (our own
  DB); tools/{shdump,agxtest} (our own tools, used read-only).
Apple binary introspection: NONE
Reproduction: harness/build.sh work/bin; python3 harness/verify.py --selftest;
  python3 harness/run.py --run <id>
Evidence: raw/<run_id>/{00_env.json,01_anchors.json,sweep.jsonl,02_summary.json}
```
