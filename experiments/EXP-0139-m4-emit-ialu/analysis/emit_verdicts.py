#!/usr/bin/env python3
"""EXP-0139 -> `analysis/field_verdicts.json` in FIELD-SWEEP-PROTOCOL §5 schema,
plus the `db_defects` block and the emittability roll-up.

Run: python3 analysis/emit_verdicts.py
"""
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
REPO = EXP.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(EXP / "harness"))
sys.path.insert(0, str(REPO / "tools" / "agx-isa"))
import verdicts as V   # noqa: E402
import isadb           # noqa: E402

TARGETS = ("iadd2 ibfe ibfe_mesh_attr ibfins ibitcount icmp_pred icmpsel imad "
           "iminmax isel10 isel10_c isel8 isel_reg isel_reg8 ishift iunary").split()
OK = ("hardware-run", "isolated-byte-diff")

SEM_OVERRIDE = {
 "ibfe.offset":
   "LITERAL, NOT masked mod 32. o = (a >> offset) & mask. Dense 0..63: every value "
   "0..31 shifts normally and every value 32..63 shifts the field out entirely "
   "(result 0). The literal model fits 64/64 stable values; a mod-32 model fits only "
   "32/64. This is the BARE-INSTRUCTION answer EXP-0102 left open: the hardware does "
   "NOT implement NIR's `mask offset mod 32`.",
 "ibfe.width":
   "TAKEN MOD 32 -- and this REFUTES the model pre-registered for it. o = (a >> "
   "offset) & ((1 << (width mod 32)) - 1), with width mod 32 == 0 meaning NO MASK "
   "(extract to the MSB). Over the dense 0..63 sweep the mod-32 model fits 64/64 "
   "stable values; the pre-registered `literal, clamp at 32` model fits only 37/64. "
   "So `width` and `offset` of the SAME instruction use OPPOSITE out-of-range rules: "
   "offset is literal, width wraps.",
 "ibitcount.tail":
   "ONLY BIT 2 (0x04) IS LOAD-BEARING. Dense 0..255 on a fully SYNTHESIZED popcount: "
   "all 128 values with bit2 set return the correct popcount; all 128 with bit2 clear "
   "return a wrong, constant, non-zero value. Bits 0,1,3,4,5,6,7 are free -- an "
   "emitter must set bit 2 and may choose the other seven bits arbitrarily. This "
   "supersedes the `0x04 marker in every observed instance` single-template label and "
   "closes the ONLY field that was blocking `ibitcount`.",
 "iunary.operand[tail]":
   "Identical bit-2 rule to `ibitcount.tail`, observed on a program that tokenizes as "
   "`iunary` and NOT as `ibitcount` (byte+1 = 0x2d). Dense 0..255.",
 "iunary.operand[src]":
   "operand byte 2 == `ibitcount.src`: reg<<2 selects the source GPR. Model matched "
   "16/16 over r0..r15 with 16 distinct mov_imm-seeded values, on a program that "
   "tokenizes as `iunary`, not `ibitcount`.",
 "iunary.operand[dst]":
   "operand byte 0 == `ibitcount.dst`: reg<<1 relocates the result. Corrected "
   "relocation oracle matched 15/16 (1 value excluded as not reproducible).",
 "iunary.operand[op_enable]":
   "operand byte 1 == `ibitcount.op_enable`: only bit 1 decides whether the op "
   "computes -- dense 0..255, confirming EXP-M4-14's `op_enable` finding on the LOOSE "
   "descriptor as well.",
 "iunary.operand[srcdesc]":
   "operand byte 3 == `ibitcount.srcdesc`. Dense 0..255, fully deterministic.",
 "iminmax.sel":
   "db.json's corpus-derived map is CONFIRMED ON HARDWARE for the four integer "
   "members: 4=umax, 5=umin, 6=imax, 7=imin, each matching an independent host "
   "computation over 8 asymmetric/boundary operand pairs. sel=0/1 (fmax/fmin) execute "
   "and behave as float max/min but do NOT match a naive IEEE oracle on this carrier: "
   "they disagree exactly on the NaN (0xFFFFFFFF) and denormal (0x0000FF00, 1, 31, 32) "
   "operands, i.e. the hardware flushes denormals to zero and suppresses NaN in "
   "max/min. A carrier with normal float operands is the named follow-up.",
 "ishift.shamt":
   "shamt byte = n << 2; o = a >> n, ARITHMETIC (sign-preserving). Model matched 32/32 "
   "at every multiple of 4 from 0 to 124 (n = 0..31), verified against a host "
   "computation over 8 operands including 0x80000000 and 0xFFFFFFFF. Every byte value "
   "that is NOT a multiple of 4 is deterministic too and is enumerated in the raw log.",
 "iadd2.dst":
   "dst = (reg<<1)|size, verified by RELOCATION over the dense 0..255 sweep: the sum "
   "reaches the store's register r6 at exactly dst=12/13 and nowhere else below reg 96. "
   "Two HW facts this establishes. (1) BOUND: reg >= 96 (dst >= 192) faults "
   "REPRODUCIBLY (5/5 attempts, healthy baselines, 60 values) -- sharper than "
   "EXP-0112's `faults at 126/127` and consistent with EXP-0020's `up to 96 regs`. "
   "(2) EXP-0112's `r(R mod 64)` aliasing rule DOES NOT HOLD for this field at the one "
   "point the sweep tests it: dst=140/141 (reg 70, which would alias r6) left r6 at its "
   "sentinel. dst=30/31 (reg 15) is a carrier artefact, not a field property -- r15 is "
   "this program's store index register, so writing the sum there moves the store.",
 "iadd2.srcB_imm":
   "srcB_imm = 4*N selects r_N (EXP-0128's rule), re-confirmed here on an independently "
   "built program with a 16-register seed table: N = 0,1,2,3,7,13,14 each produced "
   "10 + seed[N] exactly.",
 "iadd2.addsub":
   "1 = add, 0 = subtract, and the register-mode subtract polarity is d = r_N - r0 "
   "(EXP-0128 SS1.4) -- re-confirmed here, matched.",
}


