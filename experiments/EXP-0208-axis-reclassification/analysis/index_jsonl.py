#!/usr/bin/env python3
"""EXP-0208 step 1 -- index EVERY per-case record in experiments/**/raw/**/*.jsonl.

Deliberately a SUPERSET of EXP-0189/collect_raw.py and EXP-0194/scan_raw.py. The
keyings this corpus actually uses, all of which some earlier indexer dropped:

  K1  instr + field                     (the EXP-0138+ sweep era; the only one 0189 saw)
  K2  instr + field == null             (EXP-0171: 71,262 byte-level sweeps; byte_index kept)
  K3  instr + field == "mnem.field"     (EXP-0174 n3mov: DOTTED field names -- a lookup by
                                         bare field name misses every one of them)
  K4  instr + field beginning "_" / "__"(the falsifier / detection-power / ladder controls,
                                         explicitly dropped by 0189's `not startswith("_")`)
  K5  mnem only, no field               (EXP-0148 token resync: 2.9M framing records)

Pure desk analysis over our own committed artefacts. No device. No Apple binaries.
"""
import hashlib, json, os, sys, collections

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "raw_index_jsonl.jsonl")
FILEOUT = os.path.join(HERE, "raw_file_census.jsonl")

NULLF = "\x00NULL"
NOF = "\x00NOFIELD"

