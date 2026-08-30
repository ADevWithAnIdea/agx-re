#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""legacy_index.py -- make the pre-EXP-0138 raw era machine-readable.

Built for EXP-0211. `evidence_index.py` reads `.jsonl`/`.json` records keyed by a
string `instr` and a string `field`. The entire early corpus predates that
convention: it is `.log`/`.txt` transcripts, per-case `.json` process captures,
and `.hex` program dumps. 185 of the 226 experiments that have a `raw/` tree
yield ZERO cells to that indexer -- not because the observations are absent, but
because the format cannot express the key. EXP-0197 measured the same thing from
the other end: for 24 of 27 cited experiments the "no per-value records" clause
could not have come out any other way.

This program parses the legacy formats and emits records in EXACTLY the shape
`evidence_index.Indexer.handle()` consumes, plus provenance. It writes a separate
index; it NEVER edits a raw file, a label, `db.json`, `validation.json` or `docs/`.

THE THREE RULES THAT KEEP IT FROM MANUFACTURING EVIDENCE
--------------------------------------------------------
1. **Never synthesize instruction bytes.** A sweep transcript states a baseline
   encoding and a requested byte; the bytes that were actually dispatched are not
   committed. Reconstructing them from (baseline, index, value) would ASSUME the
   splice landed -- which is precisely what Gate A exists to test, and precisely
   how DEF-0166 hid. Only hex that is literally present in the file is ever
   emitted as `bytes`. Consequence: legacy byte sweeps produce liveness and
   outcome evidence, and deliberately produce NO Gate A ledger.
2. **Never guess an attribution.** A record is emitted only when the mnemonic
   comes from tokenizing committed bytes with our own disassembler, and the field
   comes either from a literal field name that exists in `db.json` for that
   mnemonic, or from a byte index that lies inside that instruction. Anything
   else is counted as `unparsed` and reported, never resolved by plausibility.
3. **Dispatch is not compilation.** A program hex with no committed execution
   outcome is compile-only corpus evidence. It goes to a SEPARATE stream that is
   never merged into the dashboards, because the liveness ladder's rung 1 says
   "dispatched" and a compiled-but-not-run program did not dispatch.

PARSERS
-------
  P1  byte-sweep table     `# ... bytes=<hex>` / `# sweeping rel=0xN` header plus
                           `0xVV  OK  <class>  [obs]  raw=<hex>` rows.
                           EXP-0005/0006/0007, RT-1a.
  P2  prose splice         an anchor line binding instruction bytes, then
                           `splice +12 0x46->0x42 -> [obs] [OK]`,
                           `splice b5 0x0a->0x02 out=[..] exp abs=[..] PASS`,
                           `splice offset->0 -> [] [HANG]`,
                           `[a_reg(+5)=b_reg 0x08 (...)] STATUS OK`.
                           EXP-0010/0012/0013/0016/0031, RT-5, RT-10.
  P3  absolute-offset      `# _agc.main len=56 ... op-byte@0x22=orig 0x1c` rows,
      sweep               attributable only when the experiment commits exactly
                           one program of that length whose byte at that offset
                           equals `orig`. EXP-0005.
  P4  dispatched program   a raw record pairing committed program bytes with a
      corpus              committed execution outcome (`main_hex` + `render`,
                           `out_word_hex`, `command_buffer_status`, ...).
                           Emits `bytes` with NO `value`: geometry `bytes-seen`,
                           never a ledger. EXP-0050 and friends.
  C0  compile-only         program bytes with no outcome in the same record.
                           Counted, written to a separate stream, NOT merged.

Usage:
    python3 tools/agx-isa/legacy_index.py --selftest
    python3 tools/agx-isa/legacy_index.py --survey            # format inventory
    python3 tools/agx-isa/legacy_index.py --parse             # emit records
    python3 tools/agx-isa/legacy_index.py --parse EXP-0010    # one slug prefix
    python3 tools/agx-isa/legacy_index.py --merge-cache OUTDIR