STRENGTH = {"hardware-run": 0, "isolated-byte-diff": 1, "corpus-correlation": 2,
            "tokenization-only": 3, "single-template-inference": 4,
            "api-accept-reject": 5, "host-private": 6, "untested": 7}


def emittable_now(mn, verdicts):
    """A family is emittable only if EVERY field in its db.json descriptor is
    hardware-run or isolated-byte-diff.

    MERGE POLICY: evidence accumulates, so a field takes the STRONGER of (the
    label already in tools/agx-isa/validation.json, this experiment's verdict).
    EXP-0139 never DEMOTES a field a prior experiment established -- a sweep
    that cannot re-derive a rule on ITS carrier is not a refutation. Any case
    where this experiment's data actively CONTRADICTS a prior label is reported
    separately in RESULTS.md, not silently merged."""
    prior = json.load(open(REPO / "tools" / "agx-isa" / "validation.json"))["instructions"]
    ins = [i for i in isadb.DB if i["mnemonic"] == mn][0]
    rows = []
    for f in ins["fields"]:
        key = "%s.%s" % (mn, f["name"])
        plab = prior.get(mn, {}).get(f["name"], {}).get("label", "untested")
        if key in verdicts:
            mlab = verdicts[key]["label"]
        elif mn == "iunary" and f["name"] == "operand":
            subs = [k for k in verdicts if k.startswith("iunary.operand[")]
            labs = [verdicts[k]["label"] for k in subs]
            mlab = "hardware-run" if labs and all(l in OK for l in labs) else "untested"
        else:
            mlab = "untested"
        if STRENGTH[mlab] <= STRENGTH[plab]:
            lab, src = mlab, ("EXP-0139" if mlab != "untested" else "neither")
        else:
            lab, src = plab, "prior (stronger; EXP-0139 = %s)" % mlab
        rows.append((f["name"], lab, src))
    return rows, all(l in OK for _, l, _ in rows)


