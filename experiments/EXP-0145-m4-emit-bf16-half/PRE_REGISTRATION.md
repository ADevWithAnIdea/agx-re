# EXP-0145 — PRE-REGISTRATION (FROZEN)

**Frozen at** repo revision `7faf0db77813ca4416d10b60e3424ee177215273` (working tree dirty: 76 paths — sibling
experiments commit continuously; per SUBAGENT_BRIEF the gate is the *authored blob
hashes* recorded in `CAPTURE_CONTRACT.json`, not a static `HEAD`).
**Target:** local Apple M4 / G16G only. No SSH. The A18 is untouched.
**Case matrix sha256:** `afd5d1e43849527244b2ac2c398a46e59b9774acd741b9cf18c1c0cbd52b40f7` (43,829 cases; `harness/matrix.py` is deterministic and
re-hashable).

---

## 1. Question

Sixteen bf16 / half / misc-float instruction descriptors and six opaque `n2_op*`-class
descriptors in `tools/agx-isa/db.json` are decodable but **not emittable**: every operand
field is `untested`, `tokenization-only` or `corpus-correlation`, and — per the Part-II
questionnaire desk audit — **no committed experiment has ever measured a single bf16 numeric
result on Apple9 hardware** (P2-01 / P2-02: "hardware YES, emit NO").

Two questions, therefore:

* **Q1 (emit).** Can an emitter *choose* the operand fields of the byte0-low-nibble-1
  bfloat group (`bf_add_dst`, `bf_mul_dst`, `bf_fma_dst`, `bf_alu`, `bf_alu8_var`), the
  `hminmax` half min/max, the low-nibble-8 `half_pack` / high-half half ALU, `funary`
  and `funary_imm` — and get the documented behaviour on real silicon?
* **Q2 (numerics).** What are the *measured* bf16 and fp16 arithmetic semantics — rounding
  mode, tie behaviour, subnormal handling (DAZ/FTZ), overflow, NaN/inf propagation, and
  whether fma is truly fused?

## 2. Hypotheses (falsifiable)

**H1 — one operand descriptor, three names.** `bf_add_dst`, `bf_mul_dst`, `bf_fma_dst` and
`bf_alu` are one 8/10-byte descriptor of the byte0-low-nibble-1 group, laid out as

| byte | meaning |
|---|---|
| +0 | bits[7:4] dst register, bits[3:0] = 0x1 group id |
| +1 | srcA operand = `(reg << 1) | fmt`, fmt 0 = bf16, 1 = fp16 |
| +2 | opsel: 0x1c add, 0x1d mul, 0x1e fma (10-byte form) |
| +3 | srcB operand = `(reg << 1) | fmt` |
| +4 | bit2 = **dst half**, bit3 = **srcA half**, bit4 = **srcB half** (0 = low 16, 1 = high 16); bit0 required set |
| +5 | source modifiers / (10-byte form) srcC operand |
| +6 | bits[7:6] = 0b11 operand-valid base; bit1 = negate srcA |
| +7 | bf-group marker |

**H2 — high/low half selection.** The two 16-bit halves of a GPR are independently
addressable as operands and as the destination, selected by byte+4 bits 3, 4 and 2
respectively. *(Same claim the brief makes for `h_alu_hi`; here it is tested on the bf
group, where a carrier holds `a` in `r0.lo` and `b` in `r0.hi`.)*

**H3 — fmt bit re-interprets, it does not widen.** `fmt = 1` reads the same 16-bit halfword
as IEEE binary16 rather than bfloat16. Prediction: with `a = 3.0` (bf16 `0x4040`) and
`fmtA = 1`, `a + b` returns `fp16(0x4040) + b = 2.125 + 5.0 = 7.125`.

**H4 — bf16 rounding.** The bf16 ALU rounds its result to bf16 **round-to-nearest, ties to
EVEN**, once. Refuters: pre-registered exact-tie vectors separate RNE from
round-to-nearest-away and from truncation in both directions
(`tie_even_down`/`tie_even_up`, `mul_tie_even`/`mul_tie_odd`).

**H5 — bf16/fp16 subnormals.** Given EXP-0074 (FP32 division delivers no IEEE subnormals)
and the shared DAZ+FTZ of `rcp`/`rsqrt`/`sqrt` (EXP-0103), the bf16/fp16 ALU **flushes**
subnormal inputs and/or results to zero. Refuter: `sub_plus_sub` (`0x0001 + 0x0001`)
returning `0x0002` refutes FTZ; `sub_plus_norm` returning the exact sum refutes DAZ.

**H6 — fma is fused.** `bf_fma_dst` / the fp16 fma round **once**. Refuter: the
`fma_fused_probe` / `h_fused` vectors, where fused and multiply-then-add differ by a full
ulp (host-computed with exact rationals).

