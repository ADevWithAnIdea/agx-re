#!/usr/bin/env python3
"""EXP-0183 -- do the bytes our own GPU EXECUTED now decode?

The anchor_decode_test asserts 255 committed HW anchors. This adds the one population
that test does not carry: EXP-0180's DSTNIB arm, sixteen byte strings that differ only
in byte0's high nibble and that the G17P executed with STATUS OK, writing r[n]. Before
DEF-0180-1 is applied, db.json's `match [[0,8,16]]` pins the whole of byte0, so fifteen
of the sixteen have NO descriptor at all.

Run INSIDE a tree:  cd <tree> && python3 halfdst_decode_check.py
"""
import collections, json, os, sys

sys.path.insert(0, os.getcwd())
import isadb  # noqa: E402

REPO = os.environ.get("AGXRE_REPO", "/Users/user/asahi_re/public/agx-re")
E180 = os.path.join(REPO, "experiments", "EXP-0180-g17p-halfalu-rerecord")

seen, out = set(), []
for run in ("g17p_run02", "g17p_run03"):
    for line in open(os.path.join(E180, "raw", run, "sweep.jsonl")):
        r = json.loads(line)
        if r["arm"] != "DSTNIB" or r["status"] != "OK":
            continue
        h = r["bytes"]
        if h in seen:
            continue
        seen.add(h)
        b = bytes.fromhex(h)
        try:
            rec, ln = isadb.decode_one(b, 0)
            out.append({"bytes": h, "dst_nibble": b[0] >> 4, "ok": True,
                        "mnemonic": rec["mnemonic"], "length": ln,
                        "decoded_dst": rec["fields"].get("dst")})
        except Exception as e:
            out.append({"bytes": h, "dst_nibble": b[0] >> 4, "ok": False,
                        "error": str(e)})
res = {"cases": len(out), "decoded": sum(1 for o in out if o["ok"]),
       "dst_field_matches_byte0_high_nibble":
           sum(1 for o in out if o["ok"] and o.get("decoded_dst") == o["dst_nibble"]),
       "mnemonics": dict(collections.Counter(o.get("mnemonic", "<none>") for o in out)),
       "detail": sorted(out, key=lambda o: o["dst_nibble"])}
print(json.dumps(res))
