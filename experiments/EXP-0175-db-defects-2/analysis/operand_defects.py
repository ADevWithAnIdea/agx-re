#!/usr/bin/env python3
"""EXP-0175 Task 3 — the WRONG-OPERAND defect class, enumerated on purpose.

Four instances of this class were found BY ACCIDENT: `fspecial`'s operands
SWAPPED, `imad` with no srcA modelled, `cvt_bf16.src` fully match-pinned so it
cannot be the source it names, and `cvt_f2h_dst.src` declaring 8 bits with only
4 choosable while labelled `hardware-run` inside the emittable set (plus
`falu2_uni.usrc` at 7 of 8).

None of them is visible to `roundtrip_test.py`: EXP-0170 proved that suite passes
against an assembler that cannot clear a bit, and EXP-0173 proved it also passes
with `falu3.srcA` and `srcB` SWAPPED. So the class has to be enumerated
structurally.

WHAT THIS SCRIPT LOOKS FOR
  A. name-implies-operand but ZERO free bits          -> cannot select anything
  B. name-implies-operand, declared width > free bits -> declares more choice
                                                         than the descriptor allows
  C. an 8-bit operand descriptor with < 7 free bits   -> cannot address the file
  D. a 4-bit register nibble                          -> r0..r15 ONLY (a known
                                                         compaction, recorded so
                                                         nobody reads it as 96)
  E. an operand named in the descriptor's own semantics but ABSENT from `fields`
  F. an operand-named field NOT typed `reg`           -> the name promises an
                                                         operand the type denies
  G. a validation.json `range` claiming more values than the descriptor can encode
  H. descriptors whose own committed text already admits a SWAP / mislabel

REGISTER-FILE FACTS it is cross-checked against (docs/isa/README.md):
  * the GPR file is 96 entries, r0..r95, a hard silicon boundary; r96..r127 fault
    as a memory index and read 0 as an ALU source (RT-7).
  * operand bytes are `(reg << 1) | size`, so SEVEN bits are needed to span
    r0..r127 and cover the 96-register file. `fspecial` maps byte+3 0..191 onto
    r0..r95 by `reg = (byte+3) >> 1`.
  * a 4-bit `dst` nibble reaches r0..r15 ONLY -- the documented compaction, and
    r15 is not writable through it (EXP-0168).
  * aliasing period is NOT universal: mod-64 on the `falu2` ALU (EXP-0112), NOT
    on `iadd2.dst` (EXP-0139), and period 16 on the fragment stage for
    `tex_sample.coord` (EXP-0172). Never carry an operand model across families.

    python3 analysis/operand_defects.py      # writes analysis/operand_defects.json

CLEAN-ROOM: pure analysis over our own db.json + validation.json.
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
REPO = os.path.abspath(os.path.join(EXP, "..", ".."))
D = os.path.join(REPO, "tools", "agx-isa")

EMIT = {"hardware-run", "isolated-byte-diff"}

# A field NAME implies an operand if it matches one of these. Deliberately broad;
# false positives are cheap (they are reported with their reason) and a miss is not.
OPERAND_NAME = re.compile(
    r"^(src|dst|usrc|addend|operand|coord|index|idx|base|reg|oper)"
    r"|(_reg|_src|_dst|reg_|src_|dst_)"
    r"|^(srcA|srcB|srcC|ray_param|lane)",
    re.I)
# ...minus names that merely CONTAIN one of those but are plainly not operands.
NOT_OPERAND = re.compile(
    r"(class|flag|mod|size|fmt|type|mode|cache|marker|desc|en$|_en|sel$|"
    r"width|off$|_off|slot|scope|kind|form|shape|neg$|top$|hi$|lo$|bit\d|"
    # names that CONTAIN an operand word but denote a flag/mode about the operand
    r"_imm|_uni|_ext|_mask|_present|_gate|_companion|_full|_comp|_enable)",
    re.I)

GPR_FILE = 96            # r0..r95, hard silicon boundary (RT-7)
OPERAND_BITS = 7         # (reg<<1)|size spans r0..r127 in 8 bits -> 7 register bits


def covered_mask(instr):
    m = 0
    for (s, w, _v) in instr.get("match", []):
        m |= ((1 << w) - 1) << s
    return m


def claimed_values(rng):
    """Largest 'N values' / 'N of M' count a validation.json range string claims."""
    if not rng:
        return None
    best = None
    # NOTE: "N distinct encodings" counts whole-INSTRUCTION encodings, not field
    # values, so it is deliberately NOT a source of a claimed field-value count.
    for pat in (r"(\d+)\s+of\s+(\d+)", r"all\s+(\d+)\s+values", r"(\d+)\s+values"):
        for mm in re.finditer(pat, rng):
            n = int(mm.group(1))
            best = n if best is None else max(best, n)
    return best


def main():
    # `--db PATH` runs the same hunt against another tree (used to prove the hunt
    # reproduces the four instances that were previously found by accident, two of
    # which EXP-0175's own edits then resolved). `--out NAME` names the report.
    dbp = os.path.join(D, "db.json")
    outn = "operand_defects.json"
    a = sys.argv[1:]
    while a:
        if a[0] == "--db":
            dbp = a[1]; a = a[2:]
        elif a[0] == "--out":
            outn = a[1]; a = a[2:]
        else:
            a = a[1:]
    db = json.load(open(dbp))
    val = json.load(open(os.path.join(D, "validation.json")))
    emittable = set(val["coverage"]["emittable_mnemonics"])

    rows = []
    for instr in db["instructions"]:
        m = instr["mnemonic"]
        cov = covered_mask(instr)
        sem = (instr.get("semantics") or "") + " " + (instr.get("provenance") or "")
        names = {f["name"] for f in instr.get("fields", [])}
        vent = val["instructions"].get(m, {})

        # ---- E: operands the descriptor's own text names but does not model ----
        # A token is SATISFIED if a field carries that exact name, or a name that
        # starts with it. `srcA` is ALSO satisfied by a plain `src` field when the
        # text names no other source -- a one-source op legitimately calls it `src`.
        named = sorted(set(re.findall(r"\bsrc[ABCD]\b|\baddend\b", sem)))
        srcs = [t for t in named if t.startswith("src")]
        missing = []
        for t in named:
            if any(f == t or f.startswith(t) for f in names):
                continue
            if t == "srcA" and len(srcs) == 1 and "src" in names:
                continue
            missing.append(t)
        if missing:
            rows.append({
                "mnemonic": m, "field": None, "defect": "E-operand-named-but-absent",
                "detail": "the descriptor's own semantics/provenance name %s, but "
                          "there is no such field; modelled fields are %s"
                          % (", ".join("`%s`" % t for t in missing), sorted(names)),
                "operands_named_in_text": named, "operands_missing": missing,
                "instruction_emittable": m in emittable,
                "severity": "high" if m in emittable else "medium"})

        # ---- H: descriptors that already admit a swap / mislabel in their text ----
        if re.search(r"SWAPPED|swapped|operand swap|operands? (are )?reversed|"
                     r"OPERAND LABELS ARE SWAPPED|backwards", sem):
            rows.append({
                "mnemonic": m, "field": None, "defect": "H-self-declared-operand-swap",
                "detail": "the committed text already records an operand swap or "
                          "mislabel for this descriptor; an emitter reading the field "
                          "NAMES gets it backwards",
                "instruction_emittable": m in emittable,
                "severity": "high" if m in emittable else "medium"})

        for f in instr.get("fields", []):
            n, st, w = f["name"], f["start"], f["width"]
            if not OPERAND_NAME.search(n) or NOT_OPERAND.search(n):
                continue
            span = ((1 << w) - 1) << st
            free = bin(span & ~cov).count("1")
            # exactly which bits of the field are pinned, and to what
            pin_mask = (cov & span) >> st
            pin_val = 0
            for (ms, mw, mv) in instr.get("match", []):
                for b in range(mw):
                    bit = ms + b
                    if st <= bit < st + w:
                        pin_val |= ((mv >> b) & 1) << (bit - st)
            row = val["instructions"].get(m, {}).get(n, {})
            lab = row.get("label")
            base = {"mnemonic": m, "field": n, "width": w, "start": st,
                    "free_bits": free, "legal_values": 1 << free,
                    "type": f.get("type"), "label": lab,
                    "range": row.get("range"),
                    "pinned_mask": pin_mask, "pinned_value": pin_val,
                    "legal_form": ("(v & 0x%02x) == 0x%02x" % (pin_mask, pin_val))
                                  if pin_mask else "any value",
                    "instruction_emittable": m in emittable,
                    "emitter_grade_label": lab in EMIT}

            defects = []
            if free == 0:
                defects.append(("A-fully-pinned",
                                "every bit of this operand's span is pinned by the "
                                "descriptor's own `match`: it has exactly ONE legal "
                                "value and cannot be the operand it names"))
            elif free < w:
                defects.append(("B-declares-more-than-it-can-choose",
                                "declares %d bits but only %d are choosable; %d are "
                                "pinned by `match`" % (w, free, w - free)))
            if w == 8 and free < OPERAND_BITS and f.get("type") in ("reg", "raw"):
                defects.append(("C-cannot-address-the-file",
                                "an 8-bit operand descriptor is `(reg<<1)|size`, so 7 "
                                "register bits are needed to span r0..r127 and cover "
                                "the %d-entry file; this field has %d free bits and its "
                                "own match forces %s, so only %d of 256 operand bytes "
                                "are legal encodings of it"
                                % (GPR_FILE, free,
                                   "(v & 0x%02x) == 0x%02x" % (pin_mask, pin_val),
                                   1 << free)))
            if w == 4 and f.get("type") == "reg":
                defects.append(("D-nibble-compaction",
                                "a 4-bit register nibble reaches r0..r15 ONLY -- the "
                                "documented compaction, NOT 96 registers; and r15 is "
                                "not writable through it (EXP-0168)"))
            if f.get("type") not in ("reg",) and re.match(r"^(src|dst|usrc|addend)", n, re.I):
                defects.append(("F-operand-name-non-operand-type",
                                "named like an operand but typed `%s`, so nothing in "
                                "the descriptor says it selects a register"
                                % f.get("type")))
            cv = claimed_values(row.get("range"))
            if cv is not None and cv > (1 << free):
                defects.append(("G-range-claims-more-than-encodable",
                                "validation.json range claims %d values but the "
                                "descriptor permits only %d legal encodings of this "
                                "field. This is a validation.json RANGE-STRING defect "
                                "(the sweep covered the whole BYTE; the field is "
                                "narrower), owned by the label owner, not a db.json "
                                "encoding error." % (cv, 1 << free)))

            for code, detail in defects:
                sev = "high" if (m in emittable and code in
                                 ("A-fully-pinned", "B-declares-more-than-it-can-choose",
                                  "C-cannot-address-the-file",
                                  "G-range-claims-more-than-encodable")) else \
                      ("medium" if code != "D-nibble-compaction" else "info")
                if code == "A-fully-pinned" and lab in EMIT:
                    sev = "high"
                rows.append(dict(base, defect=code, detail=detail, severity=sev))

    order = {"high": 0, "medium": 1, "info": 2}
    rows.sort(key=lambda r: (not r.get("instruction_emittable"),
                             order.get(r["severity"], 3),
                             r["defect"], r["mnemonic"], r.get("field") or ""))

    counts = {}
    for r in rows:
        counts[r["defect"]] = counts.get(r["defect"], 0) + 1
    out = {"_meta": {
        "experiment": "EXP-0175",
        "question": "every field whose NAME implies an operand but whose bits cannot "
                    "select one",
        "db": dbp,
        "register_file_facts": {
            "gpr_entries": GPR_FILE,
            "operand_byte_encoding": "(reg << 1) | size, 7 register bits span r0..r127",
            "fspecial_reg_formula": "reg = (byte+3) >> 1, mapping 0..191 onto r0..r95",
            "four_bit_dst": "r0..r15 compaction only; r15 not writable (EXP-0168)",
            "aliasing_is_family_specific": "mod-64 on falu2 (EXP-0112); NOT on iadd2.dst "
                                           "(EXP-0139); period 16 on the fragment stage "
                                           "for tex_sample.coord (EXP-0172)"},
        "not_visible_to_roundtrip": "EXP-0170 (assembler that cannot clear a bit) and "
                                    "EXP-0173 (falu3.srcA<->srcB swapped) both pass "
                                    "roundtrip_test.py unmodified",
        "total_rows": len(rows),
        "by_defect": counts,
        "high_severity": sum(1 for r in rows if r["severity"] == "high"),
        "in_emittable_instructions": sum(1 for r in rows if r["instruction_emittable"]),
    }, "rows": rows}
    json.dump(out, open(os.path.join(HERE, outn), "w"), indent=1)

    print("operand-named fields with a structural defect: %d rows" % len(rows))
    print("  in EMITTABLE instructions: %d ; high severity: %d"
          % (out["_meta"]["in_emittable_instructions"], out["_meta"]["high_severity"]))
    print()
    for k in sorted(counts):
        print("  %-38s %d" % (k, counts[k]))
    print("\n%-4s %-22s %-14s %3s %5s %-22s %-34s"
          % ("emit", "instr", "field", "w", "free", "label", "defect"))
    for r in rows:
        if r["severity"] == "info":
            continue
        print("%-4s %-22s %-14s %3s %5s %-22s %-34s"
              % ("YES" if r["instruction_emittable"] else "",
                 r["mnemonic"], r.get("field") or "-",
                 r.get("width", ""), r.get("free_bits", ""),
                 str(r.get("label")), r["defect"]))
    print("\n(D-nibble-compaction rows are `info` and are in the JSON, not printed here.)")
    print("wrote %s" % os.path.join(HERE, outn))
    return 0


sys.exit(main())
