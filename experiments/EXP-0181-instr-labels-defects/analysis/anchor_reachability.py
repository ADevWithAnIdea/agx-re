#!/usr/bin/env python3
"""EXP-0181 -- can the committed tokenizer even REACH the HW-validated anchor?

Five of the thirty weak descriptors were dispatched on hardware at an encoding the
committed db.json + isadb.py length rule does NOT decode.  For each, this walks the
descriptor's destination nibble (or the byte the length rule keys on) and reports which
variants tokenize.  A descriptor whose HW anchor is unreachable is decode-incomplete;
that is a caveat on the DESCRIPTOR, not a doubt about the hardware observation, and the
two are kept apart in the label recommendation.

Usage:  python3 analysis/anchor_reachability.py
CLEAN-ROOM: pure analysis over our own db.json and our own recorded anchors.
"""
import os, sys, json

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, "tools", "agx-isa"))
import isadb  # noqa: E402

# (mnemonic, HW anchor as dispatched, source experiment)
ANCHORS = [
    ("bf_add_dst",   "21001c001100c081",     "EXP-0156 bf_add.metal +32"),
    ("bf_fma_dst",   "21001e0086041000c081", "EXP-0156 bf_fma.metal"),
    ("hminmax",      "22001c0010c0",         "EXP-0156 h_max.metal +32"),
    ("cvt_bf16",     "0101148105024000",     "EXP-0162 c_f2bf"),
    ("cvt_f2h_dst",  "c10114810402",         "EXP-0162 cvt_f2h_dst arm"),
    ("cvt_f2h",      "110114810402",         "EXP-0144 (the byte0==0x11 sibling)"),
]


def dec(h):
    try:
        r = isadb.decode_one(bytes.fromhex(h), 0)
    except Exception as e:
        return "ERR: %s" % e
    if isinstance(r, tuple):
        rec, L = r[0], r[1]
    else:
        rec, L = r, None
    return "%s (len %s)" % ((rec or {}).get("mnemonic"), L)


def corpus_forms(wanted):
    """Which encodings of these mnemonics does the own-MSL corpus actually reach?
    Reported alongside the anchors so the finding cannot be read as "the descriptor
    never decodes" -- several of them decode fine at the encodings the M4 compiler
    emitted, and only the HW-validated anchor is out of the length rule's reach."""
    import collections
    hexdir = os.path.join(ROOT, "experiments", "EXP-M4-13-full-corpus", "hex")
    seen = collections.defaultdict(collections.Counter)
    for fn in sorted(os.listdir(hexdir)):
        if not fn.endswith(".hex"):
            continue
        buf = bytes.fromhex("".join(open(os.path.join(hexdir, fn)).read().split()))
        off = 0
        while off < len(buf):
            try:
                rec, L = isadb.decode_one(buf, off)
            except Exception:
                break
            if not L:
                break
            if rec["mnemonic"] in wanted:
                seen[rec["mnemonic"]][buf[off:off + L].hex()] += 1
            off += L
    return {m: [h for h, _ in c.most_common(6)] for m, c in seen.items()}


def main():
    out = {"_meta": {
        "question": "does the committed db.json + isadb.py length rule decode the exact "
                    "encoding each experiment DISPATCHED on hardware?",
        "why_it_matters": "a descriptor can have HW-confirmed semantics while the committed "
                          "tokenizer cannot reach the anchor that proved them. That is a "
                          "DECODE gap (isadb.py's length rule, another owner) and it is a "
                          "caveat on the descriptor, not a doubt about the observation.",
        "probe": "the anchor as dispatched, plus its 16 destination-nibble variants "
                 "(byte+1 and byte+2 held at the anchor's values), plus the encodings the "
                 "own-MSL corpus actually reaches for the same mnemonic."}}
    reach = corpus_forms({m for m, _, _ in ANCHORS})
    for m, h, src in ANCHORS:
        b = bytearray.fromhex(h)
        row = {"anchor": h, "source": src, "anchor_decodes_to": dec(h),
               "per_dst_nibble_holding_byte1_byte2": {},
               "corpus_reachable_encodings": reach.get(m, [])}
        for n in range(16):
            b2 = bytearray(b)
            b2[0] = (n << 4) | (b[0] & 0x0f)
            row["per_dst_nibble_holding_byte1_byte2"]["0x%x" % n] = dec(bytes(b2).hex())
        out[m] = row
    json.dump(out, sys.stdout, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
