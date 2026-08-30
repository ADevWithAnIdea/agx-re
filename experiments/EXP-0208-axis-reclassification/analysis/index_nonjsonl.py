#!/usr/bin/env python3
"""EXP-0208 step 2 -- index the NON-jsonl committed evidence.

EXP-0189's collector required `raw/**/*.jsonl`; the whole pre-EXP-0138 era stores its
evidence as .json / .txt / .log / .out / .md, and some (EXP-M4-14/splice_results.json)
is not under raw/ at all. This scanner reads all of it.

Two passes per file:
  A. structural (.json only) -- recursive walk for any dict carrying an op/instr-ish key
     together with a field-ish key; these are the root-evidence-json splice records.
  B. textual (all) -- whole-word mentions of a db.json mnemonic, and per-line
     co-occurrence of a mnemonic with one of ITS OWN field names.

Pure desk analysis over our own committed artefacts. No device. No Apple binaries.
"""
import json, os, re, sys, collections

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "work", "raw_index_nonjsonl.jsonl")

EXTS = (".json", ".txt", ".log", ".out", ".stdout", ".md", ".csv", ".tsv")
SKIP_EXP = {"EXP-0208-axis-reclassification"}

db = json.load(open(os.path.join(ROOT, "tools/agx-isa/db.json")))
MNEM = {}
for d in db["instructions"]:
    MNEM[d["mnemonic"]] = set(f["name"] for f in d.get("fields", []) or [])
mnem_re = re.compile(r"\b(" + "|".join(sorted(map(re.escape, MNEM), key=len, reverse=True)) + r")\b")

OPKEYS = ("op", "instr", "instruction", "mnemonic", "mnem", "opcode_name")
FKEYS = ("field", "field_name", "fld")

def walk_json(o, hits, path=""):
    if isinstance(o, dict):
        opv = None; fv = None
        for k in OPKEYS:
            if isinstance(o.get(k), str): opv = o[k]; break
        for k in FKEYS:
            if isinstance(o.get(k), str): fv = o[k]; break
        if opv and fv:
            if "." in fv and fv.split(".", 1)[0] in MNEM:
                opv, fv = fv.split(".", 1)
            hits.append((opv, fv, path, sorted(o.keys())[:14]))
        for k, v in o.items():
            walk_json(v, hits, path + "/" + str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            if i < 4000:
                walk_json(v, hits, path + "[]")

def main():
    out = open(OUT, "w")
    nfile = 0
    for dp, dn, fn in os.walk(os.path.join(ROOT, "experiments")):
        dn[:] = [d for d in dn if d not in SKIP_EXP and d != ".git"]
        for f in fn:
            if not f.endswith(EXTS):
                continue
            path = os.path.join(dp, f)
            rel = os.path.relpath(path, ROOT)
            parts = rel.split(os.sep)
            if len(parts) < 2: continue
            exp = parts[1]
            if exp in SKIP_EXP: continue
            try:
                sz = os.path.getsize(path)
            except OSError:
                continue
            if sz > 80 * 1024 * 1024:
                continue
            nfile += 1
            struct = []
            if f.endswith(".json"):
                try:
                    o = json.load(open(path, errors="replace"))
                    hits = []
                    walk_json(o, hits)
                    cc = collections.Counter((a, b) for a, b, _, _ in hits)
                    keysample = {}
                    for a, b, p, ks in hits:
                        keysample.setdefault((a, b), (p, ks))
                    struct = [dict(op=a, field=b, n=n, path=keysample[(a, b)][0],
                                   keys=keysample[(a, b)][1]) for (a, b), n in cc.most_common(400)]
                except Exception:
                    pass
            try:
                txt = open(path, errors="replace").read()
            except Exception:
                txt = ""
            mm = collections.Counter(mnem_re.findall(txt))
            pairs = collections.Counter()
            if mm:
                for line in txt.splitlines():
                    ms = set(mnem_re.findall(line))
                    if not ms: continue
                    for m in ms:
                        for fld in MNEM[m]:
                            if re.search(r"\b" + re.escape(fld) + r"\b", line):
                                pairs[(m, fld)] += 1
            if not mm and not struct:
                continue
            out.write(json.dumps(dict(
                file=rel, exp=exp, is_raw=(os.sep + "raw" + os.sep in os.sep + rel),
                size=sz, ext=os.path.splitext(f)[1],
                mnemonics={k: v for k, v in mm.most_common(200)},
                pairs=[[a, b, n] for (a, b), n in pairs.most_common(400)],
                struct=struct)) + "\n")
    out.close()
    sys.stderr.write("files=%d\n" % nfile)

main()
