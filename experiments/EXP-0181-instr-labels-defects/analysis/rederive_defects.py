#!/usr/bin/env python3
"""EXP-0181 Task 2 -- re-derive the four EXP-0168 descriptor defects from committed raw.

EXP-0165 re-derived nine defects and found one half wrong and one whose severity claim
was wrong; EXP-0175 re-derived five and refused a propagation that would have created a
new defect.  So none of EXP-0168's four is applied before this script has, independently:

  1. recomputed the free / pinned bit split from db.json ALONE (not from EXP-0168's table);
  2. gone back to every committed raw record naming the field and extracted the DISPATCHED
     values, their outcomes, and -- crucially -- which of them are LEGAL under the
     descriptor's own match;
  3. checked whether the corpus ever fires the descriptor with a value outside the
     narrowed span, which would refute the narrowing.

Usage:  python3 analysis/rederive_defects.py
Writes: analysis/defects_rederived.json
CLEAN-ROOM: pure re-analysis of our own committed raw + our own db.json + our own corpus.
"""
import json, os, sys, glob, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, "tools", "agx-isa"))
import isadb  # noqa: E402

EXPROOT = os.path.join(ROOT, "experiments")
HEXDIR = os.path.join(EXPROOT, "EXP-M4-13-full-corpus", "hex")
DB = json.load(open(os.path.join(ROOT, "tools", "agx-isa", "db.json")))
DESC = {i["mnemonic"]: i for i in DB["instructions"]}

TARGETS = [("iter_at", "grp"), ("pixel_order", "scope"),
           ("reg_move_cb", "form"), ("shift_amt_move", "kind")]


def bit_split(m, fname):
    d = DESC[m]
    covered = 0
    for (s, w, _v) in d.get("match", []):
        covered |= ((1 << w) - 1) << s
    pinned_val = 0
    for (s, w, v) in d.get("match", []):
        pinned_val |= (v & ((1 << w) - 1)) << s
    f = [x for x in d["fields"] if x["name"] == fname][0]
    span = ((1 << f["width"]) - 1) << f["start"]
    free_mask = span & ~covered
    pin_mask = span & covered
    free_bits = [b for b in range(f["start"], f["start"] + f["width"])
                 if free_mask >> b & 1]
    pin_bits = [b for b in range(f["start"], f["start"] + f["width"])
                if pin_mask >> b & 1]
    contiguous = bool(free_bits) and free_bits == list(range(free_bits[0], free_bits[-1] + 1))
    legal = []
    for v in range(1 << f["width"]):
        word = v << f["start"]
        if (word & pin_mask) == (pinned_val & pin_mask):
            legal.append(v)
    return {"mnemonic": m, "field": fname, "start": f["start"], "width": f["width"],
            "type": f.get("type"), "enum": f.get("enum"),
            "length_bytes": d["length"], "match": d["match"],
            "free_bits_abs": free_bits, "pinned_bits_abs": pin_bits,
            "n_free": len(free_bits), "n_legal_values": len(legal),
            "legal_values": legal if len(legal) <= 32 else legal[:32] + ["..."],
            "free_bits_contiguous": contiguous,
            "pinned_value_in_span": (pinned_val & pin_mask) >> f["start"],
            "pin_mask_in_span": pin_mask >> f["start"]}


def raw_values(m, fname):
    """Every committed raw record naming (m, fname): value, outcome, byte string."""
    per = collections.defaultdict(lambda: {"values": collections.Counter(),
                                           "outcomes": collections.Counter(),
                                           "value_outcome": collections.Counter(),
                                           "bytes": collections.Counter()})
    for path in glob.iglob(os.path.join(EXPROOT, "EXP-*", "raw", "**", "*.jsonl"),
                           recursive=True):
        exp = os.path.relpath(path, ROOT).split(os.sep)[1]
        run = os.path.relpath(path, ROOT).split(os.sep)[3]
        with open(path, errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line or line[0] != "{":
                    continue
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                if (r.get("instr") or r.get("mnemonic")) != m:
                    continue
                fld = str(r.get("field") or "")
                if fname not in fld:
                    continue
                a = per["%s/%s" % (exp, run)]
                v = r.get("value")
                if isinstance(v, int):
                    a["values"][v] += 1
                    a["value_outcome"][(v, r.get("outcome"))] += 1
                a["outcomes"][r.get("outcome")] += 1
                b = r.get("bytes")
                if isinstance(b, str):
                    a["bytes"][b] += 1
    out = {}
    for k, a in sorted(per.items()):
        vals = sorted(a["values"])
        out[k] = {"n_records": sum(a["values"].values()) or sum(a["outcomes"].values()),
                  "distinct_values": len(vals),
                  "values": vals if len(vals) <= 40 else [vals[0], "...", vals[-1]],
                  "outcomes": dict(a["outcomes"]),
                  "distinct_byte_strings": len(a["bytes"])}
    return out


def corpus_values(m, fname):
    """What value does the field actually take in every corpus firing of the descriptor?"""
    ctr = collections.Counter()
    byte0 = collections.Counter()
    for fn in sorted(os.listdir(HEXDIR)):
        if not fn.endswith(".hex"):
            continue
        buf = bytes.fromhex("".join(open(os.path.join(HEXDIR, fn)).read().split()))
        off, n = 0, len(buf)
        while off < n:
            try:
                rec, L = isadb.decode_one(buf, off)
            except Exception:
                break
            if not L:
                break
            if rec["mnemonic"] == m:
                ctr[rec["fields"].get(fname)] += 1
                byte0[buf[off]] += 1
            off += L
    return {"firings": sum(ctr.values()), "field_values": dict(sorted(ctr.items(), key=lambda kv: -kv[1])),
            "byte0_values": {hex(k): v for k, v in sorted(byte0.items())}}


def main():
    out = {"_meta": {
        "experiment": "EXP-0181",
        "source_claim": "EXP-0168 RESULTS.md section 7 (four fields declared over match-pinned bits)",
        "method": "independent recomputation from db.json + committed raw + the own-MSL corpus",
        "db_sha256": __import__("hashlib").sha256(
            open(os.path.join(ROOT, "tools", "agx-isa", "db.json"), "rb").read()).hexdigest()}}
    for m, f in TARGETS:
        r = bit_split(m, f)
        r["raw_sweeps"] = raw_values(m, f)
        r["corpus"] = corpus_values(m, f)
        out["%s.%s" % (m, f)] = r
    json.dump(out, sys.stdout, indent=1, default=str)
    return 0


if __name__ == "__main__":
    sys.exit(main())
