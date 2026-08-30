#!/usr/bin/env python3
"""DB-defect triage -- apply the class (a) SEMANTICS and class (b) FIELD-MODEL
fixes from the `db_defects` backlog to tools/agx-isa/db.json.

Class definitions (from the dispatch):
  (a) semantics-only annotation           -> semantics/provenance text only
  (b) field-model change, decoding UNCHANGED -> field split / rename / retype /
      enum extension.  `match` and `length` are NEVER touched here, so which
      descriptor fires and how many bytes it consumes is bit-for-bit unchanged.
  (c) match/length change that DOES alter decoding -> NOT applied by this script
      (see work/DB-DEFECT-TRIAGE.md and work/dbtriage/propose_c_changes.py).

Because tools/agx-isa/validate_labels.py hard-requires a validation.json entry
for every db.json field (and forbids entries for fields db.json does not have),
every (b) change is mirrored into validation.json.  Rule followed here:
  * RENAME  -> the entry moves verbatim (same bits were swept), + a rename note.
  * SPLIT   -> each child inherits the parent's label/target/evidence verbatim
               and gets the parent's range narrowed to the child's own bits.
               NO label is ever strengthened.  This script never promotes.
  * RETYPE / ENUM -> entry untouched.
The coverage block is recomputed from the resulting entries.

Idempotent: re-running detects already-applied changes and skips them.

Usage: python3 work/dbtriage/apply_ab_defects.py [--dry-run]
"""
import hashlib, json, os, sys, copy

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
DBP = os.path.join(REPO, "tools", "agx-isa", "db.json")
VALP = os.path.join(REPO, "tools", "agx-isa", "validation.json")

LABELS = ("hardware-run", "isolated-byte-diff", "corpus-correlation", "tokenization-only",
          "single-template-inference", "api-accept-reject", "host-private", "untested")
EMIT_OK = ("hardware-run", "isolated-byte-diff")

applied, skipped = [], []

_FALU3_SEM = (
    "OPERAND-SLOT RENAME (EXP-0138, HW-VALIDATED, 1809 + 2321 cases): the former names "
    "`dst_lo`/`dst`/`srcA`/`srcB`/`srcC` were wrong. byte0's high nibble is the whole "
    "DESTINATION (`dst`, 14/16 exact); byte+1 is the FIRST source descriptor (`srcA`, "
    "228/256); byte+3 is the SECOND source (`srcB`, 228/256); byte+5 is the THIRD source "
    "(`srcC`, 252/256); byte+4 is a CONTROL byte (`ctrl_len`) whose low 2 bits re-length the "
    "instruction (192/256). The 28 `srcA`/`srcB` misses are exactly the descriptor values "
    "with bit0 CLEAR: bit0 is the operand SIZE bit (1 = 32-bit, 0 = 16-bit) and a 16-bit "
    "read of an f32-seeded register returns 0.0 -- which CONFIRMS (reg<<1)|is32. byte+5's "
    "bit0 does NOT behave as a size bit."
)


# ---------------------------------------------------------------- helpers ----
def ins(db, m):
    for i in db["instructions"]:
        if i["mnemonic"] == m:
            return i
    raise KeyError(m)


def fidx(i, name):
    for k, f in enumerate(i["fields"]):
        if f["name"] == name:
            return k
    return -1


def append_sem(db, m, tag, text):
    """(a) append an annotation to `semantics`, once."""
    d = ins(db, m)
    if tag in d["semantics"]:
        skipped.append("(a) %s :: %s" % (m, tag))
        return
    d["semantics"] = d["semantics"].rstrip() + " " + text.strip()
    applied.append("(a) %s :: %s" % (m, tag))


def rename(db, val, m, old, new, note):
    """(b) rename one field; bits, width and type unchanged."""
    d = ins(db, m)
    if fidx(d, new) >= 0 and fidx(d, old) < 0:
        skipped.append("(b) %s :: rename %s->%s" % (m, old, new))
        return
    k = fidx(d, old)
    assert k >= 0, "%s.%s not found" % (m, old)
    d["fields"][k]["name"] = new
    e = val["instructions"][m].pop(old)
    e = dict(e)
    e["note"] = ((e.get("note", "") or "").rstrip() + " " + note).strip()
    val["instructions"][m][new] = e
    applied.append("(b) %s :: rename %s -> %s" % (m, old, new))


def retype(db, m, name, newtype, enum=None):
    d = ins(db, m)
    k = fidx(d, name)
    assert k >= 0, "%s.%s" % (m, name)
    if d["fields"][k]["type"] == newtype and (enum is None or d["fields"][k].get("enum") == enum):
        skipped.append("(b) %s :: retype %s" % (m, name))
        return
    d["fields"][k]["type"] = newtype
    if enum is not None:
        d["fields"][k]["enum"] = enum
    applied.append("(b) %s :: retype %s -> %s" % (m, name, newtype))


def add_enum(db, m, name, extra):
    d = ins(db, m)
    k = fidx(d, name)
    assert k >= 0
    e = d["fields"][k].setdefault("enum", {})
    new = {k2: v for k2, v in extra.items() if k2 not in e}
    if not new:
        skipped.append("(b) %s :: enum %s" % (m, name))
        return
    e.update(new)
    applied.append("(b) %s :: enum %s += %s" % (m, name, sorted(new)))


