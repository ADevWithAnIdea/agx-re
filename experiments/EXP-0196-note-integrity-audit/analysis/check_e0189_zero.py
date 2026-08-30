#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0196 -- test the 64 "EXP-0189 withheld (...): N values dispatched over M
arm(s), K observations moved ... Reason: <r>" notes against committed raw.

The claim is existential and, when N==0 with reason `no-raw` / `no-field-records`
/ `field-named-but-unstructured`, it is a NEGATIVE claim: nothing in the cited
experiments' raw records this field per value.  That is the most falsifiable
sentence shape in the corpus, so it is checked exhaustively rather than sampled.

Two instruments, same as check_citation_repair2.py:
  named       records with `instr == mnemonic` and `field == field`
  byte_index  records with `instr == mnemonic` and a `byte_index` inside the
              field's db.json byte span (the `__raw_bN` / field:null shape that
              EXP-0164/0189's underscore filter drops -- DEF-0190-1)

Read-only.  Writes analysis/e0189_zero_check.json.
"""
import collections, glob, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
EXPS = os.path.join(ROOT, "experiments")
RX = re.compile(r"EXP-0189 withheld \((\w+)\): (\d+) values dispatched over (\d+) arm\(s\), "
                r"(\d+) observations moved.*?Reason: ([a-z-]+)", re.S)


def spans():
    db = json.load(open(os.path.join(ROOT, "tools/agx-isa/db.json")))
    out = {}
    for i in db["instructions"]:
        for f in i.get("fields", []):
            out["%s.%s" % (i["mnemonic"], f["name"])] = (f["start"], f["width"])
    return out


_scan = {}


def scan_exp(expdir):
    """-> {(instr, field): n}, {(instr, byte_index): n}, per experiment."""
    if expdir in _scan:
        return _scan[expdir]
    byf = collections.Counter()
    byb = collections.Counter()
    vals = collections.defaultdict(set)
    for p in sorted(glob.glob(os.path.join(EXPS, expdir, "raw", "**", "*.jsonl"), recursive=True)):
        for ln in open(p, "rb"):
            try:
                r = json.loads(ln)
            except Exception:
                continue
            ins, fld, bi = r.get("instr"), r.get("field"), r.get("byte_index")
            if isinstance(fld, str):
                byf[(ins, fld)] += 1
                vals[(ins, fld)].add(r.get("value"))
            if bi is not None:
                byb[(ins, bi)] += 1
                vals[(ins, "byte%d" % bi)].add(r.get("value"))
    _scan[expdir] = (byf, byb, vals)
    return _scan[expdir]


def main():
    val = json.load(open(os.path.join(ROOT, "tools/agx-isa/validation.json")))
    SP = spans()
    out, agg = {}, collections.Counter()
    for m, entry in sorted(val["instructions"].items()):
        for f, r in sorted(entry.items()):
            if not isinstance(r, dict):
                continue
            mo = RX.search(r.get("note") or "")
            if not mo:
                continue
            key = "%s.%s" % (m, f)
            claim_n = int(mo.group(2))
            sp = SP.get(key)
            bs = set()
            if sp:
                bs = set(range(sp[0] // 8, (sp[0] + sp[1] - 1) // 8 + 1))
            named = byteo = 0
            nv = set()
            where = []
            for ev in (r.get("evidence") or []):
                for d in sorted(glob.glob(os.path.join(EXPS, ev.split("/")[0] + "*"))):
                    if not os.path.isdir(d):
                        continue
                    dn = os.path.basename(d)
                    byf, byb, vals = scan_exp(dn)
                    n1 = byf.get((m, f), 0)
                    n2 = sum(byb.get((m, b), 0) for b in bs)
                    if n1 or n2:
                        where.append({"exp": dn, "named": n1, "byte_index": n2,
                                      "distinct_values_named": len(vals.get((m, f), ())),
                                      "distinct_values_byte": max([len(vals.get((m, "byte%d" % b), ()))
                                                                   for b in bs] or [0])})
                    named += n1
                    byteo += n2
            verdict = ("SUPPORTED" if (claim_n == 0 and named == 0 and byteo == 0)
                       else ("CONTRADICTED-named" if named else
                             ("CONTRADICTED-byte-indexed" if byteo else "OTHER")))
            if claim_n != 0:
                verdict = "NOT-A-ZERO-CLAIM"
            agg[(mo.group(5), verdict)] += 1
            out[key] = {"label": r.get("label"), "bucket": mo.group(1), "reason": mo.group(5),
                        "claim_values_dispatched": claim_n, "evidence": r.get("evidence"),
                        "span": sp, "raw_named": named, "raw_byte_indexed": byteo,
                        "where": where, "verdict": verdict}
    json.dump(out, open(os.path.join(HERE, "e0189_zero_check.json"), "w"), indent=1, sort_keys=True)
    for k in sorted(agg):
        print(k, agg[k])
    print()
    for k, v in sorted(out.items()):
        if v["verdict"].startswith("CONTRADICTED"):
            print("%-30s %-28s claim=0  raw named=%d byte=%d  %s"
                  % (k, v["reason"], v["raw_named"], v["raw_byte_indexed"], v["where"]))


if __name__ == "__main__":
    main()
