#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0196 -- test both halves of every "EXP-0189 citation repair" note.

Each such note asserts two things:
  (a) POSITIVE: "the records supporting this row live in <DIRS>";
  (b) NEGATIVE: "the original citation <DIRS> has no per-value records for it".

(b) is the falsifiable half and the one nobody has re-run.  Two independent
instruments are applied to each named directory:

  I1  the per-value raw index (work/raw_field_index.json.gz): does any
      raw/**/*.jsonl record carry `"field": "<field>"` (or the field name in
      `group`/`arm`, which is how EXP-0138..0140 key their sweeps)?
  I2  a plain grep of the whole raw/ tree for the quoted field name, which also
      sees the pre-jsonl `.json` raw schemas that I1 cannot parse.

I1 disagreeing with I2 is itself reportable: it means "no per-value record"
is true only of the jsonl schema.

Read-only.  Writes analysis/citation_repair_check.json.
"""
import glob, gzip, json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
EXPS = os.path.join(ROOT, "experiments")
IDX = json.load(gzip.open(os.path.join(HERE, "..", "work", "raw_field_index.json.gz"), "rt"))

RX = re.compile(r"citation repair: the records supporting this row live in (.+?); "
                r"the original citation (.+?) has no per-value records for it")


def dirs_for(slug):
    return [os.path.basename(d) for d in sorted(glob.glob(os.path.join(EXPS, slug.split("/")[0] + "*")))
            if os.path.isdir(d)]


def i1(expdir, mnem, fld):
    e = IDX.get(expdir)
    if not e:
        return {"indexed": False, "field": 0, "group": 0, "arm": 0}
    def cnt(k, want):
        c = e.get(k, {})
        return sum(v for kk, v in c.items() if kk == want or kk.endswith("." + want)
                   or kk.startswith(want + "@") or kk == "%s.%s" % (mnem, want))
    return {"indexed": True, "field": cnt("field", fld), "group": cnt("group", fld),
            "arm": cnt("arm", fld)}


def i2(expdir, fld):
    raw = os.path.join(EXPS, expdir, "raw")
    if not os.path.isdir(raw):
        return {"raw_dir": False, "files": 0}
    try:
        r = subprocess.run(["grep", "-rlI", '"%s"' % fld, raw],
                           capture_output=True, text=True, timeout=300)
        return {"raw_dir": True, "files": len([x for x in r.stdout.splitlines() if x])}
    except Exception as ex:
        return {"raw_dir": True, "files": -1, "error": str(ex)}


def main():
    val = json.load(open(os.path.join(ROOT, "tools/agx-isa/validation.json")))
    out = {}
    for m, entry in sorted(val["instructions"].items()):
        for f, r in sorted(entry.items()):
            if not isinstance(r, dict):
                continue
            nt = r.get("note") or ""
            mo = RX.search(nt)
            if not mo:
                continue
            key = "%s.%s" % (m, f)
            live = [x.strip() for x in mo.group(1).split(",")]
            orig = [x.strip() for x in mo.group(2).split(",")]
            rec = {"label": r.get("label"), "evidence": r.get("evidence"),
                   "claim_live_in": live, "claim_original_has_none": orig,
                   "live_in": {}, "original": {}}
            for slug in live:
                for d in dirs_for(slug):
                    rec["live_in"][d] = {"I1": i1(d, m, f), "I2": i2(d, f)}
            for slug in orig:
                for d in dirs_for(slug):
                    rec["original"][d] = {"I1": i1(d, m, f), "I2": i2(d, f)}
            pos_ok = any(sum(v["I1"][k] for k in ("field", "group", "arm")) > 0
                         for v in rec["live_in"].values())
            neg_ok = all(sum(v["I1"][k] for k in ("field", "group", "arm")) == 0
                         for v in rec["original"].values())
            neg_ok_i2 = all(v["I2"]["files"] == 0 for v in rec["original"].values())
            rec["positive_half"] = "SUPPORTED" if pos_ok else "NOT-FOUND"
            rec["negative_half_jsonl"] = "SUPPORTED" if neg_ok else "CONTRADICTED"
            rec["negative_half_anygrep"] = "SUPPORTED" if neg_ok_i2 else "MENTIONED-IN-RAW"
            out[key] = rec
    json.dump(out, open(os.path.join(HERE, "citation_repair_check.json"), "w"),
              indent=1, sort_keys=True)
    import collections
    print(collections.Counter((v["positive_half"], v["negative_half_jsonl"],
                               v["negative_half_anygrep"]) for v in out.values()))
    for k, v in sorted(out.items()):
        print("%-34s pos=%-9s neg_jsonl=%-12s neg_grep=%s"
              % (k, v["positive_half"], v["negative_half_jsonl"], v["negative_half_anygrep"]))


if __name__ == "__main__":
    main()
