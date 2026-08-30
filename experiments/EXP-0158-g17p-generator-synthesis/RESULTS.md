# RESULTS — EXP-0158, G17P generator synthesis (DRV-ISA-01 / P0.6, closure rules 1 and 6)

**Target: A18 Pro / G17P** — every number below was measured on the documentation target.
**Status: CAPTURED, with a named and quantified concurrency limitation (§4).**

---

## 0. The honest headline

> **233 of 237 generated programs that contain ZERO copied fields produced their exact
> host-computed oracle on G17P and never produced a wrong value.**
> **4 still fail, all in one family (`iadd2` register mode at specific destination
> registers), and 24 more still need a donor — 12 control-flow programs and 12
> immediate-mode `iadd2` programs, named in §6.**

Of those 233, **60** rest on **no value this experiment measured itself** — i.e. every field
traces to a rule an earlier experiment published. The other 173 include at least one field
whose accepted set this experiment had to measure on G17P first, because the published claim
about it turned out to be **wrong on this target** (§3).

The corpus is 289 programs in 8 families. **28 of them were pre-registered to FAIL, and all 28
did**, including a positive control compared against a deliberately unreachable oracle — so the
match test is not a rubber stamp.

`EXP-0112`'s equivalent number was **0**: every one of its programs contained at least one
verbatim-copied token (`device_load.dst_lo`/`dst_ext9`/`ld_format`, `falu2.mod_hi`, and
`iadd2`'s entire 13-of-14-field anchor).

---

## 1. What was directly OBSERVED

### 1.1 The gated corpus, by family

Numbers are "behaved as predicted" over both gated runs plus the witness-gated
re-confirmation, using the **attributable** rule defined in §4.

| family | n | zero copied fields | attributably correct | notes |
|---|---|---|---|---|
| `MAIN_DAG` | 100 | 100 | 100 | the exact 100 DAG shapes EXP-0112 ran, same RNG stream, every field computed |
| `DAG_INLINE` | 24 | 24 | 24 | the same shapes with every float constant moved into `falu2`'s inline immediate |
| `INLINEIMM` | 76 | 76 | 76 | all 64 inline codes dense, + 7 `fmul` + 5 `srcB_neg` |
| `REGBOUNDARY` | 38 | 38 | 33 correct + 5 pre-registered failures | R = 63 works, R = 64 silently fails, R = 126/127 fault 5/5 |
| `IADD_SYNTH` | 16 | 16 | **11** | 5 fail — the one real negative, §6.1 |
| `IADD_ANCHOR_COPIED` | 12 | **0** | 12 | retained deliberately: still needs a donor |
| `CF` | 12 | **0** | 12 | retained deliberately: still needs a donor |
| `ADVERSARIAL` | 11 | 11 | 11 behaved as predicted (all must FAIL) | |

### 1.2 The three boundary predictions, all confirmed

- **R = 63 delivers the loaded value; R = 64 does not.** Pre-registered, not a bug. The poison
  arm discriminates the mechanism: for R ≥ 64 the consuming ALU's 6-bit source field aliases
  to `r(R mod 64)` while `extmode` bit 7 is set, so the read returns whatever that register
  holds. R = 63 is the control — 63 mod 64 = 63, so the poison and the load target are the
  same register and the load correctly overwrites the poison.
- **R = 126 and R = 127 fault the command buffer**, 5/5 in the witness-gated re-confirmation.
  EXP-0112 recorded exactly this on the M4; it **reproduces on G17P**.
- **`extmode` bit 0 is a genuine don't-care**: setting it (which no compiler does) changed
  nothing at R = 5 or R = 63.

### 1.3 The inline float immediate — used by a generator for the first time

All **64 inline codes, dense**, reproduce EXP-0138's magnitude model **exactly, 64/64, zero
exceptions**: `m·2^-5` for e = 0, `(8+m)·2^(e-6)` for e > 0, with `k = srcB_index − 64`,
`e = k>>3`, `m = k&7`. It works under `fmul` as well as `fadd`, so the operand class is
orthogonal to the opcode.

**One correction to EXP-0138, and one extrapolation that worked:**

- **the sign is negative when `srcB_neg = 0`.** EXP-0138 fitted magnitudes and its table reads
  as positive; on G17P, in this shape, `srcB = −magnitude(k)` by default.
- **`srcB_neg = 1` flips it positive.** No prior experiment applied the documented negate bit
  (EXP-M4-10) to an *immediate*. It works.

This is what lets a constant ride inside the consuming ALU instruction's own operand field —
no `mov_imm`, no separate `falu2i` seed, no extra register. `DAG_INLINE` exercises it across
24 real DAG shapes.

### 1.4 Two published claims that do NOT hold on G17P

Both were found the expensive way — by a full gated capture failing — and then isolated by
changing one variable at a time. Both are recorded in
`analysis/field_verdicts.json` → `db_defects`.

**(a) `device_load.ld_format` is a load WIDTH.** EXP-0141 records 21 of 64 codes as
"delivering the 32-bit scalar". True of the *addressed* word; **incomplete for an emitter**.
With r7–r12 seeded with distinct constants and one load into r7:

| `ld_format` | loads the target | ALSO writes |
|---|---|---|
| 17, 49 | yes | *(nothing)* |
| 25, 27, 31 | yes | r8 |
| 19, 21, 29, 51 | yes | r8, r9 |
| 23 | yes | r8, r9, r10 |
| 18, 20 | **no** | r8 (and r9) |
| 16, 33, 35 | **no** | *(nothing)* |

The extra registers receive the **following consecutive memory words**. This is invisible in a
single-load probe — this experiment's own pilot arm P7 marked all six of `{17,19,21,23,25,27}`
`ok` — and it silently corrupted **75 of 100 generated DAGs** in `raw/g17p-20260830-run01`.
**An emitter must use 17 (or 49) for a scalar load.**

**(b) `iadd2.srcA` is not inert.** EXP-0139 records "only bits 0,1 decide (must be 0)". On
G17P, sweeping the byte at step 4 over its whole range with everything else natural:

- **44 of 64** values deliver the sum;
- `(v & 0x18) == 0` places the sum in the **upper half-word** (`A+B = 17` reads back as
  `0x00110000`) — 16 values;
- `(v & 0x7C) == 0x50` **silently zeroes** — 4 values.

That mask reproduces all 64 observations exactly. `srcA` carries a live size/half-select. Six
`IADD_SYNTH` cases in `run01` returned the **second operand alone** because of it.

### 1.5 `falu2.mod_hi` — a contradiction in the record, resolved

`validation.json` (EXP-0105/EXP-0099) says `mod_hi` bits 45–47 have "no observable effect".
EXP-0101 H1 requires `falu2i.mods = 0xC0` for a load-sourced operand — and `falu2i.mods`
(bits 40..47) **is** `falu2`'s `{srcA_class, srcB_class, srcB_neg, mod_hi}`, so `0xC0` *is*
`mod_hi = 0xC`. Both cannot be unconditionally true. Measured on G17P, 0..15 dense, in two
shapes:

| srcA provenance | values that deliver the correct result |
|---|---|
| ALU-sourced | the **8 even** values (odd → silent zero) |
| **load-sourced** (device_load bridge) | **only `0xC`** — the other 7 even values leave the loaded operand reading 0 |

**The bits are inert for an ALU-sourced operand and live for a load-sourced one.** Both prior
records are correct within their own shape; neither generalises. `falu2i.mods` confirms the
same split (`{0x00,0x40,0x80,0xC0}` all fine ALU-sourced; only `0xC0` load-sourced — bits 6
and 7 are required *together*).

### 1.6 Carrier baseline reproduces on G17P

`baseline.py` re-derives both carriers from source on the target before every capture:
`carrier_dag.metal` compiles to 1590 bytes, `carrier_cf.metal` to **exactly 152** — the same
length the M4 produced — with the same `base_slot` order, including `carrier_cf`'s documented
buffer(1)/buffer(2) reversal. The A18 toolchain lays these carriers out identically.

---

## 2. Deliverable 1 — the token inventory

`PRE_REGISTRATION.md` §2 is the full field-by-field inventory of what EXP-0112 copied. Summary:

| instruction | fields | copied by EXP-0112 | copied by EXP-0158 |
|---|---|---|---|
| `device_load` | 14 | **9** (incl. the `dst_lo`/`dst_ext9` token EXP-0101 said must never be derived) | **0** |
| `device_store` | 14 | **9** | **0** |
| `falu2` | 15 | **3** (`ctrl`, `mod_lo`, `mod_hi`) | **0** |
| `falu2i` | 13 | 1 (`ctrl_lo`) | **0** |
| `iadd2` register mode | 14 | *(could not be built at all)* | **0** |
| `iadd2` immediate anchor | 14 | 13 | **13, deliberately retained** |
| `get_sr` | 6 | 6 | **0 — eliminated by not emitting it** |
| `mov_imm` | 3 | 0 (but modelled as 8-bit, which EXP-0140 refuted) | **0** |
| `stop` | 1 | 1 | **0** |
| CF skeleton (16 instrs) | ~90 | ~90 | **~90, deliberately retained** |

`get_sr` deserves a note: it is *removed*, not ruled. The dispatch is grid=1/tg=1, so
`thread_position_in_grid` is identically 0 and the index register is set with
`mov_imm(r15, 0)`. Not needing a copy is a legitimate way to stop making one, and it is
reported as such rather than as a rule.

---

## 3. What is INTERPRETATION, not observation

- **`ld_format` is "a vector width / component mask"** is an interpretation. What was
  *observed* is the per-code table in §1.4: which registers changed, and to what. The
  consecutive-memory-word pattern strongly suggests a multi-component load, but this
  experiment did not test the field against the format enumeration, sub-32-bit widths, or
  non-consecutive destinations.
- **`iadd2.srcA` "carries a size/half-select"** is an interpretation. What was observed is the
  value→outcome map and the `0x00110000` upper-half placement. The `(reg<<1)|is32` convention
  appears elsewhere in this ISA at other offsets, which is suggestive, not proof.
- **`mod_hi`'s provenance split** — observed in two shapes only (ALU-seeded `falu2i` operands,
  and a `device_load` extmode bridge). Whether a third operand provenance behaves as a third
  way is untested.