def main():
    per, ref = V.main()
    from collections import defaultdict
    byfield = defaultdict(dict)
    for (instr, field, arm), rows in per.items():
        if field.startswith("_"):
            continue
        v = V.verdict(instr, field, rows)
        if v is not None:
            byfield[(instr, field)][arm] = v
    out = {}
    for (instr, field), arms in sorted(byfield.items()):
        prim = V.PRIMARY.get(instr)
        arm = prim if prim in arms else sorted(arms)[0]
        label, rng, stats, sem, note = arms[arm]
        extra = ["second independent carrier %s %s (%s over %s)" %
                 (o, "AGREES" if ov[0] == label else "DIFFERS", ov[0], ov[1])
                 for o, ov in sorted(arms.items()) if o != arm]
        key = "%s.%s" % (instr, field)
        out[key] = dict(label=label, range=rng, target="M4", evidence=["EXP-0139"],
                        semantics=SEM_OVERRIDE.get(key, sem),
                        note="; ".join([x for x in ([note] + extra) if x]),
                        carrier=arm, stats=stats)

    # ---- instructions with no anchor anywhere in our own compiled corpus ----
    for f in ["operands", "opdesc", "tail"]:
        out["ibfe_mesh_attr.%s" % f] = dict(
            label="untested", range="none", target="M4", evidence=["EXP-0139"],
            semantics="not established",
            note="NO ANCHOR: `ibfe_mesh_attr` is the fragment/mesh-stage packed "
                 "per-primitive-attribute source mode (byte+2 == 0x66). 30 authored "
                 "compute kernels produced none, and this harness is compute-only. "
                 "Named follow-up: a mesh/fragment carrier on tools/agxtest/agxrender.m. "
                 "Declared out of scope in PRE_REGISTRATION.md §7, not silently dropped.",
            carrier=None, stats={})

    # FIELD-SWEEP-PROTOCOL SS5 schema: the top level is the flat
    # "<mnemonic>.<field>" -> {label, range, target, evidence, semantics, note}
    # map, alongside the reserved "db_defects" key. Underscore-prefixed keys
    # carry this experiment's own metadata and the emittability roll-up.
    doc = dict(out)
    doc["_meta"] = {
        "experiment": "EXP-0139-m4-emit-ialu",
        "target": "Apple M4 (G16G), macOS 26.6.2 (25G82), local host only. No A18 claim.",
        "method": "two gated launches x two in-run repeats, plus two fresh-process "
                  "re-validation passes; see RESULTS.md SS3 for the fault discipline.",
        "labels": "the eight in docs/evidence-classification.md; nothing else.",
        "promotion_rule": "a dense sweep ALONE never promotes a field. hardware-run = a "
                          "pre-registered model matched, OR inert across the whole encodable "
                          "range, OR a <=1-bit rule fully decides correct execution. "
                          "isolated-byte-diff = a 2..4-bit rule fully decides it. Everything "
                          "else is `untested` with the full enumeration in `note`, per "
                          "validation.json's own `tested-but-unexplained` convention.",
        "merge_rule": "evidence accumulates: take the STRONGER of (existing validation.json "
                      "label, this experiment's verdict). EXP-0139 never demotes a field a "
                      "prior experiment established; the one genuine contradiction "
                      "(EXP-0112's aliasing rule vs iadd2.dst) is db_defects DEF-0139-4.",
        "concurrent_gpu_experiments": ["EXP-0141-mem", "EXP-0146-integer-misc"],
    }

    verd = {k: v for k, v in out.items()}
    emit = {}
    for mn in TARGETS:
        rows, ok = emittable_now(mn, verd)
        emit[mn] = {"emittable": ok, "fields": [{"field": n, "label": l, "source": s}
                                                for n, l, s in rows]}
    doc["_emittability"] = emit
    doc["db_defects"] = DB_DEFECTS
    json.dump(doc, open(HERE / "field_verdicts.json", "w"), indent=1, sort_keys=True)

    c = Counter(v["label"] for v in out.values())
    print("fields recorded:", len(out), dict(c))
    print()
    for mn in TARGETS:
        labs = Counter(r["label"] for r in emit[mn]["fields"])
        print("  %-16s emittable=%-5s  %s" % (mn, emit[mn]["emittable"], dict(labs)))


