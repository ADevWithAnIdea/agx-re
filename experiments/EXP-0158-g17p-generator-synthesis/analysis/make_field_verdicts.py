#!/usr/bin/env python3
"""EXP-0158 -> analysis/field_verdicts.json, in the schema
FIELD-SWEEP-PROTOCOL.md section 5 mandates.  No GPU.

Only fields this experiment actually SWEPT on G17P get a verdict.  Fields it
merely *used* correctly are not upgraded: using a field is not sweeping it.
Labels come from docs/evidence-classification.md section 2 and nothing else.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP))

PILOT = json.load(open(HERE / "pilot_summary.json"))
SUMMARY = json.load(open(HERE / "summary.json"))

EV = ["EXP-0158"]
T = "G17P"


def rng_from(d):
    ok = sorted(int(k) for k, v in d.items() if v == "ok")
    return ok


V = {}

# ---------------------------------------------------------------------------
# falu2.mod_hi -- the operand-provenance split, this experiment's own finding
# ---------------------------------------------------------------------------
V["falu2.mod_hi"] = {
    "label": "hardware-run",
    "range": "0..15 dense (all 16 values), in TWO operand-provenance shapes",
    "target": T, "evidence": EV,
    "semantics":
        "ALU-sourced srcA: the 8 EVEN values deliver the correct result, the 8 ODD "
        "values silently zero -- so bit0 (instr bit44) must be 0 and bits1-3 are a "
        "don't-care. LOAD-sourced srcA (a device_load extmode bridge): ONLY 0xC "
        "works; the other seven even values leave the loaded operand reading 0 and "
        "the odd values still silently zero.",
    "note":
        "CORRECTS the record. validation.json (EXP-0105/EXP-0099) says mod_hi "
        "bits45-47 have 'no observable effect'; that holds only for an ALU-sourced "
        "operand. EXP-0101 H1's falu2i `mods = 0xC0` requirement is the SAME "
        "constraint seen through falu2i's 8-bit `mods` window, since falu2i.mods "
        "(bits 40..47) == falu2's {srcA_class, srcB_class, srcB_neg, mod_hi}. The "
        "two records are only consistent under the provenance split measured here.",
    "raw": "work/pilot/pilot_leased02.jsonl arms P1/P2",
}

V["falu2i.mods"] = {
    "label": "hardware-run",
    "range": "{0x00, 0x40, 0x80, 0xC0} x {ALU-sourced, load-sourced}",
    "target": T, "evidence": EV,
    "semantics":
        "ALU-sourced srcA: all four values deliver the correct result. LOAD-sourced "
        "srcA: only 0xC0 does; 0x00/0x40/0x80 leave the loaded operand reading 0. "
        "Bits 6 and 7 are required TOGETHER -- neither alone suffices.",
    "note": "EXP-0101 H1 REPRODUCES on G17P.",
    "raw": "work/pilot/pilot_leased02.jsonl arm P3",
}

# ---------------------------------------------------------------------------
# falu2 inline float immediate
# ---------------------------------------------------------------------------
V["falu2.srcB_class"] = {
    "label": "hardware-run",
    "range": "0,1,3 executed (2 EXCLUDED: it hung the device on first contact)",
    "target": T, "evidence": EV,
    "semantics":
        "0 = srcB reads GPR[srcB_reg]. 1 = srcB reads the non-GPR operand file; the "
        "7-bit srcB index 64..127 is then an INLINE 8-BIT FLOAT IMMEDIATE. 3 behaved "
        "like 1 in this shape. 2 produced a real GPU hang and was excluded from the "
        "gated corpus.",
    "note":
        "EXP-0138's source-class model REPRODUCES on G17P for classes 0 and 1. Class "
        "2/3 differ from EXP-0138's M4 reading ('both read 0.0'): here 3 delivered "
        "the immediate and 2 hung. NOT promoted beyond what was observed.",
    "raw": "work/pilot/pilot_P10_P6.jsonl arm P6",
}

V["falu2.srcB_reg (inline-immediate class)"] = {
    "label": "hardware-run",
    "range": "all 64 inline codes k = 0..63, DENSE, plus srcB_neg at 5 codes",
    "target": T, "evidence": EV,
    "semantics":
        "With srcB_class = 1 and srcB bit6 set, the operand is an inline minifloat of "
        "MAGNITUDE m*2**-5 (e == 0) or (8+m)*2**(e-6) (e > 0), where k = index-64, "
        "e = k>>3, m = k&7. All 64 codes reproduce that magnitude EXACTLY (64/64, "
        "zero exceptions). The SIGN is NEGATIVE when srcB_neg = 0 and POSITIVE when "
        "srcB_neg = 1.",
    "note":
        "The magnitude model is EXP-0138's, reproduced exactly on G17P. The SIGN is "
        "new: EXP-0138 fitted magnitudes only and its table reads as positive. "
        "srcB_neg (EXP-M4-10) is confirmed to apply to an INLINE IMMEDIATE, which no "
        "prior experiment tested -- an extrapolation that worked.",
    "raw": "work/pilot/pilot_leased02.jsonl arms P4/P5",
}

# ---------------------------------------------------------------------------
# device_load
# ---------------------------------------------------------------------------
V["device_load.dst_lo"] = {
    "label": "hardware-run",
    "range": "0..3 dense (all 4 values)",
    "target": T, "evidence": EV,
    "semantics": "Exactly 1 delivers the load; 0, 2 and 3 SILENTLY ZERO it.",
    "note":
        "EXP-0141's exact rule REPRODUCES on G17P. This is the token EXP-0112 had to "
        "copy verbatim; it is now computed, and the three adversarial cases that "
        "force the wrong value all fail as predicted.",
    "raw": "work/pilot/pilot_leased02.jsonl + pilot_leased03.jsonl arm P7",
}

V["device_load.ld_format"] = {
    "label": "hardware-run",
    "range": "15 codes {16,17,18,19,20,21,23,25,27,29,31,33,35,49,51} with a "
             "SIX-REGISTER witness readback",
    "target": T, "evidence": EV,
    "semantics":
        "ld_format selects a LOAD WIDTH, not merely a scalar format. Measured, with "
        "r7..r12 pre-seeded with distinct constants and one load into r7: "
        "17 and 49 write ONLY the target; 25/27/31 also write r8; 19/21/29/51 also "
        "write r8 and r9; 23 also writes r8, r9 and r10; 18 and 20 write r8 (and r9) "
        "but NOT the target; 16, 33 and 35 write nothing. The extra registers receive "
        "the FOLLOWING CONSECUTIVE memory words.",
    "note":
        "FIRST-CLASS CORRECTION to EXP-0141, which recorded 21 of 64 codes as "
        "'delivering the 32-bit scalar'. That is true of the ADDRESSED word and is "
        "not sufficient for an emitter: in a register-allocated program the extra "
        "writes silently corrupt unrelated live values, and they are invisible in a "
        "single-load probe (this experiment's own pilot arm P7 marked all six codes "
        "`ok`). It cost 75 of 100 MAIN_DAG cases in raw/g17p-20260830-run01 and was "
        "root-caused by one-variable-at-a-time isolation. AN EMITTER MUST USE 17 (or "
        "49) FOR A SCALAR LOAD.",
    "raw": "work/diag/diag_ldformat.jsonl, work/diag/diag01.jsonl, diag02.jsonl",
}

for f, tbl in PILOT["DL_FIELD_OK"].items():
    if f in ("dst_lo", "ld_format"):
        continue
    ok = rng_from(tbl)
    V["device_load." + f] = {
        "label": "isolated-byte-diff",
        "range": "%d values sampled one-field-at-a-time: %s" % (len(tbl), sorted(tbl)),
        "target": T, "evidence": EV,
        "semantics": "values delivering the load unchanged: %s" % ok,
        "note":
            "NOT `hardware-run`: this is a sparse single-field probe on one carrier, "
            "chosen to validate the specific off-natural values this experiment's "
            "generator emits, not a dense sweep. EXP-0141's dense M4 sweep is the "
            "range claim; this is its on-target spot-check.",
        "raw": "work/pilot/pilot_leased02.jsonl + pilot_leased03.jsonl arm P7",
    }

for f, tbl in PILOT["DS_FIELD_OK"].items():
    ok = rng_from(tbl)
    V["device_store." + f] = {
        "label": "isolated-byte-diff",
        "range": "%d values sampled one-field-at-a-time: %s" % (len(tbl), sorted(tbl)),
        "target": T, "evidence": EV,
        "semantics": "values storing the ALU-computed word correctly: %s" % ok,
        "note": "on-target spot-check of EXP-0141's M4 sweep; every sampled value "
                "stored correctly.",
        "raw": "work/pilot/pilot_leased02.jsonl arm P8",
    }

# ---------------------------------------------------------------------------
# iadd2 register mode
# ---------------------------------------------------------------------------
V["iadd2.srcA"] = {
    "label": "hardware-run",
    "range": "0..252 step 4 (64 values; the low 2 bits are held at 0 per EXP-0139)",
    "target": T, "evidence": EV,
    "semantics":
        "44 of 64 sampled values deliver the sum. (v & 0x18) == 0 places the sum in "
        "the UPPER HALF-WORD (A+B = 17 reads back as 0x00110000). (v & 0x7C) == 0x50 "
        "SILENTLY ZEROES. That mask model reproduces all 64 observations exactly.",
    "note":
        "REFUTES EXP-0139's 'only bits 0,1 decide (must be 0)' on G17P: bits 3 and 4 "
        "are live and there is a hole at bits[6:2] = 0b10100. srcA carries a "
        "size/half-select, not merely a format constant. Measured at destination r2 "
        "ONLY -- see the IADD_SYNTH limitation in RESULTS.md; five of sixteen "
        "(A,B,N,dst) combinations in the gated corpus still fail, most plausibly "
        "because this accepted set does not transfer across destination registers.",
    "raw": "work/pilot/pilot_iadd01.jsonl arm P11",
}

for f in ("opc_tail", "opc_tail2", "opmode", "b2_fmt", "srcB_ext", "store_en",
          "b2_bit0", "srcB_reg_hi", "lenbit", "srcB_imm_hi"):
    tbl = PILOT["IADD_FIELD_ALL"].get(f, {})
    ok = PILOT["IADD_FIELD_OK"].get(f, [])
    V["iadd2." + f] = {
        "label": "hardware-run" if len(tbl) >= 16 else "isolated-byte-diff",
        "range": "%d values sampled" % len(tbl),
        "target": T, "evidence": EV,
        "semantics": "%d of %d delivered the sum" % (len(ok), len(tbl)),
        "note": "EXP-0139's INERT reading REPRODUCES on G17P for this field "
                "(non-ok observations were victim/invalid_run class).",
        "raw": "work/pilot/pilot_iadd01.jsonl arm P11",
    }

# ---------------------------------------------------------------------------
# the register-bridge boundary
# ---------------------------------------------------------------------------
V["device_load.extmode (bridge target R)"] = {
    "label": "hardware-run",
    "range": "R in {0,1,2,3,7,15,16,20,31,32,47,48,60,61,62,63,64,65,66,67,68,79,80,"
             "95,96,111,112,126,127}, plus 5 poison controls and the bit0 don't-care",
    "target": T, "evidence": EV,
    "semantics":
        "extmode = 2*R delivers the load for R <= 63. R >= 64 does NOT: extmode bit7 "
        "is then set and the consuming ALU's 6-bit source field independently aliases "
        "to r(R mod 64), so the read returns whatever that register holds (0.0 when "
        "unwritten). R = 126 and R = 127 FAULT the command buffer, reproducibly "
        "(5/5 in the witness-gated re-confirmation). extmode bit0 is a don't-care: "
        "setting it changed nothing at R = 5 and R = 63.",
    "note":
        "EXP-0141's destination rule and EXP-0112's M4 126/127 fault both REPRODUCE "
        "on G17P. R = 63 works and R = 64 silently fails, exactly as pre-registered.",
    "raw": "raw/g17p-20260830-run03/01_results.jsonl group REGBOUNDARY",
}

OUT = {
    "_meta": {
        "experiment": "EXP-0158-g17p-generator-synthesis",
        "target": T,
        "note":
            "Verdicts are for fields this experiment SWEPT on G17P. Fields it merely "
            "used correctly are NOT upgraded. Every `fault` verdict here survived the "
            "witness-gated 5-repeat re-confirmation (FIELD-SWEEP-PROTOCOL section 7A); "
            "no fault verdict rests on a single observation.",
        "concurrency":
            "Both gated runs were taken with 8-12 sibling GPU experiments on the same "
            "device. 51 (run03) and 70 (run04) cases came back "
            "kIOGPUCommandBufferCallbackErrorInnocentVictim even after five in-case "
            "retries, and 102 of 174 re-confirmed cases returned MIXED outcomes across "
            "five runs of IDENTICAL bytes. See RESULTS.md.",
    },
    "db_defects": {
        "device_load.ld_format": {
            "modelled": "a format code; EXP-0141: '21 of 64 codes deliver the 32-bit "
                        "scalar'",
            "measured": "a LOAD WIDTH. Codes 19/21/23/25/27/29/31/51 deliver the "
                        "addressed word AND write 1-3 further consecutive registers "
                        "with the following memory words. Only 17 and 49, of those "
                        "tested, write exactly one register.",
            "evidence": "work/diag/diag_ldformat.jsonl",
            "impact": "an emitter following the EXP-0141 reading silently corrupts "
                      "live registers; it cost 75/100 generated DAGs in "
                      "raw/g17p-20260830-run01",
        },
        "iadd2.srcA": {
            "modelled": "EXP-0139: 'only bits 0,1 decide (must be 0)'; the byte does "
                        "not select a register",
            "measured": "bits 3 and 4 are LIVE on G17P ((v & 0x18) == 0 moves the "
                        "result into the upper half-word) and bits[6:2] == 0b10100 "
                        "silently zeroes",
            "evidence": "work/pilot/pilot_iadd01.jsonl arm P11",
            "impact": "six IADD_SYNTH cases in raw/g17p-20260830-run01 returned the "
                      "second operand alone instead of the sum",
        },
    },
}
OUT.update(V)

(HERE / "field_verdicts.json").write_text(
    json.dumps(OUT, indent=2, sort_keys=True) + "\n")
print("wrote analysis/field_verdicts.json with %d field verdicts" % len(V))