- **The inline immediate's default-negative sign** is observed 64/64 in one carrier and one
  instruction shape. Whether EXP-0138's M4 carrier genuinely differs, or its fit simply
  absorbed the sign, is **not resolved here** and needs a paired M4/G17P run of the same
  program to settle.

---

## 4. The concurrency limitation — stated plainly, because it bounds everything above

**Both gated runs were taken with 8–12 sibling GPU experiments on the same device.** The
consequences are large enough that hiding them would make the numbers meaningless:

- `run03`: **51** cases returned `kIOGPUCommandBufferCallbackErrorInnocentVictim` **after five
  in-case retries each**. `run04`: **70**. The cascade witness (a re-run of a known-good case
  every 40 cases) failed once in seven checks in `run03`.
- The first re-confirmation pass (`work/reconfirm/reconfirm01.jsonl`, **retained, not used**)
  produced **427 `Caused GPU Hang Error` observations in long consecutive streaks** — 36 in a
  row, then 14 clean, then 17 in a row. Among the "hanging" programs was **`dag_000_n2`, a
  two-node program that runs correctly in the recorded hardware fixture and in both gated
  runs**. A trivially correct two-instruction program cannot hang the device; the device was
  being reset by somebody else.
- That extends EXP-0153's §7A lesson: **`InnocentVictim` is not the only contamination
  signature.** Under sustained sibling load the driver also reports `...ErrorHang` against our
  command buffer.
