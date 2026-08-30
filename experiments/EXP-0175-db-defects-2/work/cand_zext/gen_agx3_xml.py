#!/usr/bin/env python3
# gen_agx3_xml.py -- render our clean-room A18 Pro (G17P) AGX instruction DB
# (tools/agx-isa/db.json, 75 descriptors) into Mesa's ISA-XML schema, producing
# docs/isa/agx3.xml.
#
# WHY: Mesa's src/asahi/isa/ keeps its G13/G14 (Apple7/8) machine ISA as a GenXML
# data file (AGX2.xml) that its build turns into a disassembler. This script emits
# the *same shape of data file* for G17P (Apple9) so the Mesa team can drop
# docs/isa/agx3.xml into src/asahi/isa/ and generate a G17P disassembler. It is a
# DATA/DOCUMENTATION generator -- we are not writing driver code.
#
# CLEAN-ROOM: every encoding fact rendered here comes from db.json, which was
# populated only from the compiled form of MSL *we wrote* (own-shader byte-diffing
# + on-hardware splice validation). No Apple binary was disassembled. This script
# only re-shapes our own data; it reads nothing from Apple's stack. See CLAUDE.md.
#
# ------------------------------------------------------------------------------
# SCHEMA MAPPING (db.json descriptor  ->  Mesa ISA-XML), modelled on AGX2.xml
# ------------------------------------------------------------------------------
# Bit numbering is IDENTICAL in both: an N-byte instruction is one little-endian
# integer, bit 0 = bit 0 of byte 0, so "byte +k bit b" = bit (8*k + b). AGX2.xml
# writes bit *ranges* inclusive, low:high (e.g. bit="16:23" = byte +2). Our DB
# stores (start, width); we emit bit="start : start+width-1".
#
# <exact>/attr value strings follow AGX2.xml's convention exactly: the string is
# the little-endian VALUE of the listed bits as a binary number, MSB (leftmost
# char) = highest listed bit, LSB (rightmost char) = lowest listed bit. Verified
# against AGX2.xml's own `mfsr` (bit="0:6 15">01110010 == byte0 0x72) and `stop`
# (bit="0:15">...1000 == 0x0088). For a contiguous range that means the field's
# LE integer value V renders as format(V, '0{width}b') -- which is exactly the
# integer our DB already stores for match values and enum keys.
#
#   our match (start,width,value)   -> <exact bit="s:e">bin(value)</exact>
#   field type "reg"  (dst/dest*)   -> <dest name= bit=>          (no kind: we
#   field type "reg"  (other)       -> <src  name= bit=>           render the whole
#                                       operand byte; the (reg<<1)|size sub-packing
#                                       is documented in docs/isa/encoding-tables.md)
#   field type "imm"                -> <immediate name= bit= [kind="signed"]>
#   field type "enum"               -> <modifier name= bit= kind="<enum>">
#   field type "mod"  (+enum)       -> <modifier name= bit= kind="<enum>">
#   field type "mod"  (no enum)     -> <modifier name= bit=>
#   field type "opcode" 1 value     -> folded into <exact> (constant opcode)
#   field type "opcode" >=2 values  -> a <group> discriminator (see below)
#   field type "raw"                -> <!-- inferred / not yet bit-decoded --> + <zero>
#
# GROUP vs INS: a descriptor whose single opcode-typed field carries >=2 named ops
# is a shared-encoding family -> emitted as <group> with that field as the
# <exact bit=...>FIELD</exact> discriminator and one child <ins FIELD="bin"/> per
# op (exactly AGX2.xml's <group name="iadd">/<ins name="iadd" negate="0"> idiom).
# Everything else is a single <ins>. Enum-typed families (imin/imax/umin/umax,
# fmax/fmin, ...) stay a single <ins> with a <modifier kind=<enum>> -- we group
# only on the field our DB itself typed as the opcode.
#
# RESERVED / UNDECODED CONVENTION (matches AGX2.xml's handling of unknowns): our
# "raw" fields are bytes we byte-diff-localized to an instruction but have not yet
# split into individual bit-fields (operand packing, address bytes, residue). We
# render each as a <zero> element carrying the field's exact bit range, preceded by
# an XML comment. As in AGX2.xml, <zero> here flags "reserved / not yet decoded"
# residue for the implementation team to resolve -- it is NOT a hardware assertion
# that those bits are literally zero (an operand/address byte plainly is not). Bits
# in neither <exact> nor a field are left unconstrained (we do not invent them).