def split(db, val, m, old, children, note):
    """(b) replace field `old` with `children` = [(name,start,width,type,enum,range_suffix)].
    The children must exactly tile the parent's bits."""
    d = ins(db, m)
    if fidx(d, children[-1][0]) >= 0:      # last child is always a NEW name
        skipped.append("(b) %s :: split %s" % (m, old))
        return
    k = fidx(d, old)
    assert k >= 0, "%s.%s not found" % (m, old)
    par = d["fields"][k]
    tot = sum(c[2] for c in children)
    assert tot == par["width"], "%s.%s: children width %d != %d" % (m, old, tot, par["width"])
    assert children[0][1] == par["start"], "%s.%s: child start mismatch" % (m, old)
    exp = par["start"]
    for c in children:
        assert c[1] == exp, "%s.%s: gap/overlap at %s" % (m, old, c[0])
        exp += c[2]
    newf = []
    for (nm, st, w, ty, en, _rs) in children:
        f = {"name": nm, "start": st, "width": w, "type": ty}
        if en:
            f["enum"] = en
        newf.append(f)
    d["fields"][k:k + 1] = newf

    pe = val["instructions"][m].pop(old)
    for (nm, st, w, ty, en, rs) in children:
        e = copy.deepcopy(pe)
        if rs:
            e["range"] = rs
        e["note"] = ((e.get("note", "") or "").rstrip() + " " + note).strip()
        val["instructions"][m][nm] = e
    applied.append("(b) %s :: split %s -> %s" % (m, old, ", ".join(c[0] for c in children)))


def recompute_coverage(db, val):
    counts = {k: 0 for k in LABELS}
    n_fields = 0
    emittable = []
    for i in db["instructions"]:
        m = i["mnemonic"]
        entry = val["instructions"][m]
        all_emit = True
        for f in i.get("fields", []):
            lab = entry[f["name"]]["label"]
            counts[lab] += 1
            n_fields += 1
            if lab not in EMIT_OK:
                all_emit = False
        if not i.get("fields"):
            all_emit = entry.get("_instruction", {}).get("label") in EMIT_OK
        if "EMITTABLE VETO" in (entry.get("_instruction") or {}).get("note", ""):
            all_emit = False
        if all_emit:
            emittable.append(m)
    cov = val["coverage"]
    cov["total_instructions"] = len(db["instructions"])
    cov["total_fields"] = n_fields
    cov["by_label"] = counts
    cov["by_label_pct"] = {k: round(100.0 * counts[k] / n_fields, 1) for k in LABELS}
    cov["emittable_instructions"] = len(emittable)
    cov["emittable_mnemonics"] = sorted(emittable)
    cov["decodable_not_yet_emittable"] = len(db["instructions"]) - len(emittable)
    # corrected emittability metric (dispatch Task 2): data words are decode
    # scaffolding, not instructions an emitter must produce.
    dw = sorted(i["mnemonic"] for i in db["instructions"]
                if i.get("emitter_role") == "data-word")
    cov["data_word_descriptors"] = len(dw)
    cov["data_word_mnemonics"] = dw
    cov["emitter_relevant_instructions"] = len(db["instructions"]) - len(dw)
    cov["emittable_of_emitter_relevant"] = len([m for m in emittable if m not in set(dw)])