- A second, **witness-gated** pass (`reconfirm02.jsonl`) runs a three-instruction sentinel-only
  program immediately before every observation and discards any observation whose witness
  failed. It still found **102 of 174 cases returning MIXED outcomes across five runs of
  IDENTICAL bytes**. Nondeterminism on identical bytes is contamination by definition.

### Why the pre-registered gate is reported but not used as the headline

`PRE_REGISTRATION.md` §7 asked for "matched bit-exactly in **both** runs", with
`01_results.jsonl` byte-identical across them. **That gate is not achievable on a machine
whose own witness program intermittently fails**, and it is reported for completeness only:

| metric | value |
|---|---|
| pre-registered strict (matched in both gated runs, contamination counted as failure) | **149** |
| **attributable** (see below) | **233** |

`verify.py --captured`, which implements the pre-registered gate literally, therefore **FAILS**,
and is left failing rather than relaxed. Its output is the list of cases whose two gated
observations disagree; every one of them is either contamination-class in at least one run or
one of the four real `IADD_SYNTH` failures.

The **attributable** rule, and the asymmetry that justifies it:

> A case is attributably correct if, across every observation made of it (run03, run04, both
> in-run revalidation passes, and the witness-gated 5-repeat pass), it produced its exact
> host-computed oracle **at least once** and **never** produced a wrong value, a silent zero,
> or a no-write.

