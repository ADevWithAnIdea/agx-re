# EXP-0203 — half-precision: giving four fields a real host oracle on G17P

**Target: Apple A18 Pro / G17P** (`AGXAcceleratorG17P`, `applegpu_g17p`, 5 GPU cores,
macOS 26.6, Metal family Apple9). Every claim here is a **G17P** claim.

## Question

Four fields across two half-precision instructions, all `untested` in
`tools/agx-isa/validation.json`:

| field | span (`db.json`) | why it was open |
|---|---|---|
| `half_alu_fma12.dst` | bits 4..7 | no oracle; cross-run agreement 0.00% (EXP-0196) |
| `half_alu_fma12.ext` | bits 32..95 | encodable range 2^64 |
| `half_pack.dstlo` | bits 8..15 | 88 moved, cross-run agreement failed (EXP-0164) |
| `half_pack.b3` | bits 24..31 | 86 moved, cross-run agreement failed (EXP-0164) |

**Can each be given arbitrary values in a carrier where a host-computed,
per-value-DISCRIMINATING oracle predicts the complete post-state, and does the hardware match
that prediction over the whole encodable range in independent gated runs?**

## Answer

| field | legacy label | geometry | liveness | semantics | recipe | target |
|---|---|---|---|---|---|---|
| `half_alu_fma12.dst` | **`hardware-run`** | geometry-mapped | live | semantically-mapped | generated-point | G17P-direct |
| `half_pack.dstlo` | **`hardware-run`** | geometry-mapped | live | semantically-mapped | generated-point | G17P-direct |
| `half_pack.b3` | **`hardware-run`** | geometry-mapped | live | semantically-mapped | generated-point | G17P-direct |
| `half_alu_fma12.ext` | `untested` (forced) | ledger-verified | live (per byte) | bounded-map | not-generated | G17P-direct |

Full numbers, the six-axis verdicts, and the model corrections are in `RESULTS.md` and
`analysis/field_verdicts.json`.

## Method

1. **The oracle was fitted OFFLINE, before the contract was frozen**, from our own committed
   `EXP-0180` raw (`analysis/fit_model_offline.py`). `|a|*b - c` matched 256/256 on each of
   two carriers; eight competing models matched fewer. The same offline pass found that
   EXP-0180's `byte+4 = 0x93` releases the third operand's lane and `0x13` does not, so this
   experiment's base instance uses `0x13` and its oracle predicts no side effect.
2. **A synthesized carrier.** Two authored MSL kernels give a long `_agc.main`; the entire
   body is replaced by a program assembled from `tools/agx-isa`'s own field rules:
   seed all 16 GPRs with distinct non-zero normal fp16 values in **both** halves → PRE
   sentinel → **dump all 16 GPRs** → the instruction under test + four 2-byte length markers
   → **dump all 16 GPRs** → POST sentinel → stop. Read-back is poisoned with `0xDEADBEEF`.
3. **Two disjoint register/readback plans** (`HI`: index r15, markers r10-13, fixed dst r1;
   `LO`: index r0, markers r2-5, fixed dst r7), so no destination value is unobservable in
   both, and a hidden write cannot masquerade as inertness.
4. **Per-case actual-byte ledger.** The spliced program is written, **read back from that
   file**, and the instruction bytes extracted at the builder's reported offset; the field
   value is decoded from those actual bytes and compared to the request.
5. **Falsifiers and controls in every arm**: a null block, an opsel change, a destination
   override, a same-dimension liveness control, and an unseeded-register control.
6. Two gated runs in opposite case order, plus three earlier gated runs retained.

## Reproduction

```sh
# ---- offline, no device ------------------------------------------------
python3 analysis/fit_model_offline.py g17p_run02   # the oracle, from EXP-0180's raw
python3 harness/casematrix.py                      # the frozen matrix + its sha256
python3 harness/selftest.py                        # 20 OFFLINE gates; a CODE test, NOT evidence

# ---- on the neo (A18 Pro / G17P) ---------------------------------------
export SSHPASS='...'                               # never written to any file
harness/sync.sh push
python3 harness/verify_remote.py                   # VERIFY SEPARATELY -- never trust the push
ssh user@$NEO 'cd agxre/EXP-0203 && python3 harness/run.py --mode pilot --run pilot01'
harness/sync.sh pull pilot01
# inspect anchors, controls and falsifiers in raw/pilot01 BEFORE the gated runs.
ssh user@$NEO 'cd agxre/EXP-0203 && python3 harness/run.py --mode gated --order forward --run g17p_run31'
ssh user@$NEO 'cd agxre/EXP-0203 && python3 harness/run.py --mode gated --order reverse --run g17p_run32'
harness/sync.sh pull g17p_run31 ; harness/sync.sh pull g17p_run32

# ---- analysis ----------------------------------------------------------
python3 analysis/verdicts.py raw/g17p_run31 raw/g17p_run32          # the gate
python3 analysis/verdicts.py raw/g17p_run31 raw/g17p_run32 --g7 frozen
python3 analysis/ext_bytes.py raw/g17p_run31 raw/g17p_run32
python3 analysis/finalize.py                                        # -> analysis/field_verdicts.json
python3 ../../tools/agx-isa/wave_audit.py .                         # the arrival gate
```

## Clean-room attestation

```text
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: our own MSL (kernels/), bytes we assembled ourselves through
                  tools/agx-isa, our own committed raw from EXP-0180, and tools/agx-isa
Apple binary introspection: NONE
Reproduction: the commands above
Evidence: raw/pilot01, raw/g17p_run21..23, raw/g17p_run31..32 (append-only)
```

No Apple binary was disassembled, decompiled, symbol-dumped, strings-scanned, or debugged.
The only machine code inspected anywhere in this experiment is the compiled form of MSL we
wrote (`kernels/`), and bytes this experiment assembled itself.