# ================================================================= MAIN ======
def main():
    dry = "--dry-run" in sys.argv
    db = json.load(open(DBP))
    val = json.load(open(VALP))

    # ---------------------------------------------------------------------
    # EXP-0138 -- float ALU
    # ---------------------------------------------------------------------
    # (b) falu2.mod_lo is an OPERAND-SOURCE-CLASS field, split 1 + 2 bits.
    split(db, val, "falu2", "mod_lo", [
        ("srcA_class", 40, 1, "mod", None,
         "byte+5 bit0, within the dense 0..7 sweep of the former 3-bit `mod_lo`"),
        ("srcB_class", 41, 2, "enum",
         {"0": "GPR (srcB_reg)", "1": "non-GPR file / inline immediate (srcB_reg)",
          "2": "reads 0.0", "3": "reads 0.0"},
         "byte+5 bits[2:1], within the dense 0..7 sweep of the former 3-bit `mod_lo`"),
    ], "FIELD-MODEL CORRECTION (EXP-0138, HW): the former 3-bit `mod_lo` is an "
       "operand-source-class field -- bit0 selects srcA's source class, bits[2:1] select "
       "srcB's. Bit2 DOMINATES bit1 (mod_lo=6 reads 0.0, not the uniform value mod_lo=2 "
       "reads at the same index). Same bits, same sweep; only the field boundary changed.")

    append_sem(db, "falu2", "INLINE FLOAT IMMEDIATE",
        "INLINE FLOAT IMMEDIATE (EXP-0138, HW-VALIDATED): with `srcB_class` == 1 the "
        "`srcB_reg` field is NOT a register index and its bit6 is LIVE -- srcB_reg in 0..63 "
        "indexes the uniform register file, srcB_reg in 64..127 supplies an INLINE 8-bit "
        "MINIFLOAT IMMEDIATE with k = srcB_reg-64, e = k>>3, m = k&7, value = m*2^-5 for "
        "e==0 else (8+m)*2^(e-6). Confirmed at k = 0,2,3,31,32,48,56,61,62,63 -> 0, 0.0625, "
        "0.09375, 1.875, 2.0, 8.0, 16.0, 26.0, 28.0, 30.0. Indices 126/127 do NOT fault in "
        "this mode (they are the immediates 28.0/30.0), unlike GPR mode where EXP-0112 "
        "recorded a fault. An emitter that treats srcB_reg as a plain register in this mode "
        "emits the wrong operand.")

    # (b) falu3 / falu3_ext -- the field NAMES were wrong (EXP-0138 H-FALU3-LAYOUT).
    for m in ("falu3", "falu3_ext"):
        if fidx(ins(db, m), "ctrl_len") >= 0:
            skipped.append("(b) %s :: falu3 operand-slot rename block" % m)
            retype(db, m, "ctrl_len", "mod")
            append_sem(db, m, "OPERAND-SLOT RENAME", _FALU3_SEM)
            continue
        note = ("FIELD RENAME (EXP-0138 H-FALU3-LAYOUT, HW, 1809+2321 cases): db.json's "
                "old names put the destination in a source slot. byte0 high nibble is the "
                "DESTINATION; byte+1 is the FIRST source descriptor; byte+3 the SECOND; "
                "byte+5 the THIRD; byte+4 is a CONTROL byte whose low 2 bits are the "
                "0x09-group LENGTH selector. Same bits, same sweep -- name only.")
        rename(db, val, m, "srcC", "srcC_keep", note)     # park, avoid collisions
        rename(db, val, m, "srcB", "ctrl_len", note)
        rename(db, val, m, "srcA", "srcB", note)
        rename(db, val, m, "dst", "srcA", note)
        rename(db, val, m, "dst_lo", "dst", note)
        rename(db, val, m, "srcC_keep", "srcC", note)
        retype(db, m, "ctrl_len", "mod")
        append_sem(db, m, "OPERAND-SLOT RENAME", _FALU3_SEM)
        _unused = (
            "OPERAND-SLOT RENAME (EXP-0138, HW-VALIDATED, 1809 + 2321 cases): the former "
            "names `dst_lo`/`dst`/`srcA`/`srcB`/`srcC` were wrong. byte0's high nibble is "
            "the whole DESTINATION (`dst`, 14/16 exact); byte+1 is the FIRST source "
            "descriptor (`srcA`, 228/256); byte+3 is the SECOND source (`srcB`, 228/256); "
            "byte+5 is the THIRD source (`srcC`, 252/256); byte+4 is a CONTROL byte "
            "(`ctrl_len`) whose low 2 bits re-length the instruction (192/256). The 28 "
            "`srcA`/`srcB` misses are exactly the descriptor values with bit0 CLEAR: bit0 is "
            "the operand SIZE bit (1 = 32-bit, 0 = 16-bit) and a 16-bit read of an "
            "f32-seeded register returns 0.0 -- which CONFIRMS (reg<<1)|is32. byte+5's bit0 "
            "does NOT behave as a size bit.")

    append_sem(db, "fspecial", "SAFETY",
        "SAFETY (EXP-0138, HW): byte+3 (`src`) values 192..255 (bit7 set) FAULT the command "
        "buffer or HANG the GPU -- run01 recorded 60 reproducible faults across 192..255 and "
        "run05 hung the GPU three times in a row at each of 192/193/194 under a 12 s "
        "watchdog, which stopped the arm under FIELD-SWEEP-PROTOCOL section 8. Only values 2 "
        "and 3 produce the correct rsqrt(4)=0.5; 188 other values silently return 0.0; "
        "values 6 and 7 leave the poison intact (the store never ran). An emitter must never "
        "set byte+3 bit7. The whole fspecial family stays PARTIAL / untested.")
    d = ins(db, "fspecial")
    if not d.get("emit_unsafe"):
        d["emit_unsafe"] = True
        applied.append("(b) fspecial :: emit_unsafe = True")
    else:
        skipped.append("(b) fspecial :: emit_unsafe")

    # ---------------------------------------------------------------------
    # EXP-0139 -- integer ALU
    # ---------------------------------------------------------------------
    append_sem(db, "ibfe", "WIDTH IS TAKEN MOD 32",
        "WIDTH IS TAKEN MOD 32, OFFSET IS LITERAL (EXP-0139 DEF-0139-2, HW, dense 0..63): "
        "`width` is taken MOD 32 -- the mod-32 model fits 64/64 stable values while a "
        "literal/clamp-at-32 model fits only 37/64, so width == 0 (mod 32) is the "
        "no-mask (extract-to-MSB) case and width=32 behaves exactly like width=0. `offset` "
        "on the SAME instruction obeys the OPPOSITE rule: it is literal, and 32..63 shift "
        "the field out entirely (result 0). The asymmetry is load-bearing for an emitter.")
    append_sem(db, "ibitcount", "TAIL RULE",
        "TAIL RULE (EXP-0139 DEF-0139-3, HW, dense 0..255 x2 gated launches): only BIT 2 of "
        "`tail` is load-bearing -- all 128 values with bit2 set compute the correct "
        "popcount, all 128 with bit2 clear return a wrong constant. The former '0x04 marker "
        "in every observed instance' was a single-template inference.")
    append_sem(db, "iadd2", "DESTINATION BOUNDS",
        "DESTINATION BOUNDS (EXP-0139 DEF-0139-4 + EXP-0146, HW): EXP-0112's r(R mod 64) "
        "register-ALIASING rule does NOT transfer to this field -- at dst=140/141 (register "
        "70, which would alias r6) the sum did not appear in r6. The fault boundary is also "
        "much lower here: dst byte 0xBE..0xFF (register index >= 95) raises a contained GPU "
        "ADDRESS FAULT, reproducibly over 60..66 dense values (5/5 attempts each, healthy "
        "baselines). Independently corroborates EXP-0020's ~96-entry GPR file from a "
        "different family and method. Emitter bound for this form: destination register <= 94.")
    append_sem(db, "isel_reg8", "HARDWARE-REACHABLE BY CONSTRUCTION",
        "HARDWARE-REACHABLE BY CONSTRUCTION (EXP-0139 DEF-0139-5): this descriptor has no "
        "corpus instance -- its layout was inferred from `isel8`. Extrapolate-and-test "
        "confirms it: rewriting the isel8 anchor's byte+2 from 0x0f to 0x25 produces an "
        "instruction the hardware ACCEPTS and executes deterministically (it changes the "
        "result rather than faulting), and all seven fields respond to a dense 0..255 sweep. "
        "Real and reachable even though our own compiler never emits it.")

    # ---------------------------------------------------------------------
    # EXP-0140 -- mov / control flow
    # ---------------------------------------------------------------------
    append_sem(db, "mov_imm", "IMMEDIATE IS 7 BITS",
        "IMMEDIATE IS 7 BITS (EXP-0140, HW, poisoned read-back): with imm_top = 1 "
        "(immediate 128..255) the instruction does NOT write the destination register at "
        "all, and unpadded it CONSUMES the following 2-byte instruction. EXP-0128 read this "
        "as a 'silent zero' only because its read-back buffer was zero-initialised; against "
        "a poisoned buffer the register is seen to keep its previous value (0xDEADBEEF "
        "survives). An emitter must treat the immediate as 7 bits: bit 7 selects a different "
        "(longer) instruction, it does not extend the immediate. "
        "DECODER GAP (EXP-0140, static): the 2-byte encoding with imm7 == 12 does not "
        "tokenize under the current length rule -- byte+1 = 0x0C makes the pair look like "
        "the 4-byte low-nibble-0xC preamble/get_sr group. It is the ONLY immediate in 0..127 "
        "with this property, checked exhaustively over all 16 dst values. Decoder defect, "
        "not necessarily a hardware one; fixing it is a LENGTH-RULE change and is deferred "
        "to a corpus A/B.")
    # (b) sel.body is three located bytes, not one opaque 24-bit blob.
    split(db, val, "sel", "body", [
        ("b1", 8, 8, "mod", None,
         "byte+1 swept 0..255 dense x2 input vectors (8 ok / 248 silent_zero / 256 wrong_value "
         "across the two vectors)"),
        ("b2", 16, 8, "mod", None,
         "byte+2 swept 0..255 dense x2 input vectors (128 ok / 128 silent_zero / 128 "
         "wrong_value / 127 fault)"),
        ("selFalse", 24, 8, "imm", None,
         "byte+3 swept 0..255 dense x2 input vectors (510 ok / 2 fault)"),
    ], "FIELD-MODEL CORRECTION (EXP-0140, HW): `body` is not an opaque 24-bit field. byte+3 "
       "is the predicate-FALSE operand (bit7 = immediate flag, value = the byte itself; 255 "
       "immediate matches vs 1 in the register region); byte+1 and byte+2 are "
       "operand/predicate source selectors with distinct outcome classes over their full "
       "256-value range. Same bits, same sweep; only the field boundary changed.")

    append_sem(db, "reg_move_c1", "ONE INSTRUCTION, NOT SIX",
        "ONE INSTRUCTION, NOT SIX (EXP-0140, HW, byte+2 swept 0..255 in a single carrier): "
        "reg_move_c0 / reg_move_c1 / reg_move_c2var / reg_move_c9 / reg_move_cb / "
        "uniform_mov are NOT six instructions -- they are ONE 4-byte instruction whose byte+2 "
        "is a form selector, and db.json's five descriptors are five values of that one "
        "field. Only byte+2 in {0x01,0x05,0x11,0x15,0x21,0x25,0x31,0x35} actually moves a "
        "value; the probe found reg_move_c1 `ok`, reg_move_c0/reg_move_c2var `silent_zero` "
        "and reg_move_c9/reg_move_cb `wrong_value`. The byte+1 split into src_reg + src_flag "
        "also does not match hardware: bit7 selects immediate-vs-uniform-file. Collapsing "
        "the five descriptors is a MATCH change and is deferred to a corpus A/B.")

    # ---------------------------------------------------------------------
    # EXP-0141 -- memory
    # ---------------------------------------------------------------------
    append_sem(db, "device_load", "DESTINATION-PAIR AND ADDR_MODE",
        "DESTINATION-PAIR AND ADDR_MODE (EXP-0141, HW): `dst_lo` and `dst_ext9` carry NO "
        "register information. dst_lo must be exactly 1; only bit 0 of dst_ext9 is live and "
        "must be 1. Three constrained bits out of the nine the two fields span; the other "
        "six are don't-care. Established by 4/4 dst_lo values and 128/128 dst_ext9 values at "
        "four independent target registers (3, 7, 20, 33) plus the full 512-value 2-D "
        "product at r7, with an identical accepted set at every target register. SUPERSEDES "
        "EXP-M4-13's dst = dst_lo | (dst_ext9 << 2) (already retracted by EXP-0101) and "
        "EXP-0101's advice to copy the pair verbatim per addr_mode/ld_format shape: the pair "
        "is a fixed 3-bit enable pattern, not a per-shape token. Separately, `addr_mode` "
        "(byte+2) is INERT for a terminal scalar 32-bit indexed load -- all 256 values load "
        "correctly, including every code in the enum. CAVEAT: only that shape was tested; "
        "the enum may still select behaviour for the base-sharing / CF / RT forms it names.")
    retype(db, "device_load", "dst_lo", "mod")
    retype(db, "device_load", "dst_ext9", "mod")

    append_sem(db, "device_store", "ADDR_MODE BIT1 IS CONTEXT-DEPENDENT",
        "ADDR_MODE BIT1 IS CONTEXT-DEPENDENT (EXP-0141, HW): byte+2 bit 1 selects the DATA "
        "SOURCE -- clear = ALU-computed, set = direct live load-result. It is INERT when the "
        "data is ALU-computed (256/256 pass), which is the configuration EXP-0119 measured "
        "and reported as 'INERT here'; with a load-forwarded source only the 128 bit1-set "
        "values work and the other 128 store 0. Two observations, one rule.")

    for m in ("atomic_mem", "atomic_rmw"):
        split(db, val, m, "index_reg", [
            ("index_reg", 40, 7, "reg", None,
             "byte+5 bits 0..6, within the dense 0..255 sweep of the whole byte"),
            ("oper_reg_lo", 47, 1, "reg", None,
             "byte+5 bit7 = bit 0 of the RMW operand-register index; observed at both values"),
        ], "OPERAND-REGISTER SPLIT (EXP-0141, HW): the RMW operand register IS encoded in "
           "the instruction. operand_register_index = (byte+5 >> 7) | ((byte+6 & 0x3F) << 1), "
           "relative to the register the compiler's own encoding selects.")
        split(db, val, m, "addr_desc", [
            ("oper_reg_hi", 48, 6, "reg", None,
             "byte+6 bits 0..5 = bits 1..6 of the RMW operand-register index; indices 0..3 "
             "each constructed and read back"),
            ("addr_desc_hi", 54, 2, "mod", None,
             "byte+6 bits 6..7: DON'T-CARE (0x01/0x41/0x81/0xC1 all select index 3)"),
        ], "OPERAND-REGISTER SPLIT (EXP-0141, HW): proven at all four constructible indices "
           "-- 0 -> a[0]=7, 1 -> a[1]=1007, 2 -> a[2]=2007, 3 -> a[3]=3007 -- each with the "
           "redirected register's later reader zeroed (the same register-release contract "
           "EXP-0086/0089/0099 document for the ALU families). RESIDUAL UNKNOWN: with "
           "byte+5 = 0x80, byte+6 values 0x30 and 0x31 restore the BASELINE operand instead "
           "of selecting index 97/99, and they are the only two addendum cases whose "
           "acceptance disagreed between run21 and run22.")
        append_sem(db, m, "RMW OPERAND REGISTER IS NOT IMPLICIT",
            "RMW OPERAND REGISTER IS NOT IMPLICIT (EXP-0141, HW): the previous claim that "
            "the operand register 'is implicit (supplied by the preceding op / amode)' is "
            "REFUTED -- DOC-02 section 3 ranked it a MISSING field, 'the worst kind of gap "
            "for an emitter'. It is encoded, as `oper_reg_lo` (byte+5 bit7) | "
            "(`oper_reg_hi` << 1) (byte+6 bits 0..5). The carrier keeps a[0..3] = "
            "7/1007/2007/3007 live across atomic_fetch_add(o, a[0]); baseline byte+5/+6 = "
            "0x00/0x00 counts 7, byte+5 = 0x80 counts 1007, byte+6 = 0x01 counts 2007, and "
            "the addendum built index 3 -> 3007. The redirected register is CONSUMED: its "
            "later reader gets 0. NOTE: our atdevimm carrier uses a UNIFORM address yet the "
            "compiler emits byte+5/+6 = 0x80/0x02, which the old per-lane-index reading does "
            "not explain; the address role is not excluded for the per-lane form, but the "
            "DATA role is proven for the uniform form.")

    append_sem(db, "atomic_mem", "RESERVED FIELDS THAT ARE NOT RESERVED",
        "RESERVED FIELDS THAT ARE NOT RESERVED (EXP-0141, HW, dense 0..255 each): `rsv10` "
        "accepts 4 of 256 values and `rsv11` exactly 1 of 256 -- they are LIVE, heavily "
        "constrained bytes, not reserved padding. (By contrast device_load/device_store "
        "reserved7 and reserved13 ARE genuinely inert, 256/256 each.)")
    append_sem(db, "atomic_tg", "RESERVED FIELDS THAT ARE NOT RESERVED",
        "RESERVED FIELDS THAT ARE NOT RESERVED (EXP-0141, HW, dense 0..255 each): `rsv4` "
        "accepts 4 of 256 values, `rsv6` 2 of 256 and `rsv9` exactly 1 of 256 -- LIVE, "
        "heavily constrained bytes, not reserved padding.")

    # ---------------------------------------------------------------------
    # EXP-0144 -- pack / convert
    # ---------------------------------------------------------------------
    rename(db, val, "pack_convert", "src", "dst",
           "OPERAND-ROLE CORRECTION (EXP-0144, HW): byte+3 is the DESTINATION register "
           "(reg<<1, bit0 don't-care) -- sweeping it redirects the result into 6 distinct "
           "observed registers, an identical map to cvt_i2f/cvt_f2i `dst`. Same bits, same "
           "sweep; the NAME was wrong.")
    split(db, val, "pack_convert", "fmt_word", [
        ("src_lane0", 40, 8, "reg", None,
         "byte+5: 256 of 256 values (dense 0..255)"),
        ("src_lane1", 48, 8, "reg", None,
         "byte+6: 256 of 256 values (dense 0..255)"),
        ("b7", 56, 8, "mod", None,
         "byte+7: 256 of 256 values (dense 0..255), rule (v & 0xfb) == 0x50"),
        ("cvt_enable", 64, 8, "mod", None,
         "byte+8: 256 of 256 values (dense 0..255)"),
        ("fmt_sel", 72, 8, "enum",
         {"64": "snorm2x16 (0x4x)", "128": "unorm2x16 (0x8x)", "192": "unorm 8-bit lanes (0xcx)"},
         "byte+9: 256 of 256 values (dense 0..255)"),
    ], "FIELD-MODEL CORRECTION (EXP-0144, HW): the former 40-bit raw `fmt_word` is five "
       "located bytes -- byte+5 = lane-0 SOURCE register (reg<<2, bits 0-1 don't-care); "
       "byte+6 = lane-1 SOURCE register (reg<<3, bits 1-2 don't-care, bit0 = 0); byte+7 rule "
       "(v & 0xfb) == 0x50, recovered by the rv01 revalidation where run03 lost it to two "
       "genuine hangs; byte+8 = conversion enable (bits 2 and 6 both set); byte+9 = FORMAT "
       "selector (bits 2-3 don't-care). Without this split an emitter following db.json "
       "cannot choose the pack format or either source register.")
    append_sem(db, "pack_convert", "EMITTER SUMMARY",
        "EMITTER SUMMARY (EXP-0144, HW): destination = byte+3, sources = byte+5 / byte+6, "
        "format = byte+9. The old `src` name at byte+3 would have made an emitter write the "
        "result to the wrong register.")

    split(db, val, "unpack_convert", "convert_desc", [
        ("dst", 24, 8, "reg", None, "byte+3: 256 of 256 values (dense 0..255)"),
        ("inert4", 32, 8, "mod", None,
         "byte+4: 256 of 256 values (dense 0..255) -- COMPLETELY INERT"),
        ("src", 40, 8, "reg", None, "byte+5: 256 of 256 values (dense 0..255)"),
        ("opdesc", 48, 8, "mod", None, "byte+6: 256 of 256 values (dense 0..255)"),
    ], "FIELD-MODEL CORRECTION (EXP-0144, HW): the former 32-bit raw `convert_desc` is four "
       "located bytes -- byte+3 = DESTINATION register (3 distinct registers observed); "
       "byte+4 COMPLETELY INERT over all 256 values; byte+5 = SOURCE register (reg<<3, bits "
       "0-2 don't-care); byte+6 = opcode/descriptor (bits 0,2 == 0,1 exactly). Neither "
       "operand register was reachable from db.json before this split.")
    rename(db, val, "unpack_convert", "reg_sel", "fmt_sel",
           "ROLE CORRECTION (EXP-0144, HW): byte+7's high nibble is a FORMAT selector, not a "
           "register and not the result destination. bits 6:5 select the format -- 0x0a/0x8a "
           "unorm8, 0x2a/0xaa snorm16, 0x4a/0xca unorm16, 0x6a/0xea unorm8 -- and bit7 is "
           "don't-care. The old inference also mis-explained our own compiler's "
           "unorm(...1cca) vs snorm(...1caa) pair.")
    retype(db, "unpack_convert", "fmt_sel", "enum",
           {"0": "unorm8 (0x0a)", "2": "snorm16 (0x2a)", "4": "unorm16 (0x4a)",
            "6": "unorm8 (0x6a)", "8": "unorm8 (0x8a)", "10": "snorm16 (0xaa)",
            "12": "unorm16 (0xca)", "14": "unorm8 (0xea)"})
    append_sem(db, "unpack_convert", "BYTE+7 BIT3",
        "BYTE+7 BIT3 (EXP-0144, HW): bit3 of byte+7 -- the top bit of the `size` field -- "
        "changes which SOURCE register is read; it is not part of the format selector.")

    # ---------------------------------------------------------------------
    # EXP-0146 -- integer misc
    # ---------------------------------------------------------------------
    if fidx(ins(db, "carry_gen"), "subop") < 0:
        skipped.append("(b) carry_gen :: operand-slot rename block")
    else:
     rename(db, val, "carry_gen", "srcA", "srcB",
           "OPERAND-SLOT RENAME (EXP-0146, HW): carry_gen is a TWO-operand compare, "
           "p[dst] = (r[byte+1] <u r[byte+3]); byte+3 is the SECOND source, not the only one.")
     rename(db, val, "carry_gen", "subop", "srcA",
           "OPERAND-ROLE CORRECTION (EXP-0146, HW, dense 0..255): byte+1 is the FIRST "
           "source-operand descriptor, not a sub-opcode or a marker. Exactly {0x01, 0x81} "
           "work -- the project-standard (reg<<1)|is32 packing with an INERT bit7 -- and "
           "every other value changes the carry. Identical in shape to byte+3.")
    retype(db, "carry_gen", "srcA", "reg")
    append_sem(db, "carry_gen", "TWO-OPERAND COMPARE",
        "TWO-OPERAND COMPARE (EXP-0146, HW): this is `p[dst] = (r[srcA] <u r[srcB])`, not a "
        "one-operand marker plus a source. MATCH OVER-CONSTRAINED (EXP-0146, HW, dense "
        "0..255): db.json pins byte+2 to the full byte 0x35, but the hardware only requires "
        "(v & 0xCD) == 0x05 -- bits 1, 4 and 5 are DON'T-CARE and 8 of 256 values work "
        "{0x05,0x07,0x15,0x17,0x25,0x27,0x35,0x37}. The pre-registered falsifier byte+2 = "
        "0x00 FIRED (contained command-buffer fault), reproducing EXP-0038's A18 "
        "neutralisation result on M4 by a second method. Relaxing the match is a DECODE "
        "change and is deferred to a corpus A/B.")

    append_sem(db, "iadd2", "NATIVE 64-BIT ADD EXISTS",
        "NATIVE 64-BIT ADD EXISTS (EXP-0146, HW-VALIDATED): the claim that '64-bit SUB uses "
        "the single native 0x1f op' while 64-bit ADD needs the "
        "iadd2 -> carry_gen -> psel -> high-add chain is only a statement about what the "
        "Apple compiler emits. Flipping ONLY the addsub bit of the 64-bit subtract "
        "(byte0 0x1f -> 0x9f) yields an EXACT single-instruction 64-bit ADD, verified on two "
        "independent 8-row boundary input sets (including 2^64-1 + 1 = 0 and 2^63 + 2^63 = "
        "0), in both gated runs and 5/5 repetitions. A native 64-bit register-pair ADD "
        "exists and is emittable.")

    # (b) ilogic.lut_a is a 2-bit selector inside an 8-bit byte.
    split(db, val, "ilogic", "lut_a", [
        ("lut_a_sel", 32, 2, "mod", None,
         "byte+4 bits 0-1, the only selecting bits (EXP-0146, dense 0..255 on the byte)"),
        ("lut_a_free", 34, 3, "mod", None,
         "byte+4 bits 2-4, DON'T-CARE (free mask 0x1c; EXP-0146, dense 0..255 on the byte)"),
        ("lut_a_z", 37, 3, "mod", None,
         "byte+4 bits 5-7, must be clear (EXP-0146, dense 0..255 on the byte)"),
    ], "FIELD-MODEL CORRECTION (EXP-0146, HW, dense 0..255): `lut_a` is a 2-bit LUT selector "
       "inside an 8-bit byte -- only bits 0-1 select, bits 2-4 are don't-care and bits 5-7 "
       "must be clear (rule (v & 0xE3) == 0x00 for the carrier's AND, 8 of 256 values ok). "
       "The label is NOT promoted by this split; it still rests on EXP-0013's "
       "corpus correlation, with EXP-0146 supplying the boundary.")
    for ch in ("lut_a_sel", "lut_a_free", "lut_a_z"):
        e = val["instructions"]["ilogic"][ch]
        if "EXP-0146" not in e["evidence"]:
            e["evidence"] = list(e["evidence"]) + ["EXP-0146"]
    append_sem(db, "ilogic", "ALL 16 TWO-INPUT BOOLEAN FUNCTIONS",
        "ALL 16 TWO-INPUT BOOLEAN FUNCTIONS (EXP-0146, HW-VALIDATED): EXP-0102 INT-12's "
        "'10 of the 16' was a statement about what MSL SOURCE reaches, not about the "
        "encoding. The selector triple (op_base, lut_a & 3, lut_b & 0x0f) produces ALL 16 "
        "two-input boolean functions from this instruction alone, collision-free -- one "
        "HW-validated encoding per function is tabulated in "
        "experiments/EXP-0146-m4-emit-int-misc/analysis/ilogic_lut_table.md. `lut_b`'s "
        "1-D live bits are 0,1,2 and 4 ((v & 0x17) == 0 for AND, free mask 0xe8), but bit3 "
        "IS function-selecting jointly with lut_a (it turns AND into a_and_not_b on the xor "
        "base) -- use the joint table, not the 1-D mask.")

    append_sem(db, "mov_zext16", "SOURCE REGISTER INERT IN THE ONLY CARRIER",
        "SOURCE REGISTER INERT IN THE ONLY CARRIER -- UNRESOLVED (EXP-0146, HW): all 128 "
        "values of byte+1 bits0-6 and BOTH values of bit7 reproduce the exact zero-extend in "
        "the k_zext16 carrier, while the same instruction's `subform` byte faults on 26 "
        "values and silently zeros on 39 -- so the instruction is live and the field is "
        "inert. Either byte+1 is not a source-register selector, or the operand is "
        "ALU-forwarded from the immediately preceding device_load, making it a don't-care in "
        "this INSTANCE. A second carrier whose zext source is several instructions away was "
        "attempted (run05/P3) but that MSL compiled to iadd2/funary and emitted no "
        "mov_zext16, so the question is OPEN. CONTRAST: shift_amt_move's byte+1, modelled "
        "the same way, IS load-bearing (exactly 1 of 128 values works).")
    append_sem(db, "n3_mov", "SOURCE REGISTER INERT IN THE ONLY CARRIER",
        "SOURCE REGISTER INERT IN THE ONLY CARRIER -- UNRESOLVED (EXP-0146, HW): all 128 "
        "values of `srcA_reg`, both values of `srcA_uni` and all 16 values of `dst` "
        "reproduce the result in the k_u64eq carrier, while `subform` faults on 32 values. "
        "Same open question as mov_zext16: a carrier whose n3_mov result is observable at "
        "register granularity is needed.")
    append_sem(db, "sfu_marker", "NOT BYTE-INVARIANT",
        "NOT BYTE-INVARIANT (EXP-0146, HW-VALIDATED, 512 cases over two gated runs): the "
        "'byte-INVARIANT 2-byte token with no operand bits' claim above is REFUTED. Both "
        "bytes are load-bearing. byte+0: only (v & 0xF7) == 0x06 works (2 of 256); 62 values "
        "return a WRONG value and 192 silently zero. byte+1: only (v & 0x13) == 0x02 works "
        "(32 of 256). Setting byte+0 to 0x00 FLIPS THE SIGN of fast::sin on exactly the rows "
        "whose argument requires range reduction (|x| > pi/2), leaving the small-argument "
        "rows correct -- so this is a 2-byte CONTROL WORD with 6 don't-care bits and at "
        "least one live quadrant/sign control bit. It should carry fields; giving it any "
        "requires RELAXING the match (which currently pins both bytes whole), so that is a "
        "DECODE change and is deferred to a corpus A/B.")

    # ---------------------------------------------------------------------
    # EXP-0147 -- pipeline misc
    # ---------------------------------------------------------------------
    split(db, val, "matrix_mac", "dst_desc", [
        ("dst_desc_lo", 72, 6, "mod", None,
         "byte+9 bits 0-5, DON'T-CARE (within the dense 256-value x2-run sweep of the byte)"),
        ("dst_en", 78, 2, "enum",
         {"0": "silent zero (bit6 clear)", "1": "correct result (bit6 set, bit7 clear)",
          "2": "silent zero", "3": "wrong value (bit7 set)"},
         "byte+9 bits 6-7 (within the dense 256-value x2-run sweep of the byte)"),
    ], "FIELD-MODEL CORRECTION (EXP-0147, HW, dense 256 x2 runs): the hardware rule is "
       "simple -- correct A*B+C iff bit6 == 1 and bit7 == 0 (0x40..0x7f, 64/64 values); "
       "bits 0-5 are don't-care; 0x00-0x3f and 0x80-0xbf give a SILENT ZERO and 0xc0-0xff a "
       "wrong value. The field was typed `raw` with no semantics.")
    split(db, val, "matrix_mac", "b11hi", [
        ("c_neg_half", 89, 1, "mod", None,
         "byte+11 bit1 (within the dense 128-value x2-run sweep of the field)"),
        ("c_neg_all", 90, 1, "mod", None,
         "byte+11 bit2 (within the dense 128-value x2-run sweep of the field)"),
        ("b11_rsv", 91, 5, "mod", None,
         "byte+11 bits 3-7, DON'T-CARE (within the dense 128-value x2-run sweep of the field)"),
    ], "FIELD-MODEL CORRECTION (EXP-0147, HW, dense 128 x2 runs): two of the seven bits are "
       "SEMANTIC accumulator-sign controls, not padding -- bit0 of the old field (byte+11 "
       "bit1) makes rows 0-3 use -C, bit1 (byte+11 bit2) makes ALL rows use -C, and both set "
       "cancel back to +C. Correct a*b+c requires both clear (32 of 128 values). The matrix "
       "unit therefore computes A*B - C, a mode Metal's simdgroup_multiply_accumulate never "
       "emits.")
    for m in ("tile_read", "tile_read_mrt"):
        split(db, val, m, "b6", [
            ("read_en", 48, 1, "enum",
             {"1": "read enabled (odd values)", "0": "SILENT ZERO (even values)"},
             "byte+6 bit0 (within the dense 256-value x2-run sweep of the byte)"),
            ("b6_hi", 49, 7, "mod", None,
             "byte+6 bits 1-7, DON'T-CARE (within the dense 256-value x2-run sweep of the byte)"),
        ], "FIELD-MODEL CORRECTION (EXP-0147, HW, dense 256 x2 runs): byte+6 bit0 is a "
           "READ-ENABLE -- all 128 ODD values give the correct read and all 128 EVEN values "
           "give a SILENT ZERO (the pixel collapses to the no-read oracle); bits 1-7 are "
           "don't-care. Identical on tile_read and tile_read_mrt. The field was typed `raw` "
           "with no semantics; in a BG/EOT program a wrong value surfaces as a BLACK TILE, "
           "not a loud failure.")
    add_enum(db, "scoreboard_fence", "kind",
             {"66": "device+texture fence (0x42; own-MSL k_atomic, role not established)"})
    append_sem(db, "scoreboard_fence", "ENUM INCOMPLETE",
        "ENUM INCOMPLETE (EXP-0147): our own MSL "
        "(experiments/EXP-0147-m4-emit-pipeline-misc/kernels/pipe_compute.metal :: k_atomic, "
        "a device atomic RMW plus a device+texture fence) compiles to `07 42 02 00`, i.e. "
        "kind = 0x42, which the enum above did not list. Added; its role is not established "
        "here. NOTE on the DETECTION POWER of EXP-0147's scoreboard_fence sweep: neutering "
        "the neighbouring threadgroup_barrier breaks the program outright, which proves "
        "GENERAL sensitivity but NOT ordering-specific sensitivity, so those field labels "
        "are not raised on that evidence.")

    # ---------------------------------------------------------------------
    # EXP-0148 -- scaffolding & lengths
    # ---------------------------------------------------------------------
    append_sem(db, "op04_len8", "OVER-CONSUMES, DISCRIMINATOR NOT FOUND",
        "OVER-CONSUMES, DISCRIMINATOR NOT FOUND (EXP-0148, corpus): over-consumption is "
        "directly demonstrated -- `04 00 d9 a1 2c 83 80 00 | c9 a1 2c a1 80 00` is a 2-byte "
        "word plus TWO clean 6-byte falu2i, and `04 00 e1 19 1c 81 06 02` is a 2-byte word "
        "plus a clean 6-byte cvt_f2h. But six candidate rules (flat 2, flat 4, and four "
        "byte+1-conditional forms) ALL measured worse than leaving the length at 8, so "
        "byte+1 is not the discriminator. Length stays 8 and emit_unsafe stays set; "
        "resolving it needs a splice, not more corpus fitting.")
    append_sem(db, "cubearray_coord_const", "UNREACHABLE UNDER THE COMMITTED DB",
        "UNREACHABLE UNDER THE COMMITTED DB (EXP-0148, corpus): 0 firings in 1080 files in "
        "both the strict and the resync walk. In k_tex_array_cube.hex -- the kernel it is "
        "named after -- its `f0 c0 04` signature sits at byte offset 48, INTERIOR to the "
        "12-byte tex_addr_setup token spanning 40..52, so it cannot fire. Its length "
        "provenance is an EXP-M4-01 lenprobe resync anchor, not hardware. Its only exercise "
        "is the literal 4-byte string in roundtrip_test.py, and that resolution is FRAGILE: "
        "it depends on the `_r9_succ_safe` lookahead guard seeing the FOLLOWING bytes fail "
        "to decode, so two unrelated op04 length experiments silently broke it. Flagged; NOT "
        "deleted without a texture-stage splice.")
    for m in ("operand_word_x2_h5", "operand_word_x2_h6", "operand_word_x2_h7"):
        append_sem(db, m, "MATCH-LANGUAGE ARTIFACT",
            "MATCH-LANGUAGE ARTIFACT, BUT LOAD-BEARING (EXP-0148): this descriptor exists "
            "only because b_alu14_prep2's match cannot express its own documented invariant "
            "byte+1 == (dst<<1)|1 -- the match language is a list of (start, width, value) "
            "triples with no cross-field predicate, so the complement was encoded as three "
            "separate out-specifying descriptors on byte+1 bits 5/6/7. Deleting them without "
            "first extending the match language would let genuine data words decode as "
            "b_alu14_prep2. Collapsing all three into `operand_word` is therefore blocked on "
            "a match-language change, not on evidence.")

    # ---------------------------------------------------------------------
    # METRIC DEFECT (dispatch Task 2) -- mark the DATA WORDS machine-readably.
    # These six descriptors already say, in their own committed semantics, "NOT A
    # STANDALONE HARDWARE OPCODE": they exist so the tokenizer can account for
    # data bytes that sit between instructions.  An emitter never emits a pad
    # word; it emits an instruction whose encoding happens to include those
    # bytes.  Counting them in the emittability DENOMINATOR is a metric defect
    # (EXP-0148 analysis/scaffolding_classification.md section 3, recommendation
    # c1-c2).  The key is DERIVED from the committed phrase, not hand-listed,
    # and validate_labels.py hard-checks that the two never drift apart.
    PHRASE = "NOT A STANDALONE HARDWARE OPCODE"
    for i in db["instructions"]:
        if PHRASE in i["semantics"]:
            if i.get("emitter_role") == "data-word":
                skipped.append("(b) %s :: emitter_role" % i["mnemonic"])
            else:
                i["emitter_role"] = "data-word"
                applied.append("(b) %s :: emitter_role = data-word" % i["mnemonic"])
        elif i.get("emitter_role") == "data-word":
            del i["emitter_role"]
            applied.append("(b) %s :: emitter_role REMOVED (phrase gone)" % i["mnemonic"])

    # ---------------------------------------------------------------------
    recompute_coverage(db, val)

    if dry:
        print("DRY RUN -- nothing written")
    else:
        # preserve the committed formatting exactly: db.json indent=2,
        # validation.json indent=1, neither with a trailing newline.
        open(DBP, "w").write(json.dumps(db, indent=2))
        val["db_sha256"] = hashlib.sha256(open(DBP, "rb").read()).hexdigest()
        open(VALP, "w").write(json.dumps(val, indent=1))
    print("APPLIED %d:" % len(applied))
    for a in applied:
        print("   ", a)
    if skipped:
        print("SKIPPED (already present) %d:" % len(skipped))
        for s in skipped:
            print("   ", s)


if __name__ == "__main__":
    main()