A bit-exact match against an independently computed host oracle **cannot be manufactured by
another process's GPU reset** — so a single `ok` is positive evidence about the encoding. A
`fault` under sibling load is evidence about the machine. The rule is therefore permissive
about faults and **strict about wrong answers**: one wrong value anywhere disqualifies a case.
Under it, exactly **4** zero-copied cases are attributably wrong, and they are all real (§6.1).

**This deviation from the pre-registered form is disclosed, not silent**, both numbers are
given, and the raw data to recompute either is committed.

Five cases faulted **5/5** in the witness-gated pass and are the only fault verdicts this
experiment asserts: `regb_R126_faultarm`, `regb_R127_faultarm` (both reproducing EXP-0112's
M4 result), `adv_iadd_dst_reg96` (pre-registered to fault, EXP-0139 `dst ≥ 96`),
`iaddsyn_A11_B22_N1_D0_add` (`iadd2` destination r0, which collides with `srcA`'s implicit r0
read), and `dag_040_n20`.

---

## 5. Method integrity

Every `dag`-carrier program carries an **integrity sentinel** — `mov_imm` → `device_store` of
a fixed constant to out word 252, through a path containing no `falu2`/`falu2i`/`device_load`
— and every read-back buffer is **pre-filled with `0xDEADBEEF`**. Together they separate four
states a zero-filled buffer conflates: *correct*, *wrong value*, *silently zero*, and **never
executed**. Both were verified working on G17P before any capture: a sentinel-only program
leaves word 0 at the poison value and sets word 252 to bits `0x55`.

`CF` is the one family with **no** sentinel: the 152-byte CF carrier cannot hold the extra 16
bytes and lengthening a carrier is not semantically neutral (EXP-0140). Stated, not skipped.

The ISA database is **pinned**. `tools/agx-isa/db.json` changed under this agent mid-read (the
orchestrator edits it concurrently; `falu2.mod_lo` was split into `srcA_class`/`srcB_class`),
so a byte-identical snapshot with a recorded hash lives in `work/isadb_pinned/` and `synth.py`
asserts at import that it loaded that copy. `tools/` was not modified.

---

## 6. The envelope — what still cannot be generated

### 6.1 `iadd2` register mode: 11 of 16, and the boundary is not yet explained

| A | B | N | dst | op | result |
|---|---|---|---|---|---|
| 10, 10, 0, 127, 1, 100, 5, 63, 77, 11, 11 | … | 0,1,2,3,5,6,9 | r2…r8, r32, r63, r64 | add/sub | **correct** |
| 33 | 44 | 13 | r9 | sub | wrong |
| 127 | 1 | 15 | r10 | add | **no write at all**, 7/7 |
| 11 | 22 | 1 | r0 | add | fault 5/5 |
| 11 | 22 | 1 | r95 | add | wrong |
| 7 | 120 | 4 | r47 | add | wrong |

No single parameter explains it: r63 and r64 work while r47 and r95 do not; N = 9 works while
N = 13 and N = 15 do not.

**But the failure signature does.** Three of the four wrong-value cases return the **second
operand alone**, never a partial sum: `A11 B22 → 22`, `A7 B120 → 120`, `A33 B44 → 44`. That is
exactly the signature §1.4(b) attributes to a bad `srcA` — the first operand's read of r0 does
not happen — and it is the same signature the six `run01` failures had before `srcA` was
constrained at all.

So the hypothesis, with a concrete next step: **pilot arm P11 measured `srcA`'s accepted set at
destination r2 only**, and that set does not transfer across destination registers. The
generator picks a different (deterministic) off-natural `srcA` per case, so a value valid at r2
lands on a bad combination at r9/r10/r47/r95. The test is a `srcA` × `dst` cross-sweep. It was
not run here, and the family is reported as **11/16, bounded**, rather than patched by pinning
`srcA` to its natural value — which would have raised the number by re-introducing a copy.

### 6.2 Still needs a donor — 24 cases, named

