#!/usr/bin/env python3
"""EXP-0182 -- GENERAL audit of the dst-nibble family-gating defect (DEF-0180-7).

DEF-0180-7: `isadb.instr_length` gates the native-half family on the FULL byte
(`if b0 == 0x10`), while byte0's HIGH NIBBLE is the DESTINATION REGISTER.  The same
function's docstring records that this exact bug was found and fixed for the 0x09
float family.  This script asks the question generally, from `db.json` alone:

  For every descriptor whose OWN `match` says byte0's high nibble is free
  (i.e. it pins `[0,4,v]` and does NOT pin `[0,8,v]`), does `instr_length`
  return the declared length at all sixteen destination nibbles?

A descriptor that decodes at only some nibbles is family-gated by construction:
an emitter can write only those destinations, and a corpus census over the family
under-counts.

Encodings are taken from (a) curated HW anchors committed in experiments' raw/
(see anchors.json) and (b) whatever the own-MSL corpus reaches for the mnemonic.

Usage:  python3 analysis/family_gate_audit.py [--tree DIR]
CLEAN-ROOM: pure analysis over our own db.json, our own corpus, our own raw.
"""
import collections, importlib.util, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
REPO = os.path.abspath(os.path.join(EXP, "..", ".."))
HEXDIR = os.path.join(REPO, "experiments", "EXP-M4-13-full-corpus", "hex")


def load(d):
    d = os.path.abspath(d)
    spec = importlib.util.spec_from_file_location("isadb_%x" % (abs(hash(d)) & 0xffffffff),
                                                  os.path.join(d, "isadb.py"))
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


def corpus_encodings(m):
    """mnemonic -> Counter of the exact byte strings the own-MSL corpus decodes to it."""
    seen = collections.defaultdict(collections.Counter)
    for fn in sorted(os.listdir(HEXDIR)):
        if not fn.endswith(".hex"):
            continue
        buf = bytes.fromhex("".join(open(os.path.join(HEXDIR, fn)).read().split()))
        off = 0
        while off < len(buf):
            try:
                rec, L = m.decode_one(buf, off)
            except Exception:
                break
            if not L:
                break
            seen[rec["mnemonic"]][buf[off:off + L].hex()] += 1
            off += L
    return seen


def probe(m, hexs, declared):
    """Per destination nibble: (length, mnemonic-or-error)."""
    b = bytearray.fromhex(hexs)
    out = {}
    for n in range(16):
        b2 = bytearray(b)
        b2[0] = (n << 4) | (b[0] & 0x0f)
        buf = bytes(b2)
        try:
            L = m.instr_length(buf, 0)
        except Exception as e:
            L = "ERR:%s" % type(e).__name__
        try:
            rec, LL = m.decode_one(buf, 0)
            mn = rec["mnemonic"]
        except Exception as e:
            mn = "<%s>" % type(e).__name__
        out["%x" % n] = {"len": L, "mnemonic": mn, "ok": (L == declared)}
    return out


def main():
    tree = os.path.join(REPO, "tools", "agx-isa")
    if "--tree" in sys.argv:
        tree = sys.argv[sys.argv.index("--tree") + 1]
    m = load(tree)
    anchors = json.load(open(os.path.join(HERE, "anchors.json")))["anchors"]
    by_mn = collections.defaultdict(list)
    for a in anchors:
        by_mn[a["mnemonic"]].append(a["bytes"])
    corp = corpus_encodings(m)

    result = {"_meta": {"tree": os.path.relpath(os.path.abspath(tree), REPO),
                        "question": "does instr_length return the declared length at all 16 "
                                    "destination nibbles, for every descriptor whose own match "
                                    "leaves byte0's high nibble free?"},
              "dst_generalised": {}, "summary": {}}
    n_full = n_part = n_noenc = 0
    for d in m.DB:
        mn, ln, match = d["mnemonic"], d["length"], d.get("match", [])
        lo = [v for (s, w, v) in match if s == 0 and w == 4]
        full = [v for (s, w, v) in match if s == 0 and w == 8]
        if not lo or full:
            continue                       # not dst-generalised over byte0's high nibble
        encs = list(dict.fromkeys(by_mn.get(mn, []) + [h for h, _ in corp.get(mn, collections.Counter()).most_common(3)]))
        encs = [h for h in encs if len(h) == 2 * ln]
        if not encs:
            n_noenc += 1
            result["dst_generalised"][mn] = {"declared_length": ln, "status": "NO-ENCODING-AVAILABLE"}
            continue
        rows = {h: probe(m, h, ln) for h in encs}
        good = {h: sum(1 for v in r.values() if v["ok"]) for h, r in rows.items()}
        best = max(good.values())
        status = "ALL-16" if best == 16 else ("PARTIAL-%d/16" % best)
        if best == 16:
            n_full += 1
        else:
            n_part += 1
        result["dst_generalised"][mn] = {
            "declared_length": ln, "status": status,
            "nibbles_ok_by_encoding": good,
            "per_nibble": {h: {k: (v["len"], v["mnemonic"]) for k, v in r.items()} for h, r in rows.items()},
        }
    result["summary"] = {"dst_generalised_descriptors": n_full + n_part + n_noenc,
                         "decode_at_all_16_nibbles": n_full,
                         "family_gated_partial": n_part,
                         "no_encoding_available": n_noenc,
                         "partial_list": sorted(k for k, v in result["dst_generalised"].items()
                                                if v["status"].startswith("PARTIAL"))}
    json.dump(result, sys.stdout, indent=1, sort_keys=True)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
