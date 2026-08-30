#!/usr/bin/env python3
"""EXP-0173: find every descriptor field that CANNOT do what its name promises.

The class "a named operand field that cannot be an operand" has been found three
times by accident (fspecial's swapped operands, imad with no srcA modelled,
cvt_bf16.src fully match-pinned). This looks for it on purpose, using only
DECISIVE mechanical tests -- properties that make the field unusable no matter
what the hardware does:

  P1  ZERO FREE BITS      the whole span is pinned by the descriptor's own
                          `match`: exactly one legal value, so it cannot name an
                          operand. (cvt_bf16.src is the known member.)
  P1c PARTIALLY PINNED    the descriptor declares W bits but only F < W are
                          choosable, because its own `match` pins the rest. The
                          field is narrower than the descriptor says it is, and
                          every sweep driven through it under-covers silently.
  P4  OVERLAPPING FIELDS  two fields in the same descriptor share bits, so
                          setting one silently changes the other -- an emitter
                          cannot choose them independently.
  P5  OUT OF RANGE        the span lies partly or wholly beyond `length * 8`.

Reported as ADVISORY, not defect, because it may be a true hardware limit:

  A1  NARROW REGISTER FIELD  an operand-named field with < 7 free bits and NO
                             sibling field whose name suggests an extension
                             (*_ext*, *_hi, *_lo, *class*, *mode*). The AGX
                             compact forms legitimately use a 4-bit dst nibble
                             plus an extension elsewhere; where no extension
                             exists, the descriptor caps the operand at
                             2**free registers and the doc should say so.

    python3 experiments/EXP-0173-closure-audit/analysis/operand_sanity.py
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(EXP))
ISA = os.path.join(ROOT, "tools", "agx-isa")
EMIT = {"hardware-run", "isolated-byte-diff"}

OPERAND_NAME = re.compile(
    r"^(dst|src|srcA|srcB|srcC|srcD|usrc|src_reg|src_ext\d*|dst_lo|dst_hi|dst_ext\d*|"
    r"data|data_reg|addr|addr_desc\w*|base|base_slot|coord\w*|sampler|tex\w*|target|"
    r"imm\w*|off|offset|idx_off|index|reg|operands?)$", re.I)
EXT_HINT = re.compile(r"(ext|_hi$|_lo$|class|mode|width|size)", re.I)


def main():
    db = json.load(open(os.path.join(ISA, "db.json")))
    val = json.load(open(os.path.join(ISA, "validation.json")))
    emittable = set(val["coverage"]["emittable_mnemonics"])
    readme = open(os.path.join(ROOT, "docs", "isa", "README.md")).read()

    defects, advisories = [], []
    for i in db["instructions"]:
        m = i["mnemonic"]
        length = i.get("length", 0)
        covered = 0
        for (s, w, _v) in i.get("match", []):
            covered |= ((1 << w) - 1) << s
        flds = i.get("fields", [])
        names = [f["name"] for f in flds]
        has_ext_sibling = any(EXT_HINT.search(n) for n in names)

        # P4: field/field overlap (decisive, and independent of any name)
        for a in range(len(flds)):
            for b in range(a + 1, len(flds)):
                fa, fb = flds[a], flds[b]
                sa = ((1 << fa["width"]) - 1) << fa["start"]
                sb = ((1 << fb["width"]) - 1) << fb["start"]
                if sa & sb:
                    defects.append({
                        "mnemonic": m, "field": "%s / %s" % (fa["name"], fb["name"]),
                        "test": "P4 OVERLAPPING FIELDS",
                        "detail": "spans share bits %#x — setting one silently changes the other; "
                                  "an emitter cannot choose them independently" % (sa & sb),
                        "instruction_emittable": m in emittable,
                        "labels": [val["instructions"].get(m, {}).get(fa["name"], {}).get("label"),
                                   val["instructions"].get(m, {}).get(fb["name"], {}).get("label")],
                    })

        for f in flds:
            name = f["name"]
            span = ((1 << f["width"]) - 1) << f["start"]
            free = bin(span & ~covered).count("1")
            lab = val["instructions"].get(m, {}).get(name, {}).get("label", "MISSING")
            operandish = bool(OPERAND_NAME.match(name))

            # P5 (decisive, any field)
            if length and (f["start"] + f["width"]) > length * 8:
                defects.append({
                    "mnemonic": m, "field": name, "test": "P5 OUT OF RANGE",
                    "detail": "span ends at bit %d but the descriptor's length is %d bytes "
                              "(%d bits)" % (f["start"] + f["width"], length, length * 8),
                    "label": lab, "emitter_grade_label": lab in EMIT,
                    "instruction_emittable": m in emittable})

            if not operandish:
                continue
            warned = bool(re.search(r"`%s`" % re.escape(m), readme)) and \
                     bool(re.search(r"(SWAP|misleading|NOT the|no first operand|pinned|inert|"
                                    r"REFUTED|do not emit)", readme, re.I))
            base = {"mnemonic": m, "field": name, "start": f["start"], "width": f["width"],
                    "free_bits": free, "legal_values": 1 << free, "label": lab,
                    "emitter_grade_label": lab in EMIT,
                    "instruction_emittable": m in emittable,
                    "mnemonic_appears_in_docs_isa_readme": bool(
                        re.search(r"`%s[`.]" % re.escape(m), readme))}
            if free == 0:
                defects.append(dict(base, test="P1 ZERO FREE BITS",
                    detail="every bit of the span is pinned by this descriptor's own match: "
                           "exactly ONE legal value, so the field cannot name an operand"))
            elif free < f["width"]:
                defects.append(dict(base, test="P1c PARTIALLY PINNED",
                    detail="descriptor declares %d bits but only %d are choosable (%d legal "
                           "values); the rest are pinned by its own match, so the field is "
                           "narrower than it says and any sweep through it under-covers"
                           % (f["width"], free, 1 << free)))
            elif free < 7 and re.match(r"^(dst|src[A-D]?|src_reg|data_reg|usrc)$", name, re.I) \
                    and not has_ext_sibling:
                advisories.append(dict(base, test="A1 NARROW REGISTER FIELD",
                    detail="%d free bits and NO sibling extension field in this descriptor, so "
                           "the operand is capped at r0..r%d. May be a true hardware limit; the "
                           "doc must say which." % (free, (1 << free) - 1)))

    known = {("fspecial", "dst"), ("fspecial", "src"), ("fspecial", "src_ext"),
             ("imad", "srcA"), ("cvt_bf16", "src"), ("op04_len8", "dst")}
    new_defects = [d for d in defects if (d["mnemonic"], d.get("field")) not in known]
    out = {"_meta": {
        "experiment": "EXP-0173",
        "question": "which descriptor fields cannot do what their name promises",
        "decisive_defects": len(defects),
        "decisive_defects_by_test": {t: sum(1 for d in defects if d["test"].startswith(t))
                                     for t in ("P1 ", "P1c", "P4", "P5")},
        "decisive_defects_in_emittable_instructions":
            sum(1 for d in defects if d["instruction_emittable"]),
        "decisive_defects_beyond_the_four_known": len(new_defects),
        "advisories": len(advisories),
        "advisories_in_emittable_instructions":
            sum(1 for a in advisories if a["instruction_emittable"]),
        "note": "A1 advisories are NOT presented as defects: a 4-bit dst nibble is a real AGX "
                "compact-form encoding. They are the places where the descriptor caps an "
                "operand and the normative doc must say so explicitly.",
    }, "decisive_defects": defects, "advisories": advisories}
    p = os.path.join(HERE, "operand_sanity.json")
    json.dump(out, open(p, "w"), indent=1)
    print(json.dumps(out["_meta"], indent=1))
    print("\n=== DECISIVE: a named operand field that cannot be an operand ===")
    print("%-34s %-22s %-6s %-20s %s" % ("instr.field", "test", "emit?", "label", "in README?"))
    for d in sorted(defects, key=lambda d: (not d["instruction_emittable"], d["mnemonic"])):
        print("%-34s %-22s %-6s %-20s %s" % (
            d["mnemonic"] + "." + str(d.get("field")), d["test"],
            "YES" if d["instruction_emittable"] else "-",
            str(d.get("label", d.get("labels"))),
            "yes" if d.get("mnemonic_appears_in_docs_isa_readme") else "**NO**"))
    print("\n=== ADVISORY: narrow register field with no extension sibling ===")
    for a in sorted(advisories, key=lambda a: (not a["instruction_emittable"], a["mnemonic"])):
        print("%-34s free=%d cap=r0..r%-3d %-5s %s" % (
            a["mnemonic"] + "." + a["field"], a["free_bits"], a["legal_values"] - 1,
            "EMIT" if a["instruction_emittable"] else "", a["label"]))
    print("\nwrote", p)


if __name__ == "__main__":
    sys.exit(main())