- **`CF` (12 cases).** EXP-0090's P3 loop + if/else → select skeleton, reused byte-for-byte.
  **No rule exists for any operand field** of `icmp_pred`, `if_push_pred`, `jump_cond`,
  `reg_move_c0`, `if_push`, `scoreboard_fence`, `ret`, `jump`, `pop_reconverge` or `isel10`.
  Only the `falu2i` immediates inside the skeleton and its final `device_store` are computed.
- **`IADD_ANCHOR_COPIED` (12 cases).** The immediate-mode `iadd2` tail. EXP-0139's masks were
  established on the register-mode carrier and demonstrably do not describe this shape — the
  anchor's `opc_tail2 = 4` violates EXP-0139's `v & 0x05 == 0x05` yet executes. Retained so
  the denominator is honest.

### 6.3 Explicitly out of scope, unchanged from EXP-0112

`reg_move` as a dataflow primitive (EXP-0101 Blocker 2); a `device_load` forwarded directly to
a `device_store` with no ALU consumer; general control-flow synthesis; anything beyond
float32 add/mul and 32-bit integer add/sub; single-thread dispatch only (grid=1, tg=1).

---

## 7. Limitations

1. **Concurrency (§4)** is the dominant one. A repeat on a quiet machine would convert the
   attributable number into the pre-registered one, or expose a real failure the noise is
   currently hiding. That run has not been done.
2. **`falu2.srcB_class = 2` hung the device on first contact** and was excluded from the gated
   corpus rather than swept. It is a named hole, not a tested value.
3. **The pilot's single-field probes (P7/P8) are sparse**, chosen to validate exactly the
   off-natural values this generator emits. They are labelled `isolated-byte-diff`, not
   `hardware-run`, in `analysis/field_verdicts.json`. Arm P7 also demonstrates the hazard of
   sparse probes: it passed `ld_format` codes that §1.4 later showed corrupt registers.
4. **`INLINE_NEG0_SIGN` is measured on one carrier and one instruction shape.** An M4↔G17P
   paired run is needed before calling it a target divergence rather than a shape difference.
5. **`iadd2.srcA`'s accepted set was measured at one destination register** (§6.1).
6. **`get_sr` is eliminated, not solved.** A driver that needs a real thread index still has no
   rule for it.

---

## 8. What this supports for DRV-ISA-01 / P0.6

**A generator can synthesize, from documented per-family rules with ZERO verbatim tokens,
arbitrary dataflow programs over `const` / `device_load` / `falu2` / `falu2i` / `device_store`
plus `iadd2` register mode — including register reuse under the documented liveness discipline,
immediates and memory offsets at their encoding boundaries, the `device_load` → ALU bridge for
any target register 0..63, and `falu2`'s inline float immediate across all 64 codes — and get
233 of 237 of them exactly right on the A18 Pro.**

That is what closure rules 1 and 6 ask for, within a named envelope. It is **not** the whole
DRV-ISA-01 bar: control flow and the immediate-mode `iadd2` tail are still template replay
(§6.2), and `iadd2` register mode is bounded at 11/16 (§6.1).

Two published claims this repository's own tables assert (`ld_format`'s scalar set,
`iadd2.srcA`'s inertness) are **refuted on G17P**, and a third (`falu2.mod_hi`) is shown to be
provenance-dependent. Those corrections are arguably worth more than the pass rate: each one is
a silent-corruption trap that a driver following the current tables would have walked into.

---

## 9. Clean-room provenance

```
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: this experiment's own authored generator/harness code (synth.py,
  generator.py, families.py, cf.py, casematrix.py, work/pilot/*.py, work/diag/*.py,
  harness/*.py) -- every instruction built via a PINNED, hash-recorded snapshot of this
  repository's own isadb.assemble(); our own carrier MSL (kernels/carrier_dag.metal,
  kernels/carrier_cf.metal); our own splice+run harness over tools/agxtest and tools/shdump.
Apple binary introspection: NONE.
Reproduction: README.md's command sequence.
Evidence: raw/g17p-20260830-run01/ (retained, pre-AMENDMENT-1),
  raw/g17p-20260830-run03/, raw/g17p-20260830-run04/, work/pilot/, work/diag/,
  work/reconfirm/, analysis/summary.json, analysis/field_verdicts.json.
```

**Concurrent GPU experiments during these captures: 8–12 (EXP-0153 through EXP-0159).**