import json, os, re, html, xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "db.json")
OUT_PATH = os.path.normpath(os.path.join(HERE, "..", "..", "docs", "isa", "agx3.xml"))

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def bitrange(start, width):
    """Our (start,width) -> AGX2 inclusive 'lo:hi' (or 'lo' for a single bit)."""
    if width == 1:
        return str(start)
    return f"{start}:{start + width - 1}"

def binval(value, width):
    """LE field value -> AGX2 value string (MSB=high bit, len == width)."""
    if value < 0:
        value &= (1 << width) - 1
    return format(value, f"0{width}b")

def xesc(s):
    return html.escape(str(s), quote=True)

def cclean(s):
    """Make text safe to place inside an XML comment: '--' is illegal there."""
    s = re.sub(r"-{2,}", "-", str(s))
    return s.rstrip("-").rstrip()

_ident_re = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")

def sanitize_ident(label):
    """Turn an enum label into a valid, compact identifier token."""
    # drop parenthesised asides, keep the leading meaningful token(s)
    base = re.sub(r"\([^)]*\)", "", str(label))
    base = base.strip()
    tok = re.sub(r"[^0-9A-Za-z]+", "_", base).strip("_")
    return tok

def clip(s, n):
    """Clip to <= n chars at a word boundary, appending an ellipsis if cut."""
    s = str(s).strip()
    if len(s) <= n:
        return s
    cut = s[:n].rsplit(" ", 1)[0].rstrip(" ,;:-")
    return cut + " ..."

def short_sem(sem):
    """First clause of a semantics string, for a compact label/comment."""
    if not sem:
        return ""
    s = sem.split(";")[0].split(".")[0].strip()
    return clip(s, 100)

# ---------------------------------------------------------------------------
# enum registry: dedupe identical value-tables into shared <enum kind> blocks
# ---------------------------------------------------------------------------

# Friendly, stable kind names for well-known signatures (readability + reuse).
FRIENDLY = {}

def enum_sig(enum):
    return tuple(sorted((int(k), str(v)) for k, v in enum.items()))

# recognise the operand-size flag wherever it appears so every size field shares it
_SIZE_SIG = tuple(sorted([(0, "b16"), (1, "b32")]))
_IMMSEL_SIG = tuple(sorted([(0, "reg"), (1, "immediate")]))

ENUM_TITLES = {
    "opsize": "Operand size (packed bit0 of the operand byte)",
    "immsel": "Source-B immediate select",
}

class EnumRegistry:
    def __init__(self):
        self.by_sig = {}      # sig -> kind
        self.order = []       # list of (kind, enum_dict, title)

    def kind_for(self, mnemonic, fieldname, enum):
        sig = enum_sig(enum)
        if sig in self.by_sig:
            return self.by_sig[sig]
        if sig == _SIZE_SIG:
            kind = "opsize"
        elif sig == _IMMSEL_SIG:
            kind = "immsel"
        else:
            kind = f"{mnemonic}_{fieldname}"
        # guard against a name clash on distinct signatures
        base = kind; n = 2
        existing = {k for k, _, _ in self.order}
        while kind in existing:
            kind = f"{base}{n}"; n += 1
        self.by_sig[sig] = kind
        title = ENUM_TITLES.get(kind, f"{mnemonic} {fieldname}")
        self.order.append((kind, enum, title))
        return kind

# ---------------------------------------------------------------------------
# XML emission (hand-rolled so we control comments/indentation like AGX2.xml)
# ---------------------------------------------------------------------------

class Out:
    def __init__(self):
        self.lines = []
    def raw(self, s):
        self.lines.append(s)
    def line(self, indent, s):
        self.lines.append("  " * indent + s)
    def text(self):
        return "\n".join(self.lines) + "\n"