"""
import argparse
import collections
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
EXPS = os.path.join(ROOT, "experiments")
OUTDIR = os.path.join(EXPS, "EXP-0211-legacy-index", "index")

sys.path.insert(0, HERE)
import evidence_index as EI        # noqa: E402  (record shape + cell math)
import isadb                       # noqa: E402  (our own clean-room disassembler)

# ------------------------------------------------------------------ vocabulary

# A CLOSED outcome vocabulary. A token not in it makes the line `unparsed`.
# `FAIL` is deliberately absent as a bare token: on its own it does not say
# whether the hardware misbehaved or the measurement did. It is accepted only in
# the `out=/exp=` form of P2, where the observation and the prediction are both
# printed and the disagreement is therefore visible.
OUTCOME = {
    "OK": "ok",
    "PASS": "ok",
    "HANG": "hang",
    "CMDBUF_ERROR": "cmdbuf_error",
    "FAULT": "fault",
    "TIMEOUT": "timeout",
    "ERROR": "error",
}

# `parse_confidence`, strongest first. A consumer may filter on it.
CONF_STRUCTURED = "structured"      # the source is machine-readable JSON
CONF_TABLE = "table"                # a fixed-column table under a stated header
CONF_PROSE = "prose"                # a sentence, anchored to committed bytes

TEXT_EXT = {".txt", ".log", ".out", ".stdout", ".stderr", ".meta", ".trace"}

# Hex that is an instruction stream, not a payload, must be even-length and at
# least 4 bytes (the shortest Apple9 descriptor).
HEXBLOB = r"[0-9a-fA-F]{8,}"


def _hex_ok(h):
    h = h.strip().lower()
    return bool(h) and len(h) % 2 == 0 and re.fullmatch(r"[0-9a-f]+", h)


# --------------------------------------------------------------- attribution


class Attrib(object):
    """Turn committed bytes into (mnemonic, length, fields). Never a guess."""

    def __init__(self, spec=None):
        self.spec = spec or EI.load_db()
        self._memo = {}

    def anchor(self, hexstr):
        """Tokenize committed bytes; return (mnemonic, length) or None.

        Refuses unless our own disassembler produces a clean first instruction
        whose descriptor is in db.json. A blob that does not tokenize, or whose
        first token errors, yields None -- the line is then `unparsed`.
        """
        h = (hexstr or "").strip().lower()
        if not _hex_ok(h):
            return None
        if h in self._memo:
            return self._memo[h]
        out = None
        try:
            recs, _ = isadb.disassemble(bytes.fromhex(h))
        except Exception:
            recs = []
        if recs and not recs[0].get("error"):
            m = recs[0].get("mnemonic")
            if m in self.spec:
                out = (m, recs[0].get("length") or self.spec[m]["length"])
        self._memo[h] = out
        return out

    def tokenize(self, hexstr):
        """Every instruction in a committed program: [(offset, mnem, len, hex)]."""
        h = (hexstr or "").strip().lower()
        if not _hex_ok(h):
            return []
        try:
            recs, rest = isadb.disassemble(bytes.fromhex(h))
        except Exception:
            return []
        out, off = [], 0
        for r in recs:
            if r.get("error"):
                break
            L = r.get("length") or 0
            if L <= 0:
                break
            m = r.get("mnemonic")
            if m in self.spec:
                out.append((off, m, L, r.get("hex") or h[2 * off:2 * (off + L)]))
            off += L
        return out

    def fields_at_byte(self, mnem, byte_index):
        """Fields of <mnem> whose bit span covers byte <byte_index>. May be []."""
        s = self.spec.get(mnem)
        if not s:
            return []
        L = s.get("length") or 0
        if byte_index is None or byte_index < 0 or (L and byte_index >= L):
            return []
        lo, hi = byte_index * 8, byte_index * 8 + 7
        return sorted(f for f, (st, w) in s["fields"].items()
                      if st <= hi and (st + w - 1) >= lo)

    def has_field(self, mnem, field):
        s = self.spec.get(mnem)
        return bool(s and field in s["fields"])


# ------------------------------------------------------------------- emission


class Emitter(object):
    """Collects records and counts every line it refused."""

    def __init__(self):
        self.records = []
        self.compile_only = []
        self.stats = collections.Counter()
        self.unparsed_samples = collections.defaultdict(list)
        self.per_parser = collections.defaultdict(collections.Counter)

    def emit(self, rec, parser, conf, src, line):
        rec = dict(rec)
        rec["parse_confidence"] = conf
        rec["_parser"] = parser
        rec["_src_file"] = src
        rec["_src_line"] = line
        self.records.append(rec)
        self.stats["records"] += 1
        self.per_parser[parser]["records"] += 1
        self.per_parser[parser]["conf_" + conf] += 1

    def emit_compile_only(self, rec, parser, src, line):
        rec = dict(rec)
        rec["_parser"] = parser
        rec["_src_file"] = src
        rec["_src_line"] = line
        rec["parse_confidence"] = CONF_STRUCTURED
        self.compile_only.append(rec)
        self.per_parser[parser]["compile_only"] += 1

    def refuse(self, parser, reason, src, line, text=""):
        self.stats["unparsed"] += 1
        self.per_parser[parser]["unparsed"] += 1
        self.per_parser[parser]["why_" + reason] += 1
        k = "%s/%s" % (parser, reason)
        if len(self.unparsed_samples[k]) < 4:
            self.unparsed_samples[k].append("%s:%d: %s" % (src, line, text[:120]))

    def candidate(self, parser):
        self.stats["candidates"] += 1
        self.per_parser[parser]["candidates"] += 1


# ------------------------------------------------------------------- helpers


def _obs_list(s):
    """Parse a printed observation list into a comparable payload, or None.

    `[15 26 12 108]`, `[1.0, -2.0]`, `['0x11223301', ...]`, `[]`. Anything that
    does not parse into a list of scalars returns None and the record carries no
    `observed` -- it is still a dispatch record, just without a payload.
    """
    if s is None:
        return None
    t = s.strip()
    if t.startswith("[") and t.endswith("]"):
        t = t[1:-1]
    t = t.strip()
    if t == "":
        return []
    parts = [p.strip().strip("'\"") for p in re.split(r"[,\s]+", t) if p.strip()]
    out = []
    for p in parts:
        try:
            if p.lower().startswith("0x"):
                out.append(int(p, 16))
            elif re.fullmatch(r"[-+]?\d+", p):
                out.append(int(p))
            elif re.fullmatch(r"[-+]?(\d+\.\d*|\.\d+|\d+)([eE][-+]?\d+)?", p):
                out.append(float(p))
            elif p.lower() in ("nan", "-nan", "inf", "-inf", "+inf"):
                out.append(p.lower())
            else:
                return None
        except ValueError:
            return None
    return out


def _int_val(tok):
    tok = tok.strip()
    try:
        if tok.lower().startswith("0x"):
            return int(tok, 16)
        return int(tok, 10)
    except ValueError:
        return None


def _run_of(path, expdir):
    return EI._run_of(path, expdir)


# =========================================================== P1: sweep tables

# `# source=kernels/iadd.metal ALU@0x20 len=10 bytes=9f015600020800a81705`
# `# sweep rel=0x0 abs=0x20 baseALU=09011c0500c0`
RX_P1_BYTES = re.compile(r"\b(?:bytes|baseALU|base_alu|basealu)\s*=\s*(" + HEXBLOB + r")")
RX_P1_REL = re.compile(r"\brel\s*=\s*(0x[0-9a-fA-F]+|\d+)")
# `0x00  OK  a+b        [15 26 12 108]  raw=0f00...`
RX_P1_OK = re.compile(
    r"^\s*0x([0-9a-fA-F]{1,2})\s+(OK|PASS)\s+(\S+)\s+\[([^\]]*)\]"
    r"(?:\s+raw=([0-9a-fA-F]+))?\s*$")
# `0x16  FAULT:CMDBUF_ERROR`   /  `0x07  CMDBUF_ERROR  command buffer failed: ...`
RX_P1_HARD = re.compile(
    r"^\s*0x([0-9a-fA-F]{1,2})\s+(?:FAULT:)?(CMDBUF_ERROR|HANG|FAULT|TIMEOUT|ERROR)\b(.*)$")
# EXP-0005 opmap/opsweep: `0x04  OK    fadd              [6 9 10 12]`
RX_P1_OK2 = re.compile(
    r"^\s*0x([0-9a-fA-F]{1,2})\s+(OK)\s+(\S+)\s+\[([^\]]*)\]\s*$")


def parse_P1(lines, src, exp, run, at, em):
    """Byte-sweep tables. Header binds the baseline encoding and the byte index."""
    anchor = rel = None
    anchor_line = 0
    for i, raw in enumerate(lines, 1):
        line = raw.rstrip("\n")
        if line.lstrip().startswith("#"):
            mb = RX_P1_BYTES.search(line)
            mr = RX_P1_REL.search(line)
            if mb:
                anchor, anchor_line = mb.group(1).lower(), i
            if mr:
                rel = _int_val(mr.group(1))
            continue
        m = RX_P1_OK.match(line) or RX_P1_OK2.match(line)
        hard = None if m else RX_P1_HARD.match(line)
        if not m and not hard:
            continue
        em.candidate("P1")
        if anchor is None:
            em.refuse("P1", "no_anchor_bytes_in_header", src, i, line)
            continue
        a = at.anchor(anchor)
        if a is None:
            em.refuse("P1", "anchor_does_not_tokenize", src, i, line)
            continue
        mnem, L = a
        if rel is None:
            em.refuse("P1", "header_states_no_byte_index", src, i, line)
            continue
        if rel >= L or rel * 2 >= len(anchor):
            em.refuse("P1", "byte_index_outside_instruction", src, i, line)
            continue
        flds = at.fields_at_byte(mnem, rel)
        if not flds:
            em.refuse("P1", "no_db_field_covers_that_byte", src, i, line)
            continue
        if m:
            val = int(m.group(1), 16)
            outcome = OUTCOME[m.group(2).upper()]
            klass = m.group(3)
            obs = _obs_list(m.group(4))
            rawhex = (m.group(5) if m.lastindex and m.lastindex >= 5 else None)
        else:
            val = int(hard.group(1), 16)
            outcome = OUTCOME[hard.group(2).upper()]
            klass = hard.group(2)
            obs, rawhex = None, None
        for f in flds:
            rec = {
                "instr": mnem, "field": f, "value": val,
                "byte_index": rel, "outcome": outcome,
                "carrier": "anchor:" + anchor[:16],
                "note": klass,
                "_anchor_bytes": anchor, "_anchor_line": anchor_line,
                "_exp": exp, "_run": run,
            }
            # The output buffer readback is the observation. It is NOT the
            # instruction encoding, and is never placed in `bytes`.
            if obs is not None:
                rec["observed"] = obs
            elif rawhex:
                rec["observed"] = {"out_hex": rawhex.lower()}
            em.emit(rec, "P1", CONF_TABLE, src, i)


# ========================================================== P3: abs-offset sweep

# `# _agc.main len=56 region_off=7344 op-byte@0x22=orig 0x1c`
RX_P3_HDR = re.compile(
    r"_agc\.main\s+len=(\d+).*?(?:op-)?byte@0x([0-9a-fA-F]+)\s*=\s*orig\s+0x([0-9a-fA-F]{1,2})")


def parse_P3(lines, src, exp, run, at, em, programs):
    """A sweep stated as an ABSOLUTE offset into `_agc.main`.

    Attributable only when the experiment commits exactly one program of the
    stated length whose byte at that offset equals the stated original value, and
    that program tokenizes cleanly. Two candidates, zero candidates, or a dirty
    tokenization all make every row of the file `unparsed`.
    """
    hdr = None
    for i, raw in enumerate(lines, 1):
        line = raw.rstrip("\n")
        if line.lstrip().startswith("#"):
            mo = RX_P3_HDR.search(line)
            if mo:
                hdr = (int(mo.group(1)), int(mo.group(2), 16),
                       int(mo.group(3), 16), i)
            continue
        m = RX_P1_OK.match(line) or RX_P1_OK2.match(line)
        hard = None if m else RX_P1_HARD.match(line)
        if not m and not hard:
            continue
        em.candidate("P3")
        if hdr is None:
            em.refuse("P3", "no_abs_offset_header", src, i, line)
            continue
        plen, absoff, orig, hline = hdr
        cands = set()
        for ph in programs:
            if len(ph) // 2 != plen:
                continue
            b = bytes.fromhex(ph)
            if absoff < len(b) and b[absoff] == orig:
                cands.add(ph)
        if len(cands) != 1:
            em.refuse("P3", "program_not_uniquely_identified", src, i, line)
            continue
        prog = cands.pop()
        toks = at.tokenize(prog)
        hit = [t for t in toks if t[0] <= absoff < t[0] + t[2]]
        if len(hit) != 1:
            em.refuse("P3", "offset_not_inside_one_clean_token", src, i, line)
            continue
        off, mnem, L, ihex = hit[0]
        rel = absoff - off
        flds = at.fields_at_byte(mnem, rel)
        if not flds:
            em.refuse("P3", "no_db_field_covers_that_byte", src, i, line)
            continue
        if m:
            val = int(m.group(1), 16)
            outcome = OUTCOME[m.group(2).upper()]
            klass, obs = m.group(3), _obs_list(m.group(4))
        else:
            val = int(hard.group(1), 16)
            outcome = OUTCOME[hard.group(2).upper()]
            klass, obs = hard.group(2), None
        for f in flds:
            rec = {"instr": mnem, "field": f, "value": val, "byte_index": rel,
                   "outcome": outcome, "carrier": "main:" + prog[:16],
                   "note": klass, "_anchor_bytes": ihex, "_anchor_line": hline,
                   "_exp": exp, "_run": run}
            if obs is not None:
                rec["observed"] = obs
            em.emit(rec, "P3", CONF_TABLE, src, i)


# ============================================================ P2: prose splice

# --- anchor lines: bind committed instruction bytes (and, sometimes, their
#     absolute base inside `_agc.main`, so an absolute splice can be made relative)
RX_A_AT_MAIN = re.compile(
    r"\b([A-Za-z_][\w ]{0,24}?)\s+at\s+main\[(\d+)\]\s*=\s*(" + HEXBLOB + r")")
RX_A_RANGE = re.compile(r"\bmain\[(\d+):(\d+)\]\s*=\s*(" + HEXBLOB + r")")
RX_A_TRAIL = re.compile(
    r"\b([A-Za-z_]\w*)\s+(" + HEXBLOB + r")\s+at\s+main\[(\d+)\]")
RX_A_BASEOP = re.compile(r"\bbaseline op bytes\s*:\s*(" + HEXBLOB + r")")
RX_A_ALUEQ = re.compile(r"\bALU\s*=\s*(" + HEXBLOB + r")")
RX_A_ALUIDX = re.compile(
    r"\bALU\[\d+\]\s*@0x([0-9a-fA-F]+)\s+len=\d+\s+(" + HEXBLOB + r")")
# `  +0x20  falu2        [fadd]    09051c0100c0`
RX_A_TOKLINE = re.compile(
    r"^\s*\+0x([0-9a-fA-F]+)\s+([a-z_][\w]*)\s+.*?\b(" + HEXBLOB + r")\b")

# --- splice lines
RX_S_RELPLUS = re.compile(
    r"\bsplice\b[^\n]*?\+(\d+)\s*(?:=\S+)?\s*0x([0-9a-fA-F]{1,2})\s*->\s*0x([0-9a-fA-F]{1,2})")
RX_S_BN = re.compile(
    r"\bsplice\b\s+(?:\w+\s+)?b(\d+)\s+0x([0-9a-fA-F]{1,2})\s*->\s*0x([0-9a-fA-F]{1,2})")
RX_S_MAINEQ = re.compile(
    r"\bsplice\b\s+main\[(\d+)\]\s*=\s*0x([0-9a-fA-F]{1,2})")
# `splice offset->0`, `splice stop payload->ff`. The target is captured as a
# NAME and the value as an opaque token; the name is checked against db.json and
# the token is then required to be an unambiguous integer literal. `ff` with no
# `0x` could be hex or a label, so it is refused rather than assumed.
RX_S_FIELD = re.compile(
    r"\bsplice\b\s+(?:\w+\s+)?([A-Za-z_]\w*)\s*->\s*(\S+)")
RX_INT_LITERAL = re.compile(r"^[-+]?(?:0x[0-9a-fA-F]+|\d+)$")
# RT-5 / RT-10: `[a_reg(+5)=b_reg 0x08  (expect B*B+C ...)] STATUS OK  D=`
RX_S_BRACKET = re.compile(
    r"^\s*\[\s*([A-Za-z_]\w*)\s*\(\+(\d+)\)\s*=\s*\S+\s+0x([0-9a-fA-F]{1,2})[^\]]*\]"
    r"\s*STATUS\s+([A-Z_]+)")

# --- outcome / observation tails
RX_T_ARROW = re.compile(
    r"->\s*(\[[^\]]*\])\s*(?:match=(True|False)\s*)?\[([A-Z_]+)\]")
RX_T_OUTEXP = re.compile(
    r"\bout=(\[[^\]]*\])\s+exp\s*\w*\s*=\s*(\[[^\]]*\])\s*(PASS|FAIL)\b")
RX_T_STATUS = re.compile(r"\bSTATUS\s+([A-Z_]+)\b")


def _anchor_scan(line, at):
    """Every anchor this line establishes: (mnem, length, hex, base_or_None)."""
    out = []
    for mo in RX_A_AT_MAIN.finditer(line):
        a = at.anchor(mo.group(3))
        if a:
            out.append((a[0], a[1], mo.group(3).lower(), int(mo.group(2))))
    for mo in RX_A_RANGE.finditer(line):
        a = at.anchor(mo.group(3))
        if a:
            out.append((a[0], a[1], mo.group(3).lower(), int(mo.group(1))))
    for mo in RX_A_TRAIL.finditer(line):
        a = at.anchor(mo.group(2))
        if a:
            out.append((a[0], a[1], mo.group(2).lower(), int(mo.group(3))))
    for rx in (RX_A_BASEOP, RX_A_ALUEQ):
        for mo in rx.finditer(line):
            a = at.anchor(mo.group(1))
            if a:
                out.append((a[0], a[1], mo.group(1).lower(), None))
    for mo in RX_A_ALUIDX.finditer(line):
        a = at.anchor(mo.group(2))
        if a:
            out.append((a[0], a[1], mo.group(2).lower(), int(mo.group(1), 16)))
    mo = RX_A_TOKLINE.match(line)
    if mo:
        a = at.anchor(mo.group(3))
        if a and a[0] == mo.group(2):
            out.append((a[0], a[1], mo.group(3).lower(), int(mo.group(1), 16)))
    # de-duplicate, preserving order
    seen, uniq = set(), []
    for t in out:
        if t[2] not in seen:
            seen.add(t[2])
            uniq.append(t)
    return uniq


# A whole committed PROGRAM, which resolves an absolute `main[N]` index to the
# instruction that actually contains that byte. EXP-0010/EXP-0012 print one per
# section.
RX_A_PROGRAM = re.compile(r"^\s*main:\s*(" + HEXBLOB + r")\s*$")
# `splice main[9]=0x00 ...` and the bare sweep form `main[4]=0x02 -> [...] [OK]`.
RX_S_MAINIDX = re.compile(r"\bmain\[(\d+)\]\s*=\s*0x([0-9a-fA-F]{1,2})")

SECTION_RX = re.compile(r"^\s*(={5,}|-{5,}|#{3,})\s*$")
ANCHOR_WINDOW = 12          # lines; an anchor older than this is out of scope


def parse_P2(lines, src, exp, run, at, em):
    """Prose splice transcripts, anchored to committed instruction bytes.

    Scope rules, which are the whole safety story:
      * an anchor is live only inside its own section (banner-delimited) and only
        for the next ANCHOR_WINDOW lines;
      * if two DIFFERENT anchored mnemonics are live, the line is refused as
        ambiguous rather than resolved by proximity;
      * a byte index must land inside the anchored instruction;
      * a named field must exist in db.json for the anchored mnemonic.
    """
    live = []          # [(mnem, L, hex, base, line_no)]  -- instruction anchors
    prog = []          # [(program_hex, line_no)]           -- whole-program anchors
    for i, raw in enumerate(lines, 1):
        line = raw.rstrip("\n")
        if SECTION_RX.match(line):
            live, prog = [], []
            continue
        mo = RX_A_PROGRAM.match(line)
        if mo and at.tokenize(mo.group(1)):
            prog.append((mo.group(1).lower(), i))
        for a in _anchor_scan(line, at):
            live.append(a + (i,))
        live = [a for a in live if i - a[4] <= ANCHOR_WINDOW]

        # An absolute `main[N]=0xVV` is resolved against the section's committed
        # program, not against an instruction anchor: the index is into the
        # program, and only tokenizing it says which instruction owns that byte.
        mo = RX_S_MAINIDX.search(line)
        if mo and RX_T_ARROW.search(line):
            em.candidate("P2")
            if len(prog) != 1:
                em.refuse("P2", "no_unique_program_anchor" if not prog
                          else "ambiguous_program_anchor", src, i, line)
                continue
            phex, pline = prog[0]
            absidx, val = int(mo.group(1)), int(mo.group(2), 16)
            toks = at.tokenize(phex)
            hit = [t for t in toks if t[0] <= absidx < t[0] + t[2]]
            if len(hit) != 1:
                em.refuse("P2", "main_index_not_inside_one_clean_token",
                          src, i, line)
                continue
            off, mnem, L, ihex = hit[0]
            rel = absidx - off
            flds = at.fields_at_byte(mnem, rel)
            if not flds:
                em.refuse("P2", "no_db_field_covers_that_byte", src, i, line)
                continue
            t = RX_T_ARROW.search(line)
            outc = OUTCOME.get(t.group(3).upper())
            if outc is None:
                em.refuse("P2", "no_outcome_token", src, i, line)
                continue
            obs = _obs_list(t.group(1))
            for f in flds:
                rec = {"instr": mnem, "field": f, "value": val,
                       "byte_index": rel, "outcome": outc,
                       "carrier": "prog:" + phex[:16],
                       "_anchor_bytes": ihex, "_anchor_line": pline,
                       "_exp": exp, "_run": run}
                if obs is not None:
                    rec["observed"] = obs
                em.emit(rec, "P2", CONF_PROSE, src, i)
            continue

        got = (RX_S_RELPLUS.search(line) or RX_S_BN.search(line) or
               RX_S_MAINEQ.search(line) or RX_S_BRACKET.match(line) or
               RX_S_FIELD.search(line))
        if not got and "splice" not in line.lower():
            continue
        if not got:
            # the word `splice` in a shape this parser does not model: e.g.
            # `splice cp[0] 0x03->0x00` (the constant program, not an
            # instruction) or `splice cp[0:4]->0e000000`. Refused, not resolved.
            em.candidate("P2")
            em.refuse("P2", "splice_line_shape_not_modelled", src, i, line)
            continue
        em.candidate("P2")
        if not live:
            em.refuse("P2", "no_live_anchor", src, i, line)
            continue
        mnems = {a[0] for a in live}
        if len(mnems) > 1:
            em.refuse("P2", "ambiguous_anchor", src, i, line)
            continue
        mnem, L, ahex, base, aline = live[-1]

        field = byte_index = value = None
        mo = RX_S_BRACKET.match(line)
        if mo:
            field, byte_index = mo.group(1), int(mo.group(2))
            value = int(mo.group(3), 16)
        elif RX_S_RELPLUS.search(line):
            mo = RX_S_RELPLUS.search(line)
            byte_index, value = int(mo.group(1)), int(mo.group(3), 16)
        elif RX_S_BN.search(line):
            mo = RX_S_BN.search(line)
            byte_index, value = int(mo.group(1)), int(mo.group(3), 16)
        elif RX_S_MAINEQ.search(line):
            mo = RX_S_MAINEQ.search(line)
            if base is None:
                em.refuse("P2", "absolute_splice_without_anchor_base", src, i, line)
                continue
            byte_index, value = int(mo.group(1)) - base, int(mo.group(2), 16)
        else:
            mo = RX_S_FIELD.search(line)
            field, vtok = mo.group(1), mo.group(2)
            if not at.has_field(mnem, field):
                em.refuse("P2", "named_target_is_not_a_db_field", src, i, line)
                continue
            if not RX_INT_LITERAL.match(vtok):
                em.refuse("P2", "ambiguous_value_literal", src, i, line)
                continue
            value = _int_val(vtok)

        if field is not None and not at.has_field(mnem, field):
            em.refuse("P2", "named_target_is_not_a_db_field", src, i, line)
            continue
        if byte_index is not None and (byte_index < 0 or byte_index >= L or
                                       byte_index * 2 >= len(ahex)):
            em.refuse("P2", "byte_index_outside_instruction", src, i, line)
            continue
        if field is not None and byte_index is not None:
            st, w = at.spec[mnem]["fields"][field]
            if not (st <= byte_index * 8 + 7 and st + w - 1 >= byte_index * 8):
                em.refuse("P2", "named_field_does_not_cover_stated_byte",
                          src, i, line)
                continue
        flds = [field] if field else at.fields_at_byte(mnem, byte_index)
        if not flds:
            em.refuse("P2", "no_db_field_covers_that_byte", src, i, line)
            continue

        outcome = obs = oracle = sem = None
        mo = RX_T_ARROW.search(line)
        if mo:
            obs = _obs_list(mo.group(1))
            outcome = OUTCOME.get(mo.group(3).upper())
            if mo.group(2) is not None:
                sem = (mo.group(2) == "True")
        if outcome is None:
            mo = RX_T_OUTEXP.search(line)
            if mo:
                obs = _obs_list(mo.group(1))
                oracle = _obs_list(mo.group(2))
                sem = (mo.group(3) == "PASS")
                outcome = "ok" if sem else "wrong_value"
        if outcome is None:
            mo = RX_S_BRACKET.match(line) and RX_T_STATUS.search(line)
            if mo:
                outcome = OUTCOME.get(mo.group(1).upper())
        if outcome is None:
            mo = RX_T_STATUS.search(line)
            if mo:
                outcome = OUTCOME.get(mo.group(1).upper())
        if outcome is None:
            em.refuse("P2", "no_outcome_token", src, i, line)
            continue

        for f in flds:
            rec = {"instr": mnem, "field": f, "value": value,
                   "outcome": outcome, "carrier": "anchor:" + ahex[:16],
                   "_anchor_bytes": ahex, "_anchor_line": aline,
                   "_exp": exp, "_run": run}
            if byte_index is not None:
                rec["byte_index"] = byte_index
            if obs is not None:
                rec["observed"] = obs
            if oracle is not None:
                rec["oracle"] = {"source": "transcript_expectation",
                                 "expected": oracle}
                rec["sem_match"] = bool(sem)
            em.emit(rec, "P2", CONF_PROSE, src, i)


# ============================================ P5: key/value dispatch record

# EXP-0003 writes one dispatch per file as `KEY value` lines. It is the only
# legacy shape that commits the ACTUAL dispatched program (`MAIN_SPLICED`)
# alongside the caller's request (`SPLICE ...: old -> new`), so it is the only
# legacy shape that can carry a real Gate A ledger.
RX_KV_ORIG = re.compile(r"^MAIN_ORIG\s+(" + HEXBLOB + r")\s*$")
RX_KV_SPLICED = re.compile(r"^MAIN_SPLICED\s+(" + HEXBLOB + r")\s*$")
# The replacement may be a single byte (`1c -> ff`) or the whole program, so
# this one does not use HEXBLOB's 4-byte floor; even length is checked below.
RX_KV_SPLICE = re.compile(
    r"^SPLICE\s+\S+@0x([0-9a-fA-F]+):\s*([0-9a-fA-F]{2,})\s*->\s*"
    r"([0-9a-fA-F]{2,})\b")
RX_KV_STATUS = re.compile(r"^STATUS\s+([A-Z_]+)\s*$")
RX_KV_RESULT = re.compile(r"^(?:RESULT|OUT)\s+(.*)$")


def parse_P5(lines, src, exp, run, at, em):
    orig = spliced = status = None
    splice = None
    result = None
    for line in lines:
        line = line.rstrip("\n")
        for rx, setter in ((RX_KV_ORIG, "orig"), (RX_KV_SPLICED, "spliced")):
            mo = rx.match(line)
            if mo:
                if setter == "orig":
                    orig = mo.group(1).lower()
                else:
                    spliced = mo.group(1).lower()
        mo = RX_KV_SPLICE.match(line)
        if mo:
            splice = (int(mo.group(1), 16), mo.group(2).lower(),
                      mo.group(3).lower())
        mo = RX_KV_STATUS.match(line)
        if mo:
            status = OUTCOME.get(mo.group(1).upper())
        mo = RX_KV_RESULT.match(line)
        if mo and result is None:
            result = mo.group(1).strip()
    if not (orig and spliced and splice):
        return
    em.candidate("P5")
    if status is None:
        em.refuse("P5", "no_status_line", src, 0, src)
        return
    absoff, old, new = splice
    if len(old) != len(new) or len(old) % 2:
        em.refuse("P5", "splice_old_new_length_mismatch", src, 0, src)
        return
    if old == new:
        em.refuse("P5", "no_byte_changed", src, 0, src)
        return
    tok_s = at.tokenize(spliced)
    tok_o = at.tokenize(orig)
    hit_s = [t for t in tok_s if t[0] <= absoff < t[0] + t[2]]
    hit_o = [t for t in tok_o if t[0] <= absoff < t[0] + t[2]]
    if len(hit_s) != 1 or len(hit_o) != 1:
        # The very failure EXP-0197 4.4 describes for `stop.reserved`: once the
        # replacement word overwrites byte 0 as well, the dispatched program no
        # longer tokenizes to the descriptor the case claims to be testing.
        em.refuse("P5", "spliced_program_does_not_tokenize_at_that_offset",
                  src, 0, src)
        return
    off, mnem, L, ihex = hit_s[0]
    if hit_o[0][1] != mnem:
        em.refuse("P5", "splice_changes_descriptor_identity", src, 0, src)
        return
    nb = len(new) // 2
    emitted = 0
    for j in range(nb):
        if new[2 * j:2 * j + 2] == old[2 * j:2 * j + 2]:
            continue
        rel = absoff + j - off
        flds = at.fields_at_byte(mnem, rel)
        if not flds:
            continue
        val = int(new[2 * j:2 * j + 2], 16)
        for f in flds:
            rec = {"instr": mnem, "field": f, "value": val, "byte_index": rel,
                   "bytes": ihex, "outcome": status,
                   "carrier": "prog:" + orig[:16],
                   "_exp": exp, "_run": run}
            if result:
                rec["observed"] = {"result": result}
            em.emit(rec, "P5", CONF_TABLE, src, 0)
            emitted += 1
    if not emitted:
        em.refuse("P5", "no_db_field_covers_any_changed_byte", src, 0, src)


# ================================================ P4: dispatched program corpus

PROG_KEYS = ("main_hex", "program_hex", "code_hex", "shader_hex")
OUTCOME_KEYS = ("command_buffer_status", "cb_status", "status", "tool_status",
                "exec_status")
PAYLOAD_KEYS = ("render", "out_word_hex", "out_hex", "out_words", "observed",
                "pixel", "read_words_hex", "output_hex", "colors")

STATUS_MAP = {
    "ok": "ok", "OK": "ok", "completed": "ok", "Completed": "ok", "4": "ok",
    "pass": "ok", "success": "ok",
    "error": "cmdbuf_error", "Error": "cmdbuf_error", "5": "cmdbuf_error",
    "fault": "fault", "hang": "hang", "timeout": "timeout",
    "notenqueued": "measurement_failure",
}


def _status_of(doc):
    """The execution outcome committed WITH the program bytes.

    Searched at the top level and one level into child dicts (EXP-0050 nests it
    under `render`). Not searched any deeper: a status found three levels away
    may belong to a different case, and a wrong pairing here would turn a
    compile-only record into a fabricated dispatch.
    """
    scopes = [doc] + [v for v in doc.values() if isinstance(v, dict)]
    for sc in scopes:
        for k in OUTCOME_KEYS:
            v = sc.get(k)
            if isinstance(v, (str, int)):
                st = STATUS_MAP.get(str(v).strip())
                if st:
                    return st
    return None


def _payload_of(doc):
    scopes = [doc] + [v for v in doc.values() if isinstance(v, dict)]
    for sc in scopes:
        for k in PAYLOAD_KEYS:
            if sc.get(k) is not None:
                return {k: sc[k]}
    return None


def parse_P4(doc, src, exp, run, at, em, line=0):
    """A raw record that pairs committed program bytes with an execution outcome.

    Emits `bytes` and NO `value`: there is no caller intent to compare, so this
    can only ever reach the geometry ladder's `bytes-seen` rung, never a Gate A
    ledger. A record with bytes but no outcome is compile-only corpus and goes to
    the separate stream.
    """
    prog = None
    for k in PROG_KEYS:
        v = doc.get(k)
        if isinstance(v, str) and _hex_ok(v) and len(v) >= 8:
            prog = v.lower()
            break
    if prog is None:
        return
    em.candidate("P4")
    toks = at.tokenize(prog)
    if not toks:
        em.refuse("P4", "program_does_not_tokenize", src, line, prog[:60])
        return
    st = _status_of(doc)
    payload = _payload_of(doc)
    case = doc.get("case") or doc.get("case_id") or doc.get("name")
    if st is None:
        for off, mnem, L, ihex in toks:
            em.emit_compile_only(
                {"instr": mnem, "bytes": ihex, "carrier": str(case),
                 "_exp": exp, "_run": run}, "C0", src, line)
        em.refuse("P4", "program_bytes_with_no_execution_outcome", src, line,
                  str(case))
        return
    for off, mnem, L, ihex in toks:
        for f in sorted(at.spec[mnem]["fields"]):
            rec = {"instr": mnem, "field": f, "bytes": ihex, "outcome": st,
                   "carrier": str(case), "_exp": exp, "_run": run}
            if payload is not None:
                rec["observed"] = payload
            em.emit(rec, "P4", CONF_STRUCTURED, src, line)


# ==================================================================== driving


def collect_programs(expdir, at, limit=4000):
    """Every distinct clean-tokenizing program hex committed under raw/.

    Used only by P3, to resolve an absolute offset to an instruction, and only
    when the resolution is unique.
    """
    out = set()
    rx = re.compile(r"\b([0-9a-fA-F]{16,})\b")
    n = 0
    for p, ext in EI.iter_files(os.path.join(expdir, "raw")):
        n += 1
        if n > limit:
            break
        try:
            data = open(p, errors="replace").read(4 << 20)
        except OSError:
            continue
        for mo in rx.finditer(data):
            h = mo.group(1).lower()
            if len(h) % 2 == 0 and len(out) < 4000:
                out.add(h)
    return out


def parse_experiment(expdir, at, em, want_p3=True):
    exp = os.path.basename(expdir)
    rawdir = os.path.join(expdir, "raw")
    if not os.path.isdir(rawdir):
        return
    programs = None
    for p, ext in EI.iter_files(rawdir):
        rel = os.path.relpath(p, ROOT)
        run = _run_of(p, expdir)
        if ext in TEXT_EXT:
            try:
                lines = open(p, errors="replace").read(16 << 20).splitlines()
            except OSError:
                continue
            parse_P1(lines, rel, exp, run, at, em)
            parse_P2(lines, rel, exp, run, at, em)
            parse_P5(lines, rel, exp, run, at, em)
            if want_p3 and any(RX_P3_HDR.search(x) for x in lines[:40]):
                if programs is None:
                    programs = collect_programs(expdir, at)
                parse_P3(lines, rel, exp, run, at, em, programs)
        elif ext == ".json":
            try:
                doc = json.load(open(p, errors="replace"))
            except Exception:
                continue
            for d, ln in _iter_dicts(doc):
                parse_P4(d, rel, exp, run, at, em, ln)
        elif ext == ".jsonl":
            try:
                fh = open(p, errors="replace")
            except OSError:
                continue
            with fh:
                for ln, line in enumerate(fh, 1):
                    line = line.strip()
                    if not line or line[0] != "{":
                        continue
                    try:
                        d = json.loads(line)
                    except Exception:
                        continue
                    for dd, _ in _iter_dicts(d):
                        parse_P4(dd, rel, exp, run, at, em, ln)


def _iter_dicts(doc, depth=0, ln=0):
    """Yield (dict, line) for a JSON document, including a JSON-in-`stdout`."""
    if depth > 5:
        return
    if isinstance(doc, dict):
        yield doc, ln
        so = doc.get("stdout")
        if isinstance(so, str) and so.strip().startswith("{"):
            for cand in (so.strip(), so.strip().splitlines()[-1]):
                try:
                    inner = json.loads(cand)
                except Exception:
                    continue
                for x in _iter_dicts(inner, depth + 1, ln):
                    yield x
                break
        for v in doc.values():
            if isinstance(v, (list, dict)):
                for x in _iter_dicts(v, depth + 1, ln):
                    yield x
    elif isinstance(doc, list):
        for i, v in enumerate(doc):
            if isinstance(v, (list, dict)):
                for x in _iter_dicts(v, depth + 1, ln or i):
                    yield x


def run_parse(only=None, verbose=True):
    at = Attrib()
    em = Emitter()
    dirs = sorted(d for d in os.listdir(EXPS)
                  if os.path.isdir(os.path.join(EXPS, d)))
    if only:
        dirs = [d for d in dirs if any(d.startswith(o) for o in only)]
    for i, d in enumerate(dirs, 1):
        before = em.stats["records"]
        parse_experiment(os.path.join(EXPS, d), at, em)
        got = em.stats["records"] - before
        if verbose and got:
            print("  [%3d/%3d] %-46s +%d" % (i, len(dirs), d, got))
            sys.stdout.flush()
    return em


# ---------------------------------------------------------------- cell build


def build_cells(records):
    """Turn emitted records into evidence_index cells, using ITS OWN code.

    Reusing `Indexer.handle` guarantees the legacy stream is scored by exactly
    the rules the modern indexer applies -- Gate A routing, control detection,
    the semantic-check test, the hard-outcome exclusion.
    """
    spec = EI.load_db()
    ix = EI.Indexer(spec)
    per = collections.defaultdict(lambda: {
        "cells": collections.defaultdict(EI._new_cell),
        "ctrl": collections.defaultdict(EI._new_cell),
        "meta": {"instr_names_seen": collections.Counter(),
                 "field_names_seen": collections.Counter(),
                 "instr_records": collections.Counter(),
                 "group_strings": set()},
        "runs": collections.Counter(),
    })
    for r in records:
        exp = r.get("_exp")
        b = per[exp]
        run = r.get("_run") or "raw"
        # Target is NOT asserted here. `_target_of_run` sees the same run-dir
        # name evidence_index would see; a README's prose device line is not
        # promoted into the target axis by this tool (see RESULTS.md).
        target = EI._target_of_run(run)
        b["runs"][run] += 1
        ix.handle(r, b["cells"], b["ctrl"], b["meta"],
                  (r.get("_src_file"), r.get("_src_line")), run, target,
                  in_raw=True)
    out = {}
    for exp, b in per.items():
        out[exp] = {
            "cells": {"%s.%s" % (m, f): EI._finish(c)
                      for (m, f), c in b["cells"].items()},
            "controls": {"%s.%s" % (m, f): EI._finish(c)
                         for (m, f), c in b["ctrl"].items()},
            "runs": dict(b["runs"]),
        }
    return out


def _merge_cell(dst, src):
    """Sum a legacy cell into an existing cache cell, conservatively."""
    for k in ("records", "in_raw", "ledger_records", "ledger_decoded",
              "ledger_agree", "ledger_disagree", "byte_ledger_records",
              "byte_ledger_agree", "byte_ledger_disagree", "sem_checks",
              "sem_true", "sem_false", "baseline_oracle", "host_oracle",
              "liveness_predictions", "prose_predictions", "victim",
              "sentinel_bad"):
        dst[k] = dst.get(k, 0) + src.get(k, 0)
    for k in ("n_req_values", "n_actual_bytes", "n_actual_field_values",
              "n_valid_payloads", "n_oracle_digests", "V", "L"):
        dst[k] = max(dst.get(k, 0), src.get(k, 0))
    for k in ("keying", "runs", "raw_runs", "targets", "outcomes", "hard",
              "sem_buckets", "contamination", "files", "carriers", "arms",
              "probes"):
        d = dict(dst.get(k) or {})
        for kk, vv in (src.get(k) or {}).items():
            d[kk] = d.get(kk, 0) + vv
        dst[k] = d
    return dst


def merge_cache(outdir, records, src_index=None, verbose=True):
    """Write a PARALLEL evidence-index cache: EXP-0209's, plus the legacy cells.

    The committed cache is never modified. `dashboards.py --index-dir OUTDIR`
    then scores exactly as it does in production, with the legacy era visible.
    """
    src_index = src_index or EI.CACHE
    os.makedirs(outdir, exist_ok=True)
    built = build_cells(records)
    n_new = n_merged = 0
    for fn in sorted(os.listdir(src_index)):
        if not fn.endswith(".json"):
            continue
        try:
            doc = json.load(open(os.path.join(src_index, fn)))
        except Exception:
            continue
        exp = fn[:-5]
        add = built.pop(exp, None)
        if add:
            for k, c in add["cells"].items():
                if k in doc["cells"]:
                    doc["cells"][k] = _merge_cell(doc["cells"][k], c)
                    n_merged += 1
                else:
                    doc["cells"][k] = c
                    n_new += 1
            for k, c in add["controls"].items():
                doc.setdefault("controls", {}).setdefault(k, c)
            m = doc["_meta"]
            for r, n in add["runs"].items():
                m.setdefault("runs", {})
                m["runs"][r] = m["runs"].get(r, 0) + n
                m.setdefault("run_targets", {}).setdefault(
                    r, EI._target_of_run(r))
            m["legacy_index"] = True
        json.dump(doc, open(os.path.join(outdir, fn), "w"), indent=1,
                  default=str)
    if verbose:
        print("merged cache -> %s  (new cells %d, merged into existing %d, "
              "experiments with no cache entry %d)"
              % (outdir, n_new, n_merged, len(built)))
    return n_new, n_merged


# ------------------------------------------------------------------- selftest


def selftest():
    """Both directions. A parser that never says `no` manufactures evidence.

    The must-EXTRACT half proves the instrument is not simply mute; the
    must-REFUSE half proves it does not resolve an ambiguity by plausibility.
    """
    ok = True

    def chk(name, cond):
        nonlocal ok
        print("%-4s %s" % ("PASS" if cond else "FAIL", name))
        if not cond:
            ok = False

    at = Attrib()

    def run_text(lines, parser=parse_P2, **kw):
        em = Emitter()
        parser(lines, "selftest.log", "EXP-SELFTEST", "raw", at, em, **kw)
        return em

    # ---------------------------------------------------------- MUST EXTRACT
    # 1. the EXP-0010 `jump.offset` fixture, verbatim from the committed raw.
    em = run_text([
        "  backward jump at main[106] = 0f0054d4ffffffffff00  "
        "offset_field=d4ffffffffff (signed -44)",
        "  splice offset->0 (jump to self) -> []  [HANG]        (contained)",
        "  splice offset->+8 (forward) -> [] [CMDBUF_ERROR]",
    ])
    hang = [r for r in em.records
            if r["instr"] == "jump" and r["field"] == "offset"
            and r["outcome"] == "hang" and r["value"] == 0]
    chk("EXTRACT: jump.offset -> 0 is recovered from the EXP-0010 prose as a HANG",
        len(hang) == 1 and hang[0]["_anchor_bytes"] == "0f0054d4ffffffffff00")
    chk("EXTRACT: the same anchor also yields offset->+8 as cmdbuf_error",
        any(r["field"] == "offset" and r["value"] == 8
            and r["outcome"] == "cmdbuf_error" for r in em.records))
    chk("EXTRACT: no `bytes` is ever synthesized for a splice record",
        all("bytes" not in r for r in em.records))

    # 2. EXP-0012: a relative `+12` splice on a committed device_load encoding.
    em = run_text([
        "  device_load at main[4] = 6710440001012000510100404600  (+12=main[16]=0x46)",
        "  splice +12 0x46->0x42 (8-bit ) -> ['0x11223301', '0x11223301'] [OK]",
    ])
    got = [r for r in em.records if r["instr"] == "device_load"]
    chk("EXTRACT: `splice +12 0x46->0x42` reaches device_load.elem_size (byte 12)",
        any(r["field"] == "elem_size" and r["value"] == 0x42
            and r["byte_index"] == 12 and r["outcome"] == "ok" for r in got))

    # 3. RT-5: a NAMED field with its byte offset, against committed bytes.
    em = run_text([
        "baseline op bytes: cf02560200040809d4432401",
        "[a_reg(+5)=b_reg 0x08  (expect B*B+C = 28j+1000)] STATUS OK  D=",
    ])
    chk("EXTRACT: RT-5 `[a_reg(+5)=... 0x08] STATUS OK` reaches matrix_mac.a_reg",
        any(r["instr"] == "matrix_mac" and r["field"] == "a_reg"
            and r["value"] == 8 and r["outcome"] == "ok" for r in em.records))

    # 4. EXP-0013: an out=/exp= pair is a real host prediction (Gate C).
    em = run_text([
        "  fneg ALU=0b010e09020a00800000 out=[-1.0, 2.0] exp=[-1.0, 2.0] PASS",
        "  splice b5 0x0a->0x02 out=[1.0, 2.0] exp abs=[1.0, 2.0] PASS",
    ])
    sem = [r for r in em.records if r.get("sem_match") is True]
    chk("EXTRACT: `out=/exp=/PASS` is emitted with an oracle and sem_match",
        len(sem) >= 1 and sem[0].get("oracle", {}).get("expected") == [1.0, 2.0])

    # 5. P1: a dense byte-sweep table row.
    em = Emitter()
    parse_P1([
        "# source=kernels/iadd.metal ALU@0x20 len=10 bytes=9f015600020800a81705",
        "# sweeping rel=0x7 (abs 0x27)  A=[12, 20, 7, 100] B=[3, 6, 5, 8]",
        "0x01  OK  min        [3 6 5 8]  raw=03000000060000000500000008000000",
        "0x03  FAULT:CMDBUF_ERROR",
    ], "selftest.log", "EXP-SELFTEST", "raw", at, em)
    chk("EXTRACT: a P1 sweep row yields a record on the byte-7 field(s)",
        any(r["value"] == 1 and r["byte_index"] == 7 and r["outcome"] == "ok"
            for r in em.records))
    chk("EXTRACT: a P1 `FAULT:CMDBUF_ERROR` row is kept as a hard outcome",
        any(r["value"] == 3 and r["outcome"] == "cmdbuf_error"
            for r in em.records))
    chk("EXTRACT: a P1 row's `raw=` output buffer never becomes `bytes`",
        all("bytes" not in r for r in em.records))

    # 6. P4: program bytes WITH an outcome are a dispatch record.
    em = Emitter()
    parse_P4({"case": "c1", "main_hex": "09051c0100c00e000000",
              "command_buffer_status": "ok", "render": {"colors": ["11223344"]}},
             "selftest.json", "EXP-SELFTEST", "raw", at, em)
    chk("EXTRACT: program bytes + a committed outcome emit dispatch records",
        any(r["instr"] == "falu2" and "bytes" in r and "value" not in r
            for r in em.records))

    # ----------------------------------------------------------- MUST REFUSE
    # 7. the constant-program line that LOOKS like an instruction splice.
    em = run_text([
        "  const_program region abs_off=7008 len=64",
        "  splice cp[0] 0x03->0x00                   -> [11, 22] match=True [OK]",
        "  splice cp[0:4]->0e000000 (no-load variant head) -> [11, 22] [OK]",
    ])
    chk("REFUSE: `splice cp[0] 0x03->0x00` (constant program) emits nothing",
        len(em.records) == 0 and em.stats["unparsed"] == 2)

    # 8. a splice with no anchor in scope.
    em = run_text(["  splice +12 0x46->0x42 -> [1, 2] [OK]"])
    chk("REFUSE: a splice with no anchored instruction bytes emits nothing",
        len(em.records) == 0
        and em.per_parser["P2"]["why_no_live_anchor"] == 1)

    # 9. an anchor whose bytes do not tokenize.
    em = run_text([
        "  mystery at main[4] = ffffffffffffffffffffffff",
        "  splice +2 0x00->0x01 -> [1] [OK]",
    ])
    chk("REFUSE: bytes our own disassembler cannot tokenize are not an anchor",
        len(em.records) == 0)

    # 10. a named target that is not a field of the anchored descriptor.
    em = run_text([
        "  trailing stop 0e000000 at main[32]",
        "  splice stop payload->ff -> [11, 22] match=True [OK]",
    ])
    chk("REFUSE: `payload` is not a db.json field of `stop`, so nothing is emitted",
        len(em.records) == 0
        and em.per_parser["P2"]["why_named_target_is_not_a_db_field"] == 1)

    # 11. a byte index past the end of the anchored instruction.
    em = run_text([
        "  trailing stop 0e000000 at main[32]",
        "  splice +9 0x00->0x01 -> [1] [OK]",
    ])
    chk("REFUSE: byte +9 of a 4-byte `stop` is outside the instruction",
        len(em.records) == 0
        and em.per_parser["P2"]["why_byte_index_outside_instruction"] == 1)

    # 12. two different anchored mnemonics live at once.
    em = run_text([
        "  device_load at main[4] = 6710440001012000510100404600",
        "  jump at main[106] = 0f0054d4ffffffffff00",
        "  splice +5 0x00->0x01 -> [1] [OK]",
    ])
    chk("REFUSE: two live anchors make the splice ambiguous, not resolvable",
        len(em.records) == 0
        and em.per_parser["P2"]["why_ambiguous_anchor"] == 1)

    # 13. a splice with no outcome token at all.
    em = run_text([
        "  device_load at main[4] = 6710440001012000510100404600",
        "  splice +12 0x46->0x42 (8-bit)",
    ])
    chk("REFUSE: a splice with no outcome token is not an observation",
        len(em.records) == 0
        and em.per_parser["P2"]["why_no_outcome_token"] == 1)

    # 14. a named field that does not cover the byte the line states.
    em = run_text([
        "baseline op bytes: cf02560200040809d4432401",
        "[a_reg(+9)=b_reg 0x08  (expect ...)] STATUS OK  D=",
    ])
    chk("REFUSE: `a_reg(+9)` contradicts a_reg's own bit span (byte 5)",
        len(em.records) == 0
        and em.per_parser["P2"]["why_named_field_does_not_cover_stated_byte"] == 1)

    # 15. a P1 table with no baseline encoding in its header.
    em = Emitter()
    parse_P1(["# sweeping rel=0x7", "0x01  OK  min  [3 6 5 8]"],
             "selftest.log", "EXP-SELFTEST", "raw", at, em)
    chk("REFUSE: a sweep table with no committed baseline encoding emits nothing",
        len(em.records) == 0
        and em.per_parser["P1"]["why_no_anchor_bytes_in_header"] == 1)

    # 16. a P1 table whose header states no byte index.
    em = Emitter()
    parse_P1(["# bytes=9f015600020800a81705", "0x01  OK  min  [3 6 5 8]"],
             "selftest.log", "EXP-SELFTEST", "raw", at, em)
    chk("REFUSE: a sweep table with no stated byte index emits nothing",
        len(em.records) == 0
        and em.per_parser["P1"]["why_header_states_no_byte_index"] == 1)

    # 17. compile-only program bytes must NOT become a dispatch record.
    em = Emitter()
    parse_P4({"case": "k01", "main_hex": "09051c0100c00e000000"},
             "selftest.json", "EXP-SELFTEST", "raw", at, em)
    chk("REFUSE: program bytes with NO outcome are compile-only, not dispatch",
        len(em.records) == 0 and len(em.compile_only) == 2)

    # 18. P3 must refuse when the program is not uniquely identified.
    em = Emitter()
    parse_P3(["# _agc.main len=6 region_off=0 op-byte@0x02=orig 0x1c",
              "0x04  OK    fadd              [6 9 10 12]"],
             "selftest.log", "EXP-SELFTEST", "raw", at, em,
             {"09051c0100c0", "09011c0500c8"})
    chk("REFUSE: two candidate programs of the stated length -> unparsed",
        len(em.records) == 0
        and em.per_parser["P3"]["why_program_not_uniquely_identified"] == 1)
    em = Emitter()
    parse_P3(["# _agc.main len=6 region_off=0 op-byte@0x02=orig 0x1c",
              "0x04  OK    fadd              [6 9 10 12]"],
             "selftest.log", "EXP-SELFTEST", "raw", at, em, {"09051c0100c0"})
    chk("EXTRACT: exactly one candidate program resolves the absolute offset",
        any(r["instr"] == "falu2" and r["byte_index"] == 2
            and r["value"] == 4 for r in em.records))

    # 19a. the program anchor: an absolute `main[N]` index is resolved by
    # tokenizing the committed program, not by proximity to an instruction.
    E1 = "0ca01006e7105400000020001100009011000e000000"
    em = run_text(["main: " + E1,
                   "  splice main[4]=0x00 -> [0, 0, 0, 0]  [OK]"])
    chk("EXTRACT: `main[4]` resolves through the committed program to its owner",
        any(r["instr"] == "device_store" and r["byte_index"] == 0
            and r["value"] == 0 and r["outcome"] == "ok" for r in em.records)
        or not at.fields_at_byte("device_store", 0))
    em = run_text(["  splice main[4]=0x00 -> [0, 0]  [OK]"])
    chk("REFUSE: an absolute main[N] with no committed program emits nothing",
        len(em.records) == 0
        and em.per_parser["P2"]["why_no_unique_program_anchor"] == 1)
    em = run_text(["main: " + E1,
                   "  splice main[999]=0x00 -> [0, 0]  [OK]"])
    chk("REFUSE: a main index past the end of the program emits nothing",
        len(em.records) == 0
        and em.per_parser["P2"]["why_main_index_not_inside_one_clean_token"] == 1)

    # 19b. P5: the only legacy shape with a real Gate A ledger, both ways.
    em = Emitter()
    parse_P5([
        "MAIN_ORIG 0ca01006e7105400000020001100009011000e000000",
        "SPLICE _agc.main@0x12: 0e000000 -> 0e0000ff",
        "MAIN_SPLICED 0ca01006e7105400000020001100009011000e0000ff",
        "STATUS OK", "RESULT 2 11 22",
    ], "selftest.log", "EXP-SELFTEST", "raw", at, em)
    chk("EXTRACT: P5 emits the requested byte AND the actual dispatched bytes",
        any(r["instr"] == "stop" and r["field"] == "reserved"
            and r["value"] == 0xff and r["bytes"] == "0e0000ff"
            for r in em.records))
    em = Emitter()
    parse_P5([
        "MAIN_ORIG 0ca01006e7105400000020001100009011000e000000",
        "SPLICE _agc.main@0x12: 0e000000 -> ffffffff",
        "MAIN_SPLICED 0ca01006e710540000002000110000901100ffffffff",
        "STATUS OK",
    ], "selftest.log", "EXP-SELFTEST", "raw", at, em)
    chk("REFUSE: a splice that destroys the descriptor's own match bits is "
        "not evidence about that descriptor's field",
        len(em.records) == 0)

    # 20. the attributor itself, both ways.
    chk("ATTRIB: a known encoding tokenizes to its db.json mnemonic",
        at.anchor("0f0054d4ffffffffff00") == ("jump", 10))
    chk("ATTRIB: odd-length / non-hex is refused",
        at.anchor("0f0054d") is None and at.anchor("zzzz") is None)
    chk("ATTRIB: a byte index past the descriptor length has no fields",
        at.fields_at_byte("stop", 9) == [])
    chk("ATTRIB: byte 12 of device_load resolves to elem_size",
        at.fields_at_byte("device_load", 12) == ["elem_size"])
    chk("ATTRIB: a field name that is not in db.json is refused",
        not at.has_field("jump", "offsets") and at.has_field("jump", "offset"))

    # 21. the emitted shape must be what evidence_index consumes.
    em = run_text([
        "  backward jump at main[106] = 0f0054d4ffffffffff00",
        "  splice offset->0 -> []  [HANG]",
    ])
    cells = build_cells([dict(r, _exp="EXP-SELFTEST") for r in em.records])
    c = cells["EXP-SELFTEST"]["cells"].get("jump.offset")
    chk("SHAPE: the record is admitted by evidence_index's own Indexer",
        bool(c) and c["records"] == 1 and c["in_raw"] == 1
        and c["hard"].get("hang") == 1)
    chk("SHAPE: a hang is NOT counted as a valid payload",
        bool(c) and c["n_valid_payloads"] == 0)

    print("\nLEGACY-INDEX SELFTEST %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


# --------------------------------------------------------------------- survey


def survey():
    """The format inventory: what is actually in `experiments/*/raw/`."""
    inv = {"by_ext": collections.Counter(), "bytes": collections.Counter(),
           "exps_by_ext": collections.defaultdict(set),
           "dirs_with_raw": 0, "dirs_without_raw": 0, "per_exp": {}}
    for d in sorted(os.listdir(EXPS)):
        p = os.path.join(EXPS, d)
        if not os.path.isdir(p):
            continue
        r = os.path.join(p, "raw")
        if not os.path.isdir(r):
            inv["dirs_without_raw"] += 1
            continue
        inv["dirs_with_raw"] += 1
        per = collections.Counter()
        for dp, dn, fn in os.walk(r):
            dn[:] = [x for x in dn if x not in EI.SKIPDIRS]
            for f in fn:
                e = os.path.splitext(f)[1].lower() or "(noext)"
                try:
                    sz = os.path.getsize(os.path.join(dp, f))
                except OSError:
                    continue
                inv["by_ext"][e] += 1
                inv["bytes"][e] += sz
                inv["exps_by_ext"][e].add(d)
                per[e] += 1
        inv["per_exp"][d] = dict(per)
    inv["by_ext"] = dict(inv["by_ext"])
    inv["bytes"] = dict(inv["bytes"])
    inv["exps_by_ext"] = {k: sorted(v) for k, v in inv["exps_by_ext"].items()}
    return inv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--survey", action="store_true")
    ap.add_argument("--parse", nargs="*", metavar="SLUG")
    ap.add_argument("--merge-cache", metavar="OUTDIR")
    ap.add_argument("--parsers", default=None,
                    help="comma-separated parser ids to merge, e.g. P1,P2,P3,P5. "
                         "Default: all. Use it to see how much of a delta rests "
                         "on the weakest parser.")
    ap.add_argument("--out", default=OUTDIR)
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.survey:
        print(json.dumps(survey(), indent=1, default=str))
        return 0
    if a.parse is not None or a.merge_cache:
        em = run_parse(a.parse or None)
        os.makedirs(a.out, exist_ok=True)
        with open(os.path.join(a.out, "legacy_records.jsonl"), "w") as fh:
            for r in em.records:
                fh.write(json.dumps(r, sort_keys=True, default=str) + "\n")
        with open(os.path.join(a.out, "compile_only_records.jsonl"), "w") as fh:
            for r in em.compile_only:
                fh.write(json.dumps(r, sort_keys=True, default=str) + "\n")
        stats = {"records": len(em.records),
                 "compile_only": len(em.compile_only),
                 "candidates": em.stats["candidates"],
                 "unparsed": em.stats["unparsed"],
                 "per_parser": {k: dict(v) for k, v in em.per_parser.items()},
                 "unparsed_samples": dict(em.unparsed_samples)}
        json.dump(stats, open(os.path.join(a.out, "parse_stats.json"), "w"),
                  indent=1, default=str)
        print(json.dumps({k: stats[k] for k in
                          ("records", "compile_only", "candidates", "unparsed")},
                         indent=1))
        if a.merge_cache:
            want = set((a.parsers or "").split(",")) if a.parsers else None
            recs = [r for r in em.records
                    if want is None or r.get("_parser") in want]
            print("merging %d of %d records (parsers=%s)"
                  % (len(recs), len(em.records), a.parsers or "all"))
            merge_cache(a.merge_cache, recs)
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
