#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0198 PART 2 -- settle the 12 `b_alu10_loe` / `b_alu10_lof` rows whose
`note` says "0 values dispatched" beside a `range` saying "256 of 256, DENSE".

EXP-0196 3.5 recorded the contradiction and declined to rule on it, calling it
"a descriptor-identity question this audit is not equipped to settle".  It is a
descriptor-identity question, and it is settleable from committed artifacts.

Five machine checks:
 B1  the 12 rows really do carry both strings.
 B2  no raw record anywhere in experiments/*/raw names instr b_alu10_*.
 B3  EXP-0171 -- the cited evidence -- DOES carry per-key verdicts for these
     fields, and every one of them is keyed to a carrier named `...@ilogic+32`,
     i.e. an ILOGIC anchor.
 B4  db.json's `ilogic` match was RE-SPANNED by EXP-0174/0175 (commit 74f6af25)
     from `[[0,8,11],[17,7,15]]` (byte0 pinned to the whole byte 0x0b, so
     destination r0 only) to `[[0,4,11],[17,7,15]]` (low nibble only).
 B5  the exact anchor bytes EXP-0171 dispatched tokenize as b_alu10_lof/loe
     under the PRE-repair db.json and as ilogic under the CURRENT one.

B4/B5 read the pre-repair db.json out of git (`git show 74f6af25^:...`), which is
this repo's own committed history, not an external source.

Read-only.  Writes analysis/check_b_alu10.json.
"""
import collections, glob, json, os, re, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
EXPS = os.path.join(ROOT, "experiments")
REPAIR_COMMIT = "74f6af25"          # exp(0174,0175)
ANCHORS = ["2b031f01000000000000", "2b031e01000000000000", "2b011e01000000000000"]


def load_db(rev=None):
    if rev is None:
        return json.load(open(os.path.join(ROOT, "tools/agx-isa/db.json")))
    txt = subprocess.check_output(["git", "-C", ROOT, "show",
                                   "%s:tools/agx-isa/db.json" % rev], text=True)
    return json.loads(txt)


def tokenize(db, hexs):
    """Most-specific matching descriptor of the right length, ranked by how many
    bits its `match` constrains -- db.json's own specificity rule."""
    w = int.from_bytes(bytes.fromhex(hexs), "little")
    out = []
    for i in db["instructions"]:
        m = i.get("match")
        if not m or (i.get("length") or 0) != len(hexs) // 2:
            continue
        if all(((w >> s) & ((1 << wd) - 1)) == v for s, wd, v in m):
            out.append((sum(x[1] for x in m), i["mnemonic"]))
    out.sort(reverse=True)
    return out


def main():
    val = json.load(open(os.path.join(ROOT, "tools/agx-isa/validation.json")))
    res = {}

    # ---- B1: the rows -----------------------------------------------------
    rows = {}
    for m, e in sorted(val["instructions"].items()):
        if not m.startswith("b_alu10_lo"):
            continue
        for f, r in sorted(e.items()):
            if not isinstance(r, dict):
                continue
            nt, rg = r.get("note") or "", r.get("range") or ""
            # NB: EXP-0196 3.5 quotes all 12 ranges as "256 of 256"; four are not
            # (src_flag is "2 of 2", src_reg is "128 of 128").  Matching only
            # "256 of 256" finds 8 of the 12.
            if "0 values dispatched" in nt and re.match(r"\s*\d+ of \d+ sub-values, DENSE", rg):
                rows["%s.%s" % (m, f)] = {"label": r.get("label"),
                                          "evidence": r.get("evidence"),
                                          "note": nt, "range": rg}
    res["B1_rows_with_both_strings"] = {"n": len(rows), "keys": sorted(rows),
                                        "example": rows[sorted(rows)[0]] if rows else None}

    # ---- B2: no raw record names the descriptor ---------------------------
    named = collections.Counter()
    for p in glob.glob(os.path.join(EXPS, "*", "raw", "**", "*.jsonl"), recursive=True):
        with open(p, "rb") as fh:
            for ln in fh:
                if b"b_alu10" not in ln:
                    continue
                try:
                    r = json.loads(ln)
                except Exception:
                    continue
                if str(r.get("instr", "")).startswith("b_alu10"):
                    named[(os.path.relpath(p, EXPS), r["instr"])] += 1
    res["B2_raw_records_with_instr_b_alu10"] = {
        "n": sum(named.values()), "where": {str(k): v for k, v in named.items()}}

    # ---- B3: EXP-0171's own per-key verdicts and their carriers -----------
    fv = json.load(open(os.path.join(
        EXPS, "EXP-0171-g17p-ilogic-srca", "analysis", "field_verdicts.json")))["verdicts"]
    keys = sorted(k for k in fv if k.startswith("b_alu10_"))
    carriers = collections.Counter()
    dispatched = {}
    for k in keys:
        for c, v in (fv[k].get("carriers") or {}).items():
            carriers[c] += 1
            dispatched.setdefault(k, {})[c] = {
                "values_dispatched": v.get("values_dispatched"),
                "distinct_bytes": v.get("distinct_bytes"),
                "moved": v.get("moved")}
    res["B3_exp0171_keys"] = {
        "n_keys": len(keys), "keys": keys,
        "carriers": dict(carriers),
        "every_carrier_is_an_ilogic_anchor": all("@ilogic+" in c for c in carriers),
        "per_key_dispatch": dispatched}

    # ---- B4: the ilogic re-span -------------------------------------------
    before, after = load_db(REPAIR_COMMIT + "^"), load_db()
    def desc(db, mn):
        for i in db["instructions"]:
            if i["mnemonic"] == mn:
                return {"match": i.get("match"), "length": i.get("length")}
    res["B4_ilogic_respan"] = {
        "commit": REPAIR_COMMIT,
        "before": {m: desc(before, m) for m in ("ilogic", "b_alu10_loe", "b_alu10_lof")},
        "after": {m: desc(after, m) for m in ("ilogic", "b_alu10_loe", "b_alu10_lof")},
        "ilogic_match_changed": desc(before, "ilogic") != desc(after, "ilogic"),
        "b_alu10_unchanged": (desc(before, "b_alu10_loe") == desc(after, "b_alu10_loe")
                              and desc(before, "b_alu10_lof") == desc(after, "b_alu10_lof"))}

    # ---- B5: what the dispatched anchor tokenizes to, before and after ----
    tok = {}
    for h in ANCHORS:
        tok[h] = {"before": tokenize(before, h), "after": tokenize(after, h)}
    res["B5_anchor_tokenization"] = tok

    # ---- B6: db.json's own auditor note -----------------------------------
    note_for_auditors = None
    for i in after["instructions"]:
        if i["mnemonic"] == "b_alu10_loe":
            s = i.get("semantics") or ""
            mo = re.search(r"NOTE FOR LABEL AUDITORS:.*?(?=⚠|$)", s, re.S)
            note_for_auditors = mo.group(0).strip() if mo else None
    res["B6_db_json_note_for_label_auditors"] = note_for_auditors

    json.dump(res, open(os.path.join(HERE, "check_b_alu10.json"), "w"), indent=1,
              sort_keys=True)
    print("B1 rows with both strings:", res["B1_rows_with_both_strings"]["n"])
    print("B2 raw records with instr=b_alu10_*:",
          res["B2_raw_records_with_instr_b_alu10"]["n"])
    print("B3 EXP-0171 b_alu10 keys:", res["B3_exp0171_keys"]["n_keys"],
          "| every carrier an ilogic anchor:",
          res["B3_exp0171_keys"]["every_carrier_is_an_ilogic_anchor"],
          "| carriers:", list(res["B3_exp0171_keys"]["carriers"]))
    print("B4 ilogic match before:", res["B4_ilogic_respan"]["before"]["ilogic"]["match"],
          "after:", res["B4_ilogic_respan"]["after"]["ilogic"]["match"],
          "| b_alu10 unchanged:", res["B4_ilogic_respan"]["b_alu10_unchanged"])
    for h, v in tok.items():
        print("B5 %s  before=%s  after=%s" % (h, v["before"], v["after"]))
    print("B6:", (note_for_auditors or "")[:300])


if __name__ == "__main__":
    main()