def emit_enum(o, kind, enum, title):
    o.line(1, f'<enum kind="{xesc(kind)}" name="{xesc(title)}">')
    for k in sorted(enum.keys(), key=lambda z: int(z)):
        label = str(enum[k])
        # human label kept verbatim in a `label=` attr; the element text is a
        # sanitized token (identifier) so it reads like AGX2.xml's value names.
        tok = sanitize_ident(label) or f"v{k}"
        if tok != label:
            o.line(2, f'<value value="{int(k)}" label="{xesc(label)}">{xesc(tok)}</value>')
        else:
            o.line(2, f'<value value="{int(k)}">{xesc(tok)}</value>')
    o.line(1, "</enum>")

def field_is_dest(f):
    n = f["name"].lower()
    return "dst" in n or "dest" in n

def field_bits(f):
    return set(range(f["start"], f["start"] + f["width"]))

def n_values(f):
    return len(f.get("enum", {}))

def runs(bitset):
    """Contiguous ascending runs of a bit set -> list of (lo, hi) inclusive."""
    bs = sorted(bitset)
    out = []
    i = 0
    while i < len(bs):
        j = i
        while j + 1 < len(bs) and bs[j + 1] == bs[j] + 1:
            j += 1
        out.append((bs[i], bs[j]))
        i = j + 1
    return out

def runs_str(rns):
    return " ".join(str(a) if a == b else f"{a}:{b}" for a, b in rns)

def emit_match(o, indent, match, exclude):
    """Emit <exact> for constant identity bits, skipping any bit in `exclude`
    (bits owned by a discriminator/override field). Splits ranges as needed and
    recomputes the sub-value for each surviving run so values stay correct."""
    for (start, width, value) in match:
        keep = set(range(start, start + width)) - exclude
        if not keep:
            continue
        for (a, b) in runs(keep):
            w = b - a + 1
            sub = (int(value) >> (a - start)) & ((1 << w) - 1)
            o.line(indent, f'<exact bit="{a if a == b else f"{a}:{b}"}">{binval(sub, w)}</exact>')

def emit_field(o, indent, mnemonic, f, reg, covered):
    """Emit one field, restricted to the bits NOT already pinned by <exact>
    (`covered`). A field fully covered by match is a constant the match already
    encodes -> we skip it with a note rather than double-encode (or contradict)."""
    t = f["type"]
    name = f["name"]
    fb = field_bits(f)
    rem = fb - covered
    full = bitrange(f["start"], f["width"])

    if not rem:
        o.line(indent, f'<!-- {cclean(name)} [{full}]: constant, pinned by match/opcode -->')
        return

    br = runs_str(runs(rem))          # may be multi-piece if match split it
    trimmed = (rem != fb)

    if t == "reg":
        tag = "dest" if field_is_dest(f) else "src"
        o.line(indent, f'<{tag} name="{xesc(name)}" bit="{br}"/>')
    elif t == "imm":
        signed = ' kind="signed"' if (mnemonic == "jump" and name == "offset") else ""
        o.line(indent, f'<immediate name="{xesc(name)}" bit="{br}"{signed}/>')
    elif t in ("enum", "mod") and "enum" in f and n_values(f) >= 2:
        kind = reg.kind_for(mnemonic, name, f["enum"])
        o.line(indent, f'<modifier name="{xesc(name)}" bit="{br}" kind="{xesc(kind)}"/>')
    elif t in ("enum", "mod"):
        o.line(indent, f'<modifier name="{xesc(name)}" bit="{br}"/>')
    elif t == "opcode":
        enum = f.get("enum", {})
        if n_values(f) >= 2:
            # a multi-op field that is NOT the group discriminator (e.g. ibitcount
            # fn_hi/form): render as a modifier over an enum value table.
            kind = reg.kind_for(mnemonic, name, enum)
            o.line(indent, f'<modifier name="{xesc(name)}" bit="{br}" kind="{xesc(kind)}"/>')
        elif n_values(f) == 1:
            (val,) = list(enum.keys())
            op = list(enum.values())[0]
            o.line(indent, f'<!-- opcode {cclean(name)} = {cclean(op)} -->')
            # the full-byte opcode value is consistent with any match overlap
            o.line(indent, f'<exact bit="{full}">{binval(int(val), f["width"])}</exact>')
        else:
            o.line(indent, f'<!-- opcode-select {cclean(name)} [{br}]: inferred / not yet bit-decoded -->')
            o.line(indent, f'<zero bit="{br}"/>')
    elif t == "raw":
        o.line(indent, f'<!-- {cclean(name)} [{br}]: inferred / not yet bit-decoded -->')
        o.line(indent, f'<zero bit="{br}"/>')
    else:
        raise ValueError(f"unknown field type {t}")

