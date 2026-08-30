#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0197 step 1 -- for every ORIGINAL citation named by a "has no per-value
records" clause, search that experiment under EVERY keying for per-value records of
the named field.

The defect under investigation is that EXP-0189's collector indexes a record ONLY
when `field` and `instr` are both strings, `field` does not start with `_`, and the
file ends in `.jsonl`.  So a field-name index is not admissible evidence of absence
here.  This scanner therefore uses four independent keyings, and reports each
separately so that a "no" from one is never read as a "no" overall:

  K1  named      : record with instr == <mnem> and field == <field>
  K2  byte-span  : record with instr == <mnem>, field null/underscore-prefixed, and
                   byte_index (or __raw_b<N>) inside the field's db.json byte span
  K3  grouping   : any record whose group/carrier/arm/name/item/case/kernel/label
                   string names the field or the mnemonic
  K4  encodings  : hex blobs harvested from ANY file of the experiment (jsonl, json,
                   txt, log, hex -- the formats EXP-0189 never opened), tokenized
                   with our own disassembler (tools/agx-isa).  ANCHORED = the
                   instruction appears in a clean tokenization from the blob start.
                   MATCHFIT = db.json's own match constraints hold in some L-byte
                   window (weaker; an 8-bit match fits by chance, so it is reported
                   but never relied on alone).

K4 is the decisive keying for the pre-2026-08 experiments, whose raw is text logs
and per-case .json -- formats in which "a record keyed by field name" cannot exist
at all, so K1/K2 returning zero there says nothing.

Read-only.  Writes work/scan_<key>.json and work/scan_summary.json.
"""
import json, os, re, sys, collections

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(EXP, "..", ".."))
EXPS = os.path.join(ROOT, "experiments")
WORK = os.path.join(EXP, "work")
sys.path.insert(0, os.path.join(ROOT, "tools", "agx-isa"))
import isadb  # noqa: E402  (our own clean-room disassembler)

HEXFULL = re.compile(r"^(?:0x)?[0-9a-fA-F]+$")
HEXRUN = re.compile(r"[0-9a-fA-F]{8,}")
GROUPKEYS = ("group", "carrier", "arm", "name", "item", "case", "case_name",
             "kernel", "label", "test", "op", "tag", "id", "func", "function")
SKIPDIRS = {"__pycache__", ".git"}
SKIPEXT = {".png", ".jpg", ".gz", ".zip", ".bin", ".o", ".dylib", ".metallib",
           ".air", ".pyc"}
MAXBLOB = 16384          # hex chars; longer strings are truncated-scanned in windows
CAP_UNIQUE_BLOBS = 400000


def iter_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIPDIRS]
        for fn in sorted(filenames):
            ext = os.path.splitext(fn)[1].lower()
            if ext in SKIPEXT:
                continue
            p = os.path.join(dirpath, fn)
            try:
                if os.path.getsize(p) == 0:
                    continue
            except OSError:
                continue
            yield p


def walk_strings(obj, out, depth=0):
    if depth > 12:
        return
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            walk_strings(v, out, depth + 1)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            walk_strings(v, out, depth + 1)


HEXTOK = re.compile(r"^(?:0x)?[0-9a-fA-F]+$")


def spaced_runs(text, minbytes):
    """Join maximal runs of whitespace-separated pure-hex tokens.

    EXP-0029/0034/0035/0037 write their encodings as `0f 80 86 02 07 02 80 06`
    or `a9171415 02000000 00018f02 5400`.  A contiguous-run regex sees none of
    them -- which is the same class of blind spot this audit is investigating,
    so it is fixed here rather than reported as an absence."""
    out, cur = [], []
    for tok in re.split(r"[\s]+", text):
        t = tok.strip()
        if t.endswith(":"):
            # an address/label column ("00000500:") ends a run, it is not part of it
            if cur:
                h = "".join(cur)
                if len(h) // 2 >= minbytes:
                    out.append(h)
                cur = []
            continue
        core = t[2:] if t[:2] in ("0x", "0X") else t
        if core and len(core) % 2 == 0 and len(core) <= 32 and HEXTOK.match(t):
            cur.append(core.lower())
        else:
            if cur:
                h = "".join(cur)
                if len(h) // 2 >= minbytes:
                    out.append(h)
                cur = []
    if cur:
        h = "".join(cur)
        if len(h) // 2 >= minbytes:
            out.append(h)
    return out


def blobs_from_strings(strs, minbytes):
    out = []
    for s in strs:
        if not s or len(s) > MAXBLOB:
            # still mine long strings for embedded runs
            if s and len(s) <= 4 * MAXBLOB:
                for mo in HEXRUN.finditer(s):
                    h = mo.group(0)
                    if len(h) % 2 == 0 and len(h) // 2 >= minbytes:
                        out.append(h.lower())
            continue
        t = s[2:] if s[:2] in ("0x", "0X") else s
        if HEXFULL.match(s) and len(t) % 2 == 0 and len(t) // 2 >= minbytes:
            out.append(t.lower())
        else:
            for mo in HEXRUN.finditer(s):
                h = mo.group(0)
                if len(h) % 2 == 0 and len(h) // 2 >= minbytes:
                    out.append(h.lower())
        out.extend(spaced_runs(s, minbytes))
    return out


def anchored_hits(buf, mnem):
    """Instructions with this mnemonic in a clean tokenization from offset 0."""
    try:
        recs, leftover = isadb.disassemble(buf)
    except Exception:
        return []
    hits, off = [], 0
    for r in recs:
        if r.get("error"):
            break
        if r.get("mnemonic") == mnem:
            hits.append((off, r.get("fields") or {}))
        off += r.get("length") or 0
    return hits


def matchfit_hits(buf, spec):
    """Offsets where db.json's own match constraints hold. Weak; reported separately."""
    L = spec["length"]
    if not L or not spec["match"] or len(buf) < L:
        return []
    out = []
    for d in range(0, len(buf) - L + 1):
        v = int.from_bytes(buf[d:d + L], "little")
        if all(((v >> s) & ((1 << w) - 1)) == val for s, w, val in spec["match"]):
            out.append((d, v))
    return out


