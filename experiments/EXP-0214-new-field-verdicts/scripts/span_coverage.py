#!/usr/bin/env python3
"""EXP-0214: re-derive coverage of a NEW (post-EXP-0212) field span from the
committed raw of the experiment that discovered it.

The question this answers is NOT "did the parent field get swept?" -- it is
"did the bits [start, start+width) of the ACTUAL DISPATCHED instruction bytes
take on distinct values, and how many, on how many carriers, in how many runs?"

Reads sweep.jsonl records with an actual-byte ledger (`bytes` hex) and reports
exact numerators/denominators per RE_EXPERIMENT_PROCESS_CORRECTIONS section 5.
"""
import json, os, sys, collections, argparse


def bits(hexstr, start, width):
    """Little-endian bit extraction from an instruction byte string."""
    if not hexstr:
        return None
    try:
        b = bytes.fromhex(hexstr)
    except Exception:
        return None
    if (start + width + 7) // 8 > len(b):
        return None
    v = int.from_bytes(b, "little")
    return (v >> start) & ((1 << width) - 1)


def load(paths, instr=None):
    for p in paths:
        run = os.path.basename(os.path.dirname(p))
        with open(p) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                if instr and r.get("instr") != instr:
                    continue
                r["_run"] = run
                yield r


def cover(records, start, width, byte_key="bytes"):
    out = {
        "records_seen": 0, "records_with_bytes": 0, "records_span_decodable": 0,
        "span_values": collections.Counter(),
        "distinct_actual_encodings": set(),
        "per_arm": collections.defaultdict(lambda: {
            "n": 0, "span_values": set(), "actual_enc": set(), "runs": set()}),
        "runs": set(),
        "by_field": collections.Counter(),
    }
    for r in records:
        out["records_seen"] += 1
        hx = r.get(byte_key)
        if not hx:
            continue
        out["records_with_bytes"] += 1
        v = bits(hx, start, width)
        if v is None:
            continue
        out["records_span_decodable"] += 1
        out["span_values"][v] += 1
        out["distinct_actual_encodings"].add(hx)
        a = out["per_arm"][r.get("arm")]
        a["n"] += 1
        a["span_values"].add(v)
        a["actual_enc"].add(hx)
        a["runs"].add(r["_run"])
        out["runs"].add(r["_run"])
        out["by_field"][(r.get("field"), r.get("byte_index"))] += 1
    return out


def render(out, start, width):
    d = {
        "start": start, "width": width,
        "encodable_values": 1 << width,
        "records_seen": out["records_seen"],
        "records_with_actual_bytes": out["records_with_bytes"],
        "records_span_decodable": out["records_span_decodable"],
        "distinct_span_values": len(out["span_values"]),
        "distinct_actual_encodings": len(out["distinct_actual_encodings"]),
        "runs": sorted(out["runs"]),
        "span_value_histogram": dict(sorted(out["span_values"].items())),
        "per_arm": {k: {"n": v["n"],
                        "distinct_span_values": len(v["span_values"]),
                        "span_values": sorted(v["span_values"]),
                        "distinct_actual_encodings": len(v["actual_enc"]),
                        "runs": sorted(v["runs"])}
                    for k, v in sorted(out["per_arm"].items(), key=lambda x: str(x[0]))},
        "contributing_sweep_fields": {("%s@byte%s" % (k[0], k[1])): n
                                      for k, n in sorted(out["by_field"].items(),
                                                         key=lambda x: str(x[0]))},
    }
    return d


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, required=True)
    ap.add_argument("--width", type=int, required=True)
    ap.add_argument("--instr")
    ap.add_argument("--byte-key", default="bytes")
    ap.add_argument("paths", nargs="+")
    a = ap.parse_args()
    o = cover(load(a.paths, a.instr), a.start, a.width, a.byte_key)
    print(json.dumps(render(o, a.start, a.width), indent=1))