def pick_group_field(d):
    """Return the sole opcode-typed field with >=2 named ops, else None.
    That field becomes the <group> discriminator (AGX2.xml idiom)."""
    ops = [f for f in d.get("fields", []) if f["type"] == "opcode" and n_values(f) >= 2]
    if len(ops) == 1:
        return ops[0]
    return None

def match_bits(match):
    s = set()
    for (start, width, value) in match:
        s |= set(range(start, start + width))
    return s

def override_fields(d, gf):
    """Non-discriminator fields that carry >=2 real values yet are fully pinned by
    match (the DB match over-constrained a byte that actually varies, e.g.
    ray_move.form 128/129). Let the FIELD own those bits: we drop them from the
    <exact> identity and document the full value table via the field's enum."""
    mb = match_bits(d["match"])
    out = []
    for f in d.get("fields", []):
        if f is gf:
            continue
        if "enum" in f and n_values(f) >= 2 and field_bits(f) <= mb:
            out.append(f)
    return out

def emit_instruction(o, d, reg):
    m = d["mnemonic"]
    length = d["length"]
    sem = short_sem(d.get("semantics", ""))
    prov = d.get("provenance", "").split(":")[0].split("(")[0].strip()
    gf = pick_group_field(d)
    ovf = override_fields(d, gf)

    # bits owned by a discriminator/override field come OUT of the <exact> identity
    exclude = set()
    if gf is not None:
        exclude |= field_bits(gf)
    for f in ovf:
        exclude |= field_bits(f)
    covered = match_bits(d["match"]) - exclude      # bits still fixed by <exact>

    o.raw("")
    o.line(1, f'<!-- {cclean(m)}: {cclean(sem)} -->')
    if prov:
        o.line(1, f'<!-- provenance: {cclean(clip(d.get("provenance",""), 150))} -->')

    lab = f' label="{xesc(sem)}"' if sem else ""
    tag = "group" if gf is not None else "ins"
    o.line(1, f'<{tag} name="{xesc(m)}" length="{length}"{lab}>')
    emit_match(o, 2, d["match"], exclude)
    if gf is not None:
        o.line(2, f'<exact bit="{bitrange(gf["start"], gf["width"])}">{xesc(gf["name"])}</exact>')
    for f in d.get("fields", []):
        if f is gf:
            continue
        emit_field(o, 2, m, f, reg, covered)

    if gf is not None:
        o.raw("")
        used = set()
        for k in sorted(gf["enum"].keys(), key=lambda z: int(z)):
            label = str(gf["enum"][k])
            tok = sanitize_ident(label)
            if not _ident_re.match(tok or ""):
                tok = f'{m}_{gf["name"]}{k}'
            cand = tok; n = 2
            while cand in used:
                cand = f"{tok}_{n}"; n += 1
            used.add(cand)
            attr = binval(int(k), gf["width"])
            extra = f' label="{xesc(label)}"' if tok != label else ""
            o.line(2, f'<ins name="{xesc(cand)}" {xesc(gf["name"])}="{attr}"{extra}/>')
    o.line(1, f"</{tag}>")

# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def build():
    db = json.load(open(DB_PATH))
    ins = db["instructions"]
    reg = EnumRegistry()

    # Pre-pass: register every enum referenced by a rendered field, in a stable
    # first-encounter order, so the <enum> blocks are deterministic. Skip the
    # opcode field that will become a <group> discriminator (it is not a modifier).
    for d in ins:
        gf = pick_group_field(d)
        for f in d.get("fields", []):
            if f is gf:
                continue
            # every non-discriminator field with a real (>=2) value table becomes
            # a <modifier kind=...>; register it (single-value opcodes fold to <exact>)
            if "enum" in f and n_values(f) >= 2:
                reg.kind_for(d["mnemonic"], f["name"], f["enum"])

    o = Out()
    o.raw("<!--")
    o.raw("  Apple A18 Pro / G17P AGX shader ISA - Mesa ISA-XML rendering.")
    o.raw("  GENERATED from tools/agx-isa/db.json by tools/agx-isa/gen_agx3_xml.py.")
    o.raw("  Do not hand-edit; regenerate after any DB change.")
    o.raw("")
    o.raw(f"  Source DB: {xesc(db.get('isa',''))}")
    o.raw("  SPDX-License-Identifier: MIT")
    o.raw("")
    o.raw("  CLEAN-ROOM: every encoding below was learned only from the compiled form")
    o.raw("  of MSL we wrote (own-shader byte-diff + on-hardware splice validation).")
    o.raw("  No Apple binary was disassembled. This file re-shapes our own data (db.json)")
    o.raw("  into the same GenXML schema Mesa uses for G13/G14 (src/asahi/isa/AGX2.xml)")
    o.raw("  so the Mesa team can generate a G17P disassembler from it. See CLAUDE.md.")
    o.raw("")
    o.raw("  BIT NUMBERING (identical to AGX2.xml): an N-byte instruction is one")
    o.raw("  little-endian integer; bit 0 = bit 0 of byte 0; byte +k bit b = bit 8*k+b.")
    o.raw("  bit=\"lo:hi\" is inclusive. An <exact>/attr value string is the little-endian")
    o.raw("  value of the listed bits (leftmost char = highest listed bit).")
    o.raw("")
    o.raw("  LENGTH: unlike G13, the first parcel does NOT encode length on G17P; length")
    o.raw("  is a function of byte 0 (group) + a per-group length bit/signature. Each <ins>")
    o.raw("  here is one concrete form with a fixed byte length; the full length rule lives")
    o.raw("  in tools/agx-isa/isadb.py::instr_length and docs/isa/encoding-tables.md.")
    o.raw("")
    o.raw("  RESERVED/UNDECODED: <zero> elements tagged 'inferred / not yet bit-decoded'")
    o.raw("  mark bytes we byte-diff-localized but have not split into bit-fields yet")
    o.raw("  (operand packing, address bytes, residue). As in AGX2.xml they flag work for")
    o.raw("  the impl team; they are NOT a hardware assertion that the bits are literally 0.")
    o.raw("-->")
    o.raw("<isa>")

    # value tables
    o.raw("")
    o.line(1, "<!-- ============================ value tables ============================ -->")
    for kind, enum, title in reg.order:
        o.raw("")
        emit_enum(o, kind, enum, title)

    # instructions / groups
    o.raw("")
    o.line(1, "<!-- ========================= instructions / groups ====================== -->")
    for d in ins:
        emit_instruction(o, d, reg)

    o.raw("")
    o.raw("</isa>")
    return o.text(), reg, ins

def main():
    text, reg, ins = build()
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as fh:
        fh.write(text)

    # validate: well-formed XML
    ET.fromstring(text)

    # report counts
    n_ins = len(re.findall(r"<ins\b", text))
    n_grp = len(re.findall(r"<group\b", text))
    n_enum = len(re.findall(r"<enum\b", text))
    n_zero = len(re.findall(r"<zero\b", text))
    n_group_desc = sum(1 for d in ins if pick_group_field(d) is not None)
    n_single = len(ins) - n_group_desc
    print(f"wrote {OUT_PATH}")
    print(f"  descriptors in db.json : {len(ins)}")
    print(f"  rendered as single <ins>: {n_single}")
    print(f"  rendered as <group>     : {n_group_desc}")
    print(f"  <ins>  total (incl. group children): {n_ins}")
    print(f"  <group> total: {n_grp}")
    print(f"  <enum>  total: {n_enum}")
    print(f"  <zero>  (inferred/undecoded residue placeholders): {n_zero}")
    print("  XML parses OK (xml.etree)")

if __name__ == "__main__":
    main()