def load_specs():
    db = json.load(open(os.path.join(ROOT, "tools/agx-isa/db.json")))
    return {i["mnemonic"]: {"length": i.get("length"), "match": i.get("match") or [],
                            "fields": {f["name"]: (f["start"], f["width"])
                                       for f in i.get("fields", [])}}
            for i in db["instructions"]}


def scan_dir(expdir, mnem, field, span, spec):
    """Return the four keyings' evidence for (mnem, field) inside experiments/<expdir>."""
    root = os.path.join(EXPS, expdir)
    L = spec["length"] or 4
    span_bytes = set()
    if span:
        s, w = span
        span_bytes = set(range(s // 8, (s + w - 1) // 8 + 1))
    R = {
        "dir": expdir, "has_raw": os.path.isdir(os.path.join(root, "raw")),
        "files_scanned": 0, "jsonl_files": 0, "json_files": 0, "text_files": 0,
        "k1_named": {"n": 0, "values": set(), "first": None, "by_file": collections.Counter()},
        "k2_byte": {"n": 0, "values": set(), "first": None, "by_file": collections.Counter()},
        "k3_group": {"n": 0, "labels": collections.Counter(), "first": None},
        "k4_anchored": {"blobs": 0, "values": set(), "first": None,
                        "by_file": collections.Counter(), "examples": []},
        "k4_matchfit": {"blobs": 0, "values": set(), "first": None,
                        "by_file": collections.Counter()},
        "instr_records_any": 0,
        "instr_names_seen": collections.Counter(),
        "field_names_seen": collections.Counter(),
    }
    seen_blob = {}

    def note_blob(h, where):
        if h in seen_blob:
            return
        if len(seen_blob) > CAP_UNIQUE_BLOBS:
            return
        seen_blob[h] = where
        try:
            buf = bytes.fromhex(h)
        except ValueError:
            return
        for off, fl in anchored_hits(buf, mnem):
            R["k4_anchored"]["blobs"] += 1
            R["k4_anchored"]["by_file"][where[0]] += 1
            if field in fl:
                R["k4_anchored"]["values"].add(fl[field])
            if R["k4_anchored"]["first"] is None:
                R["k4_anchored"]["first"] = {"file": where[0], "line": where[1],
                                             "hex": h[:96], "offset": off,
                                             "field_value": fl.get(field)}
            if len(R["k4_anchored"]["examples"]) < 8:
                R["k4_anchored"]["examples"].append(
                    {"file": where[0], "line": where[1], "hex": h[:96],
                     "offset": off, "field_value": fl.get(field)})
        if span:
            s, w = span
            mask = (1 << w) - 1
            for d, v in matchfit_hits(buf, spec):
                R["k4_matchfit"]["blobs"] += 1
                R["k4_matchfit"]["by_file"][where[0]] += 1
                R["k4_matchfit"]["values"].add((v >> s) & mask)
                if R["k4_matchfit"]["first"] is None:
                    R["k4_matchfit"]["first"] = {"file": where[0], "line": where[1],
                                                 "hex": h[:96], "offset": d,
                                                 "field_value": (v >> s) & mask}

    def handle_record(rec, where):
        if not isinstance(rec, dict):
            return
        ins, fld = rec.get("instr"), rec.get("field")
        if isinstance(ins, str):
            R["instr_names_seen"][ins] += 1
        if isinstance(fld, str):
            R["field_names_seen"][fld] += 1
        if ins == mnem:
            R["instr_records_any"] += 1
            if fld == field:
                k = R["k1_named"]
                k["n"] += 1
                k["values"].add(json.dumps(rec.get("value"), sort_keys=True))
                k["by_file"][where[0]] += 1
                if k["first"] is None:
                    k["first"] = {"file": where[0], "line": where[1],
                                  "record": json.dumps(rec)[:600]}
            elif fld is None or (isinstance(fld, str) and fld.startswith("_")):
                bi = rec.get("byte_index")
                if bi is None and isinstance(fld, str):
                    mo = re.search(r"b(?:yte)?[_+]?(\d+)$", fld)
                    if mo:
                        bi = int(mo.group(1))
                if bi is not None and bi in span_bytes:
                    k = R["k2_byte"]
                    k["n"] += 1
                    k["values"].add(json.dumps(rec.get("value"), sort_keys=True))
                    k["by_file"][where[0]] += 1
                    if k["first"] is None:
                        k["first"] = {"file": where[0], "line": where[1],
                                      "record": json.dumps(rec)[:600]}
        for gk in GROUPKEYS:
            gv = rec.get(gk)
            if isinstance(gv, str) and (field in gv or mnem in gv):
                k = R["k3_group"]
                k["n"] += 1
                k["labels"]["%s=%s" % (gk, gv)] += 1
                if k["first"] is None:
                    k["first"] = {"file": where[0], "line": where[1], "key": gk,
                                  "value": gv, "record": json.dumps(rec)[:400]}
        strs = []
        walk_strings(rec, strs)
        for h in blobs_from_strings(strs, L):
            note_blob(h, where)

    for p in iter_files(root):
        rel = os.path.relpath(p, ROOT)
        R["files_scanned"] += 1
        ext = os.path.splitext(p)[1].lower()
        try:
            if ext == ".jsonl":
                R["jsonl_files"] += 1
                with open(p, errors="replace") as fh:
                    for ln, line in enumerate(fh, 1):
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            rec = json.loads(line)
                        except Exception:
                            note_blob_text(line, (rel, ln), L, note_blob)
                            continue
                        if isinstance(rec, list):
                            for rr in rec:
                                handle_record(rr, (rel, ln))
                        else:
                            handle_record(rec, (rel, ln))
            elif ext == ".json":
                R["json_files"] += 1
                with open(p, errors="replace") as fh:
                    try:
                        doc = json.load(fh)
                    except Exception:
                        doc = None
                if doc is None:
                    continue
                if isinstance(doc, list):
                    for i, rr in enumerate(doc):
                        handle_record(rr, (rel, i))
                elif isinstance(doc, dict):
                    handle_record(doc, (rel, 0))
                    for k, v in doc.items():
                        if isinstance(v, list):
                            for i, rr in enumerate(v):
                                handle_record(rr, (rel, "%s[%d]" % (k, i)))
                        elif isinstance(v, dict):
                            for k2, v2 in v.items():
                                handle_record(v2, (rel, "%s.%s" % (k, k2)))
            else:
                R["text_files"] += 1
                with open(p, errors="replace") as fh:
                    for ln, line in enumerate(fh, 1):
                        if len(line) > 4 * MAXBLOB:
                            line = line[:4 * MAXBLOB]
                        for h in blobs_from_strings([line], L):
                            note_blob(h, (rel, ln))
        except (OSError, UnicodeDecodeError):
            continue

    for k in ("k1_named", "k2_byte"):
        R[k]["values"] = sorted(R[k]["values"])[:300]
        R[k]["distinct_values"] = len(set(R[k]["values"]))
        R[k]["by_file"] = dict(R[k]["by_file"])
    for k in ("k4_anchored", "k4_matchfit"):
        vals = sorted(R[k]["values"])
        R[k]["distinct_values"] = len(vals)
        R[k]["values"] = vals[:300]
        R[k]["by_file"] = dict(R[k]["by_file"].most_common(20))
    R["k3_group"]["labels"] = dict(R["k3_group"]["labels"].most_common(25))
    R["instr_names_seen"] = dict(R["instr_names_seen"].most_common(15))
    R["field_names_seen"] = dict(R["field_names_seen"].most_common(15))
    R["unique_blobs"] = len(seen_blob)
    return R


def note_blob_text(line, where, L, cb):
    for h in blobs_from_strings([line], L):
        cb(h, where)


def main():
    only = set(sys.argv[1:])
    rows = json.load(open(os.path.join(WORK, "rows.json")))
    specs = load_specs()
    summary = {}
    for r in rows:
        if only and r["key"] not in only:
            continue
        spec = specs[r["instr"]]
        span = (r["start"], r["width"]) if r["start"] is not None else None
        per = {}
        for slug, dirs in r["orig_dirs"].items():
            for d in dirs:
                per[d] = scan_dir(d, r["instr"], r["field"], span, spec)
                a = per[d]
                print("  %-34s %-38s K1=%-6d K2=%-6d K3=%-5d K4anch=%-6d(%d vals) "
                      "K4fit=%-6d(%d vals) files=%d" % (
                          r["key"], d, a["k1_named"]["n"], a["k2_byte"]["n"],
                          a["k3_group"]["n"], a["k4_anchored"]["blobs"],
                          a["k4_anchored"]["distinct_values"],
                          a["k4_matchfit"]["blobs"],
                          a["k4_matchfit"]["distinct_values"], a["files_scanned"]))
                sys.stdout.flush()
        summary[r["key"]] = {"row": {k: r[k] for k in
                                     ("instr", "field", "label", "target", "evidence",
                                      "orig_slugs", "live_slugs", "start", "width",
                                      "bytes_of_span", "corrected_by_0196")},
                             "original": per}
        fn = os.path.join(WORK, "scan_%s.json" % r["key"].replace(".", "_"))
        json.dump(summary[r["key"]], open(fn, "w"), indent=1, default=str)
    json.dump(summary, open(os.path.join(WORK, "scan_summary.json"), "w"),
              indent=1, default=str)


if __name__ == "__main__":
    main()