**H7 — hminmax.** byte+4 bits[2:0] select min (1) / max (0); the other five bits and the
byte+1/+3/+5 operand bytes behave as the `iminmax` family. NaN handling is **unknown** and
is measured, not assumed.

**H8 — half_pack generalises.** The 4-byte low-nibble-8 form `X8 01 1b 09` is
`half_pack` for any dst register, not only the `0x18` (dst r1) form `db.json` matches.

## 3. Variables

*Independent:* the spliced byte value (0..255) at each byte of each carrier's instruction
window; the synthesised field tuple (dst, srcA reg/half/fmt, srcB reg/half/fmt, opsel,
dst-half) in the GENERATED family; the raw bf16/fp16 **input bit patterns** in the NUMERIC
family.
*Controlled:* one byte changed per case; grid = 1 thread; both operand values changed
between input sets S1 and S2 so a constant is distinguishable from a value that tracks an
operand; identical carrier, identical binary archive path discipline, identical timeouts.
*Dependent:* the 2/4-byte result read back from buffer 0, the integrity sentinel in
buffer 4, the command-buffer status and the OS fault-classification string.

## 4. Expected observations and refuters

* If H1/H2 hold, clearing byte+4 bit4 in the native-bfloat add carrier turns `a + b` into
  `a + a`, and setting bit3 turns it into `b + b`. If instead the result is unchanged, or
  silently zero for every value, H2 is refuted.
* If H1 holds, an instruction **built from the rule table** (never copied from compiler
  output) with (dst = 2, srcA = r0.lo, srcB = r0.hi, opsel = mul) returns `a * b` exactly.
* **Pre-registered failures.** `opsel = 0x1e` spliced into the 8-byte form (a length
  change), `opsel = 0x00`, and `srcB = r63` are all pre-registered to **not** match the add
  oracle. If they match, the method cannot tell a real difference and the sweep proves
  nothing.
* If H4 holds, `tie_even_down` returns `0x3F80` **and** `tie_even_up` returns `0x3F82`.
  Any other pair refutes RNE.

## 5. Known confounders and their mitigation

| Confounder | Mitigation |
|---|---|
| Another agent's GPU fault surfacing in our command buffer (protocol §7) | every fault re-run in isolation; the OS classification string recorded verbatim; periodic baseline re-validation with 4 retries; a whole-run stop on an all-attempt baseline failure |
| A wrong field value producing a *silent zero* rather than a fault | output buffer **poisoned with 0xDEADBEEF** by binding it as both input and output, so "never written" is distinguishable from "wrote zero" |
| The program not running at all | **integrity sentinel** on an independent path (buffer 4, constant `0xA5A5A5A5`, also poisoned) giving a three-way clean / not-run / corrupt verdict |
| Metal serving a cached library instead of the spliced bytes | a **unique archive path per request** (deleted after the response, never reused) |
| Our own oracle being wrong | fp16 encoder is an exact-integer RNE implementation cross-checked against `struct` over 400,000 patterns (0 mismatches); every NUMERIC candidate is computed with `fractions.Fraction`, never floating point |
| Compiler output drifting under us | the instruction window is located between the carrier's own load prefix and its **sentinel anchor**, never at a hard-coded offset; all carrier and kernel sha256 are frozen in `CAPTURE_CONTRACT.json` |
| A single-carrier artefact | the bf group is exercised on **five** independent carriers (f32-converted add/mul, native add/mul, native fma, packed bfloat2) |

## 6. Safety

One hypothesis per arm; hard 8 s watchdog on every request; **an arm stops after 2 genuine
hangs**, the run stops after 10; every record appended and `fsync`ed as it completes;
`PROGRESS.md` entry per milestone. Never `macvdmtool`. Never the A18. Nothing written
outside this experiment directory.

## 7. Deliberate scope limits (recorded before the run)

`fldexp`, `coord_madf`, `n2_op8` and `sr_read_wide` have **no carrier**: our own MSL does
not emit them on this toolchain (`ldexp(v,n)` is fully software-lowered; the 0x2e-leader
`coord_madf` needs a texture and `agxrun_persist` binds buffers only; two independent
simdgroup-matrix carriers emit `matrix_mac` but no `sr_read_wide`, and the ray-query path
is unbindable per EXP-0146). These are recorded as **negative emission results / testbed
gaps** and are *not* labelled from a dead path.

## 8. Clean-room attestation

```
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: kernels/*.metal (authored by us) and the AGX bytes produced by
                  compiling them through the public runtime newLibraryWithSource: API
Apple binary introspection: NONE
Reproduction: sh harness/build.sh work/bin
              python3 harness/run_sweep.py run01 BYTEWISE,GENERATED,NUMERIC
              python3 harness/run_sweep.py run02 GENERATED,NUMERIC
              python3 analysis/verdicts.py run01 run02
Evidence: raw/run01/sweep.jsonl, raw/run02/sweep.jsonl (append-only)
```