DB_DEFECTS = [
 {"id": "DEF-0139-1", "where": "tools/agx-isa/db.json :: iunary.operand",
  "claim": "`operand` is modelled as ONE 40-bit `raw` field (byte+3..+7) described as a "
           "MIXED popcount-source / SFU-interp / format-conversion coefficient word.",
  "finding": "In the 8-byte byte0==0x27 space it is NOT one field. It is five one-byte "
             "sub-fields with EXACTLY `ibitcount`'s meanings: byte+3 dst (reg<<1), "
             "byte+4 op_enable (bit 1), byte+5 src (reg<<2), byte+6 srcdesc, byte+7 tail "
             "(bit 2). Established on programs that tokenize as `iunary`, NOT as "
             "`ibitcount` (byte+1 = 0x2d, so the tighter match loses), with the src and "
             "dst models matching 16/16 and 15/16 over mov_imm-seeded registers and both "
             "remaining bytes swept densely 0..255.",
  "evidence": "raw/m4_20260828_run0{1,2}/sweep.jsonl arm=IUNARY; analysis/field_stats.json",
  "recommendation": "split `iunary.operand` into the five named sub-fields for the "
                    "byte0==0x27 / length-8 space. The RT (opsel 0x22 with byte+1==0x81) "
                    "and interp/convert siblings are a DIFFERENT length class and are not "
                    "covered by this finding."},
 {"id": "DEF-0139-2", "where": "tools/agx-isa/db.json :: ibfe semantics note",
  "claim": "`width = 1,4,8,12,16 -> 0x10/0x40/0x80/0xc0/0x100; width=0 means extract-to-MSB`.",
  "finding": "Correct as far as it goes but incomplete in the way that matters to an "
             "emitter: `width` is taken MOD 32. Dense 0..63 -- the mod-32 model fits 64/64 "
             "stable values, a literal/clamp-at-32 model fits only 37/64. width ≡ 0 (mod 32) "
             "is the no-mask (extract-to-MSB) case, so width=32 behaves exactly like "
             "width=0. `offset` on the SAME instruction is the opposite: literal, with "
             "32..63 shifting the field out entirely (0). ",
  "evidence": "raw/m4_20260828_run0{1,2}/sweep.jsonl arm=IBFE field=width/offset",
  "recommendation": "state both rules explicitly, and note the asymmetry; it is the "
                    "bare-instruction answer to EXP-0102's own recommended follow-up."},
 {"id": "DEF-0139-3", "where": "tools/agx-isa/validation.json :: ibitcount.tail",
  "claim": "`single-template-inference`, `0x04 marker in every observed instance`.",
  "finding": "Only BIT 2 is load-bearing. All 128 values with bit2 set compute the correct "
             "popcount; all 128 with bit2 clear return a wrong constant. Dense 0..255 on a "
             "fully synthesized program, deterministic across two gated launches.",
  "evidence": "raw/m4_20260828_run0{1,2}/sweep.jsonl arm=IBITCOUNT field=tail",
  "recommendation": "promote to hardware-run with the bit-2 rule; this was the ONLY field "
                    "blocking `ibitcount`."},
 {"id": "DEF-0139-4", "where": "cross-experiment: EXP-0112 register-aliasing rule",
  "claim": "registers alias r(R mod 64) for R in [64,112] and fault at 126/127.",
  "finding": "Does NOT transfer to `iadd2.dst`. At dst=140/141 (reg 70, which would alias "
             "r6) the sum did not appear in r6. And the fault boundary is much lower here: "
             "reg >= 96 (dst >= 192) faults REPRODUCIBLY over 60 dense values (5/5 attempts "
             "each, healthy baselines), consistent with EXP-0020's `up to 96 regs`.",
  "evidence": "raw/m4_20260828_run0{1,2}/sweep.jsonl arm=IADD2 field=dst; "
              "raw/m4_20260828_reval01/revalidate.jsonl",
  "recommendation": "scope EXP-0112's aliasing claim to the families it was measured on; "
                    "do not generalize it to iadd2's destination field."},
 {"id": "DEF-0139-5", "where": "tools/agx-isa/db.json :: isel_reg8 (no corpus instance)",
  "claim": "`adopts the isel8 field layout` -- inferred, never observed.",
  "finding": "EXTRAPOLATE-AND-TEST: constructing it by rewriting the `isel8` anchor's "
             "byte+2 from 0x0f to 0x25 produces an instruction the hardware ACCEPTS and "
             "executes deterministically (it changes the result rather than faulting), and "
             "all seven of its fields respond to a dense 0..255 sweep. The layout claim "
             "survives; the instruction is real and reachable even though our own compiler "
             "never emits it.",
  "evidence": "raw/m4_20260828_run0{1,2}/sweep.jsonl arm=ISEL_REG8",
  "recommendation": "keep the descriptor; record that it is hardware-reachable by "
                    "construction, not merely inferred."},
 {"id": "DEF-0139-6", "where": "this experiment's own harness (self-reported)",
  "claim": "n/a",
  "finding": "The ICMPSEL arm was fed the INTEGER input vector while its host oracle was "
             "computed from the float vector (mode == 'float_in' never equalled the "
             "'float' the input selector tested for). Found by the newly mandated "
             "periodic baseline re-validation, not by inspection. The captured bytes are "
             "exactly what `(a<b)?1:0` produces for A_IN/B_IN reinterpreted as float32 with "
             "denormals flushed to zero, so the arm's observations are sound and are scored "
             "against its own gated baseline instead.",
  "evidence": "raw/m4_20260828_run02/03_baseline.jsonl; analysis/verdicts.py header",
  "recommendation": "none for db.json; recorded so a reader can see why ICMPSEL's reference "
                    "is its observed baseline rather than a host formula."},
]

if __name__ == "__main__":
    main()
