# EXP-0195: byte-for-byte copy of EXP-0194/analysis/scan_raw.py.  The ONLY change is
# that OUT reads $E0195_INDEX_OUT, so regenerating the index writes nothing into EXP-0194.
#!/usr/bin/env python3
"""EXP-0194 step 1: index every per-case raw record in experiments/**/raw/**.jsonl.

Pure desk analysis over our own committed artifacts. No device, no Apple binaries.

For each (experiment, file, instr, field, carrier) we aggregate:
  n records, distinct field values, distinct `bytes`, distinct observed payloads
  (canonicalised + hashed), distinct oracle payloads, outcome histogram,
  match histogram, and the flags that FIELD-SWEEP-PROTOCOL 3/5 say disqualify.
Written to analysis/raw_index.jsonl (one row per group).
"""
import hashlib, json, os, sys, collections

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
OUT = os.environ["E0195_INDEX_OUT"]  # EXP-0195: was os.path.join(HERE, "raw_index.jsonl")

def canon(o):
    return hashlib.sha256(json.dumps(o, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]

def main():
    files = []
    for dp, dn, fn in os.walk(os.path.join(ROOT, "experiments")):
        if os.sep + "raw" + os.sep not in dp + os.sep:
            continue
        for f in fn:
            if f.endswith(".jsonl"):
                files.append(os.path.join(dp, f))
    files.sort()
    groups = {}
    nlines = nparsed = 0
    for path in files:
        rel = os.path.relpath(path, ROOT)
        exp = rel.split(os.sep)[1]
        with open(path, "r", errors="replace") as fh:
            for line in fh:
                nlines += 1
                if '"field"' not in line:
                    continue
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                if not isinstance(r, dict):
                    continue
                fld = r.get("field")
                ins = r.get("instr") or r.get("instruction") or r.get("mnemonic")
                if fld is None or ins is None:
                    continue
                nparsed += 1
                key = (exp, rel, str(ins), str(fld), str(r.get("carrier") or r.get("carrier_id") or ""))
                g = groups.get(key)
                if g is None:
                    g = groups[key] = dict(
                        exp=exp, file=rel, instr=str(ins), field=str(fld),
                        carrier=str(r.get("carrier") or r.get("carrier_id") or ""),
                        n=0, values=set(), bytes=set(), obs=set(), orc=set(),
                        outcomes=collections.Counter(), match=collections.Counter(),
                        invalid=0, victim=0, sentinel_bad=0, arm=set(),
                        fstart=set(), fwidth=set(), byteidx=set(), nonok_bytes=set(),
                        ok_obs=set(), ok_values=set(), matched_values=set())
                g["n"] += 1
                v = r.get("value")
                if v is not None:
                    g["values"].add(json.dumps(v, sort_keys=True))
                b = r.get("bytes")
                if isinstance(b, str):
                    g["bytes"].add(b)
                if "observed" in r:
                    g["obs"].add(canon(r["observed"]))
                if "oracle" in r:
                    g["orc"].add(canon(r["oracle"]))
                oc = r.get("outcome")
                g["outcomes"][str(oc)] += 1
                g["match"][str(r.get("match"))] += 1
                if r.get("invalid_run"):
                    g["invalid"] += 1
                if r.get("victim"):
                    g["victim"] += 1
                if r.get("sentinel_bad"):
                    g["sentinel_bad"] += 1
                if r.get("arm"):
                    g["arm"].add(str(r["arm"]))
                for k, gk in (("fstart", "fstart"), ("fwidth", "fwidth"), ("byte_index", "byteidx")):
                    if r.get(k) is not None:
                        g[gk].add(r[k])
                if oc == "ok":
                    if "observed" in r:
                        g["ok_obs"].add(canon(r["observed"]))
                    if v is not None:
                        g["ok_values"].add(json.dumps(v, sort_keys=True))
                if r.get("match") is True and v is not None:
                    g["matched_values"].add(json.dumps(v, sort_keys=True))
                else:
                    if oc not in ("ok",) and isinstance(b, str):
                        g["nonok_bytes"].add(b)
    with open(OUT, "w") as out:
        for key, g in sorted(groups.items()):
            row = dict(g)
            for k in ("values", "bytes", "obs", "orc", "arm", "fstart", "fwidth",
                      "byteidx", "nonok_bytes", "ok_obs", "ok_values", "matched_values"):
                row["n_" + k] = len(g[k])
            for k in ("fstart", "fwidth", "byteidx", "arm"):
                row[k] = sorted(g[k], key=str)[:6]
            for k in ("values", "bytes", "obs", "orc", "nonok_bytes", "ok_obs", "ok_values", "matched_values"):
                row.pop(k)
            row["outcomes"] = dict(g["outcomes"])
            row["match"] = dict(g["match"])
            out.write(json.dumps(row) + "\n")
    sys.stderr.write("files=%d lines=%d field_records=%d groups=%d\n"
                     % (len(files), nlines, nparsed, len(groups)))

main()