def canon(o):
    return hashlib.sha256(json.dumps(o, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:12]

INSTR_KEYS = ("instr", "instruction", "mnemonic", "mnem", "op", "opcode_name", "instr_name")
FIELD_KEYS = ("field", "field_name", "fld")
VAL_KEYS = ("value", "val", "requested", "requested_value")
BYTE_KEYS = ("bytes", "actual_bytes", "instr_bytes", "encoded", "hex")
REQ_KEYS = ("requested_bytes", "req_bytes", "bytes_requested", "anchor_bytes")
FIDX_KEYS = ("byte_index", "byteidx", "byte_off", "byte", "b_idx", "byte_no")

def main():
    files = []
    for dp, dn, fn in os.walk(os.path.join(ROOT, "experiments")):
        if os.sep + "raw" + os.sep not in dp + os.sep and not dp.endswith(os.sep + "raw"):
            continue
        for f in fn:
            if f.endswith(".jsonl"):
                files.append(os.path.join(dp, f))
    files.sort()
    groups = {}
    fcensus = []
    for path in files:
        rel = os.path.relpath(path, ROOT)
        exp = rel.split(os.sep)[1]
        c = collections.Counter()
        with open(path, "r", errors="replace") as fh:
            for line in fh:
                c["lines"] += 1
                line = line.strip()
                if not line or line[0] != "{":
                    continue
                try:
                    r = json.loads(line)
                except Exception:
                    c["unparsed"] += 1
                    continue
                if not isinstance(r, dict):
                    continue
                c["objs"] += 1
                ins = None
                for k in INSTR_KEYS:
                    if isinstance(r.get(k), str) and r[k]:
                        ins = r[k]; break
                fld = None; has_fk = False
                for k in FIELD_KEYS:
                    if k in r:
                        has_fk = True
                        if isinstance(r[k], str) and r[k]:
                            fld = r[k]
                        break
                keying = None
                if fld is not None and "." in fld:            # K3 dotted
                    pre, post = fld.split(".", 1)
                    if ins is None:
                        ins = pre
                    fld = post
                    keying = "K3_dotted"
                if ins: c["with_instr"] += 1
                if fld: c["with_field"] += 1
                if ins and fld: c["with_both"] += 1
                if has_fk and fld is None: c["null_field"] += 1
                if fld and fld.startswith("_"): c["underscore_field"] += 1
                if ins is None and fld is None:
                    c["unkeyed"] += 1
                    continue
                if keying is None:
                    if fld is None:
                        keying = "K2_nullfield" if has_fk else "K5_instr_only"
                    elif fld.startswith("_"):
                        keying = "K4_underscore"
                    else:
                        keying = "K1_instr_field"
                fkey = fld if fld is not None else (NULLF if has_fk else NOF)
                carrier = r.get("carrier") or r.get("carrier_id") or r.get("group") or ""
                arm = r.get("arm") or r.get("run_id") or ""
                key = (exp, rel, str(ins), fkey, str(carrier), str(arm))
                g = groups.get(key)
                if g is None:
                    g = groups[key] = dict(
                        exp=exp, file=rel, instr=str(ins), field=fkey, keying=keying,
                        carrier=str(carrier), arm=str(arm), n=0,
                        values=set(), abytes=set(), rbytes=set(), obs=set(), orc=set(),
                        okobs=set(), okvals=set(), faultvals=set(), hangvals=set(),
                        fidx=set(), fstart=set(), fwidth=set(), mutidx=set(),
                        outcomes=collections.Counter(), match=collections.Counter(),
                        invalid=0, victim=0, sentinel_bad=0, semchecked=0,
                        falsifier=0, moved_true=0, keys=set())
                g["n"] += 1
                g["keys"] |= set(r.keys())
                v = None
                for k in VAL_KEYS:
                    if k in r and not isinstance(r[k], (dict, list)):
                        v = r[k]; break
                if v is not None:
                    g["values"].add(json.dumps(v, sort_keys=True))
                for k in BYTE_KEYS:
                    if isinstance(r.get(k), str):
                        g["abytes"].add(r[k]); break
                for k in REQ_KEYS:
                    if isinstance(r.get(k), str):
                        g["rbytes"].add(r[k]); break
                if "observed" in r:
                    g["obs"].add(canon(r["observed"]))
                elif "out" in r:
                    g["obs"].add(canon(r["out"]))
                if "oracle" in r:
                    g["orc"].add(canon(r["oracle"]))
                    g["semchecked"] += 1
                if "match" in r:
                    g["match"][str(r.get("match"))] += 1
                oc = str(r.get("outcome") or r.get("status") or r.get("result") or "?")
                g["outcomes"][oc] += 1
                lo = oc.lower()
                if lo in ("ok", "pass"):
                    if "observed" in r: g["okobs"].add(canon(r["observed"]))
                    elif "out" in r: g["okobs"].add(canon(r["out"]))
                    if v is not None: g["okvals"].add(json.dumps(v, sort_keys=True))
                if "fault" in lo or "error" in lo:
                    if v is not None: g["faultvals"].add(json.dumps(v, sort_keys=True))
                if "hang" in lo:
                    if v is not None: g["hangvals"].add(json.dumps(v, sort_keys=True))
                if r.get("invalid_run"): g["invalid"] += 1
                if r.get("victim"): g["victim"] += 1
                if r.get("sentinel_bad"): g["sentinel_bad"] += 1
                if r.get("falsifier"): g["falsifier"] += 1
                if r.get("moved"): g["moved_true"] += 1
                for k in FIDX_KEYS:
                    if isinstance(r.get(k), int):
                        g["fidx"].add(r[k]); break
                m = r.get("mut")
                if isinstance(m, list):
                    for e in m:
                        if isinstance(e, list) and len(e) >= 1 and isinstance(e[0], int):
                            g["mutidx"].add(e[0])
                if isinstance(r.get("start"), int): g["fstart"].add(r["start"])
                if isinstance(r.get("fstart"), int): g["fstart"].add(r["fstart"])
                if isinstance(r.get("width"), int): g["fwidth"].add(r["width"])
                if isinstance(r.get("fwidth"), int): g["fwidth"].add(r["fwidth"])
        row = dict(file=rel, exp=exp)
        row.update(c)
        fcensus.append(row)
    with open(OUT, "w") as out:
        for key, g in sorted(groups.items()):
            row = dict(g)
            for k in ("values", "abytes", "rbytes", "obs", "orc", "okobs", "okvals",
                      "faultvals", "hangvals", "fidx", "fstart", "fwidth", "mutidx", "keys"):
                row["n_" + k] = len(g[k])
            row["fidx"] = sorted(g["fidx"])[:64]
            row["mutidx"] = sorted(g["mutidx"])[:64]
            row["fstart"] = sorted(g["fstart"])[:12]
            row["fwidth"] = sorted(g["fwidth"])[:12]
            row["keys"] = sorted(g["keys"])
            # UNION-ABLE SETS -- summing per-group counts across runs double-counts and
            # would report "2 distinct payloads" for a field that is inert in both runs.
            row["obs"] = sorted(g["obs"])[:400]
            row["okobs"] = sorted(g["okobs"])[:400]
            row["orc"] = sorted(g["orc"])[:400]
            row["values"] = sorted(g["values"])[:600]
            row["okvals"] = sorted(g["okvals"])[:600]
            row["faultvals"] = sorted(g["faultvals"])[:600]
            row["hangvals"] = sorted(g["hangvals"])[:600]
            row["abytes_h"] = sorted(hashlib.sha256(b.encode()).hexdigest()[:8] for b in g["abytes"])[:600]
            for k in ("abytes", "rbytes"):
                row.pop(k)
            row["outcomes"] = dict(g["outcomes"])
            row["match"] = dict(g["match"])
            out.write(json.dumps(row) + "\n")
    with open(FILEOUT, "w") as out:
        for r in fcensus:
            out.write(json.dumps(r) + "\n")
    sys.stderr.write("files=%d groups=%d\n" % (len(files), len(groups)))

main()
