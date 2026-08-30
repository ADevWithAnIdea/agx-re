#!/usr/bin/env python3
"""EXP-0201 FIELD MODELS -- the per-value, host-computed, falsifiable prediction.

One function per target field. Given the field value and the arm's carrier it
returns

    {"predicted_fn": <library member name | "FAULT" | None>,
     "vals":         <8-lane host vector | None>,
     "equiv":        <equivalence-class key the model predicts>,
     "predicted_token": <mnemonic the bytes should still tokenize as | None>}

`equiv` is the model's content for fields whose per-value *vector* is not
predictable: H3 and H6 assert that certain bits of an operand descriptor are
inert, i.e. `f(v) == f(v ^ mask)`. That is a real per-value prediction and it can
be refuted; it is NOT a constant oracle, which is what left `copysign.operands`
at `untested` after a full 256-value M4 sweep.

Every map below is a PRE-REGISTERED PREDICTION taken from `db.json`'s own field
notes, not an assumption. A class whose observed vector matches no library
member refutes the published map -- refuter R1a/R4a/R5a in PRE_REGISTRATION.md.

CLEAN-ROOM: arithmetic over our own MSL's semantics and our own encoding
database. No Apple binary consulted.
"""

# `db.json` falu3.op note (EXP-0160, G17P, dense 256 x 2 seed sets):
# OPERATION by the low 3 bits of byte+2.
OP_LOW3 = {0: "a+b", 1: "a*b", 2: "a*b+a", 3: None,
           4: "-b", 5: "zero", 6: "a*b+c", 7: "FAULT"}
OP_INERT_MASK = 0x20          # "bit 5 is the ONLY inert bit"

# `db.json` falu3_srcmod12.opsel enum.
OPSEL_ENUM = {4: "a+b", 5: "a*b", 6: "a*b+c", 7: None}
SRCMOD12_MATCH_BIT = 17       # [17,1,1] -- INSIDE opsel's own 3-bit span

# `db.json` falu2/falu3 note: ctrl bits 0/1 are the INSTRUCTION-LENGTH selector,
# length = 6 + 2*(byte+4 & 3)   (EXP-M4-10 / EXP-0119).
def ctrl_length(v):
    return 6 + 2 * (v & 3)


def m_falu3_op(value, carrier, baseline_value, lib):
    fn = OP_LOW3[value & 7]
    return {"predicted_fn": fn,
            "vals": None if fn in (None, "FAULT") else lib.get(fn),
            "equiv": value & ~OP_INERT_MASK,
            "predicted_token": None if (value & 7) == 7 else carrier["kind"]}


def m_opsel(value, carrier, baseline_value, lib):
    """opsel is bits 16..18 and the descriptor pins bit 17 -- so only 2 of the
    3 bits are free WITHIN this mnemonic, and a value with bit 17 clear is a
    DIFFERENT instruction (`falu_srcmod12b`), not a different operand."""
    in_mnemonic = bool((value >> 1) & 1)
    fn = OPSEL_ENUM.get(value) if in_mnemonic else None
    return {"predicted_fn": fn,
            "vals": lib.get(fn) if fn else None,
            "equiv": value,
            "predicted_token": "falu3_srcmod12" if in_mnemonic
                               else "falu_srcmod12b"}


def m_ctrl(value, carrier, baseline_value, lib):
    """The low 2 bits re-length the instruction; only a value that preserves the
    modelled 12-byte length can leave the instruction stream framed as compiled."""
    L = ctrl_length(value)
    intact = (L == 12) and (value | 3) == (baseline_value | 3)
    return {"predicted_fn": "a*b+c" if intact else None,
            "vals": lib.get("a*b+c") if intact else None,
            "equiv": value,
            "predicted_token": "falu3_srcmod12" if L == 12 else None,
            "predicted_length": L}


def m_operand(inert_mask, baseline_fn):
    """Operand-descriptor model: `(reg << 1) | size` with `inert_mask` bits
    HW-tested inert on five other families (EXP-0099/0112). The prediction is
    the EQUIVALENCE `f(v) == f(v ^ inert_mask)` plus the accept set."""
    def m(value, carrier, baseline_value, lib):
        accept = (value & ~inert_mask) == (baseline_value & ~inert_mask)
        fn = baseline_fn(carrier) if accept else None
        return {"predicted_fn": fn,
                "vals": lib.get(fn) if fn else None,
                "equiv": value & ~inert_mask,
                "predicted_token": carrier["kind"]}
    return m


def _fsp_base_by_name(carrier):
    f = carrier["func"]
    return {"k_fsp_rsqrt": "rsqrt(a)", "k_fsp_rcp": "rcp(a)",
            "k_fsp_sqrt": "sqrt(a)", "k_fsp_two": "rsqrt(a)"}[f]


def _cs_base_by_name(carrier):
    return {"k_cs_load": "copysign(a,b)", "k_cs_swap": "copysign(b,a)",
            "k_cs_alu": "copysign(a,b)", "k_cs_chain": "copysign(a,b)"}[carrier["func"]]


# instruction.field -> model
MODELS = {
    "falu3.op":              m_falu3_op,
    "falu3_ext.op":          m_falu3_op,
    "falu3_srcmod12.opsel":  m_opsel,
    "falu3_srcmod12.ctrl":   m_ctrl,
    # bit 7 of a source-operand byte is HW-TESTED INERT on five families.
    "fspecial_est.srcA":     m_operand(0x80, _fsp_base_by_name),
    # H6: bits 0 (size) and 7 (inert top bit) -> f(v) == f(v ^ 0x81).
    "copysign.operands":     m_operand(0x81, _cs_base_by_name),
}


def predict(instr, field, value, carrier, baseline_value, lib):
    key = "%s.%s" % (instr, field)
    m = MODELS.get(key)
    if m is None:                       # control / falsifier arms: no prediction
        return {"predicted_fn": None, "vals": None, "equiv": value,
                "predicted_token": None}
    return m(value, carrier, baseline_value, lib)
