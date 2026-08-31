#!/usr/bin/env python3
"""EXP-0219 part-A scoring: the four `imad` dispatches EXP-0218 named.

Reads this experiment's OWN committed raw only.  The single fitted parameter is
declared in CAPTURE_CONTRACT.json and re-stated here:

    FILE[j] := the addend recovered from arm `cross` (carrier dag) / `cross32`
               (carrier const), byte+9 = 0x2e, byte+8 = 0xd0, K = j,
               SEED SET 1, run01 ONLY.

Every other number below is HELD OUT against it.

Nothing here decodes an instruction by mnemonic or by the DB's field names: each
byte is read by POSITION out of the record's own ACTUAL bytes (Gate A), exactly
as EXP-0218 did, so a stale descriptor cannot move a count.
"""
import json
import sys
import collections
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
M32 = 0xFFFFFFFF


def load(run):
    return [json.loads(l) for l in (EXP / "raw" / run / "sweep.jsonl").open()]


def actual(r):
    return bytes.fromhex(r["ledger"]["actual_bytes"])


def fit_file(recs, arm):
    F = {}
    for r in recs:
        b = actual(r)
        if (r["arm"] == arm and b[9] == 0x2e and b[8] == 0xd0 and r["sset"] == 1
                and r["outcome"] in ("ok", "silent_zero", "wrong_value")
                and r["ledger"]["gate_a_ok"]):
            F[(b[7] >> 3) & 0x1F] = r["recovered_A"]
    return F


def fget(F, j):
    return F.get(j, 0)


def A_of(b7, b8, b9, F, selector, index):
    K = (b7 >> 3) & 0x1F
    sel = {"bit3": (b9 >> 3) & 1, "bit1": (b9 >> 1) & 1,
           "and": ((b9 >> 3) & 1) & ((b9 >> 1) & 1),
           "or": ((b9 >> 3) & 1) | ((b9 >> 1) & 1)}[selector]
    if sel == 0:
        return (((b8 & 7) << 5) | K) & 0xFF                 # M_IMM8
    if index == "5":
        if (b8 & 7) != 0:
            return 0
        i = K
    else:
        i = K | ((b8 & 7) << 5)
    if b9 & 1:                                              # 32-bit word
        return (fget(F, i) | (fget(F, i + 1) << 16)) & M32
    return fget(F, i)


def score(recs, F, selector, index, pred=lambda r: True):
    hit = tot = 0
    miss = []
    for r in recs:
        if not r["ledger"]["gate_a_ok"] or r["outcome"] in ("hang", "fault",
                                                            "measurement_failure",
                                                            "undecodable"):
            continue
        if not pred(r):
            continue
        b = actual(r)
        m = 0 if (b[7] & 3) else 1
        if (b[7] & 3) == 3:
            continue
        P = r["oracle"]["P"]
        want = ((m * P) + A_of(b[7], b[8], b[9], F, selector, index)) & M32
        got = r["observed"]["regs"][0] if r["observed"]["regs"] else None
        tot += 1
        if got == want:
            hit += 1
        elif len(miss) < 12:
            miss.append({"b7": b[7], "b8": b[8], "b9": b[9], "sset": r["sset"],
                         "want": want, "got": got, "arm": r["arm"]})
    return hit, tot, miss


def main():
    out = {}
    RUNS = {"dag": ["g17p_e0219_A_dag_run01", "g17p_e0219_A_dag_run02"],
            "const": ["g17p_e0219_A_const_run01", "g17p_e0219_A_const_run02"]}
    data = {c: {r: load(r) for r in rs} for c, rs in RUNS.items()}

    FILE = {"dag": fit_file(data["dag"]["g17p_e0219_A_dag_run01"], "cross"),
            "const": fit_file(data["const"]["g17p_e0219_A_const_run01"], "cross32")}
    out["FILE_fitted"] = {c: {str(k): v for k, v in sorted(f.items())}
                          for c, f in FILE.items()}
    out["FILE_fitted_hex"] = {c: {str(k): hex(v) for k, v in sorted(f.items()) if v}
                              for c, f in FILE.items()}

    # ---------------- Gate A ledger ------------------------------------------
    led = {}
    for c, rs in data.items():
        for rid, recs in rs.items():
            led[rid] = {"n": len(recs),
                        "gate_a_ok": sum(1 for r in recs if r["ledger"]["gate_a_ok"]),
                        "bytes_match": sum(1 for r in recs if r["ledger"]["bytes_match"]),
                        "distinct_actual": len({r["ledger"]["actual_bytes"] for r in recs}),
                        "distinct_requested": len({r["bytes"] for r in recs}),
                        "outcomes": collections.Counter(r["outcome"] for r in recs)}
    out["gate_a"] = {k: {kk: (dict(vv) if isinstance(vv, collections.Counter) else vv)
                         for kk, vv in v.items()} for k, v in led.items()}

    # ---------------- Gate B controls ----------------------------------------
    ctrl = {}
    for c, rs in data.items():
        for rid, recs in rs.items():
            cs = [r for r in recs if r["arm"] == "ctrl"]
            ctrl[rid] = [{"b7": actual(r)[7], "b9": actual(r)[9], "sset": r["sset"],
                          "outcome": r["outcome"], "r0": r["observed"]["regs"][0]
                          if r["observed"]["regs"] else None,
                          "A": r["recovered_A"], "predict": r["predict"][:44]}
                         for r in cs]
    out["gate_b_controls"] = ctrl

    # ---------------- A1: which bit is the selector ---------------------------
    a1 = {}
    for c, rs in data.items():
        for rid, recs in rs.items():
            rows = {}
            for r in recs:
                b = actual(r)
                if r["arm"] not in ("cross",) or b[8] != 0xd0:
                    continue
                if not r["ledger"]["gate_a_ok"]:
                    continue
                K = (b[7] >> 3) & 0x1F
                rows.setdefault(b[9], {})[(K, r["sset"])] = r["recovered_A"]
            summ = {}
            for b9, d in sorted(rows.items()):
                nimm = sum(1 for (K, s), A in d.items() if A == K)
                nfet = sum(1 for (K, s), A in d.items() if A == fget(FILE[c], K))
                summ[hex(b9)] = {"n": len(d), "A==IMM8(K)": nimm,
                                 "A==FILE[K]": nfet,
                                 "bit1": (b9 >> 1) & 1, "bit3": (b9 >> 3) & 1,
                                 "bit0": b9 & 1}
            if summ:
                a1[rid] = summ
    out["A1_b9_branch_by_value"] = a1

    # ---------------- A3: 32-bit fetch pairing --------------------------------
    a3 = {}
    for c, rs in data.items():
        for rid, recs in rs.items():
            pair = word = tot = 0
            detail = []
            for r in recs:
                b = actual(r)
                if b[8] != 0xd0 or b[9] != 0x2f or not r["ledger"]["gate_a_ok"]:
                    continue
                if r["outcome"] in ("hang", "fault", "measurement_failure"):
                    continue
                K = (b[7] >> 3) & 0x1F
                F = FILE[c]
                p = (fget(F, K) | (fget(F, K + 1) << 16)) & M32
                j = K & ~1
                w = (fget(F, j) | (fget(F, j + 1) << 16)) & M32
                A = r["recovered_A"]
                tot += 1
                pair += (A == p)
                word += (A == w)
                if p != w:
                    detail.append({"K": K, "sset": r["sset"], "A": A,
                                   "pair": p, "word": w,
                                   "verdict": "pair" if A == p else
                                              ("word" if A == w else "neither")})
            a3[rid] = {"n": tot, "pair_hits": pair, "word_hits": word,
                       "discriminating_cases": detail}
    out["A3_fetch32_pairing"] = a3

    # ---------------- A2: fetch index width -----------------------------------
    a2 = {}
    for c, rs in data.items():
        for rid, recs in rs.items():
            imm = collections.Counter()
            fetch_nonzero = []
            fetch_tot = 0
            imm_hit = imm_tot = 0
            for r in recs:
                b = actual(r)
                if r["arm"] != "b8imm" or not r["ledger"]["gate_a_ok"]:
                    continue
                K = (b[7] >> 3) & 0x1F
                hi3 = b[8] & 7
                A = r["recovered_A"]
                if b[9] == 0x26:                    # immediate branch (control)
                    imm_tot += 1
                    if A == ((hi3 << 5) | K):
                        imm_hit += 1
                    else:
                        imm[(hi3, K, A)] += 1
                elif b[9] == 0x2e:                  # fetch branch
                    fetch_tot += 1
                    if hi3 != 0 and A != 0:
                        fetch_nonzero.append({"K": K, "hi3": hi3, "A": A,
                                              "index8": K | (hi3 << 5),
                                              "sset": r["sset"]})
            a2[rid] = {"immediate_control": {"hit": imm_hit, "n": imm_tot,
                                             "misses": list(imm.items())[:8]},
                       "fetch_n": fetch_tot,
                       "fetch_nonzero_at_hi3_ne_0": fetch_nonzero[:40],
                       "n_fetch_nonzero_at_hi3_ne_0": len(fetch_nonzero)}
    out["A2_fetch_index_width"] = a2

    # ---------------- A4 + unified model scoreboard ---------------------------
    board = {}
    for c, rs in data.items():
        for rid, recs in rs.items():
            e = {}
            for selector in ("bit3", "bit1", "and", "or"):
                for index in ("5", "8"):
                    h, t, m = score(recs, FILE[c], selector, index)
                    e["U_%s_idx%s" % (selector, index)] = "%d/%d" % (h, t)
            # arm/branch breakdowns under the surviving model
            for nm, pred in (
                ("b9=0x26 immediate branch, all 32 K",
                 lambda r: actual(r)[9] == 0x26 and actual(r)[8] == 0xd0),
                ("b9=0x20 immediate branch, all 32 K",
                 lambda r: actual(r)[9] == 0x20),
                ("b9=0x22 (bit1=1,bit3=0)", lambda r: actual(r)[9] == 0x22),
                ("b9=0x2c (bit3=1,bit1=0)", lambda r: actual(r)[9] == 0x2c),
                ("b9=0x2e fetch 16-bit", lambda r: actual(r)[9] == 0x2e and actual(r)[8] == 0xd0),
                ("b9=0x2f fetch 32-bit", lambda r: actual(r)[9] == 0x2f),
                ("seed set 2 only", lambda r: r["sset"] == 2),
            ):
                h, t, _ = score(recs, FILE[c], "bit3", "5", pred)
                e["bit3/idx5 :: " + nm] = "%d/%d" % (h, t)
            board[rid] = e
    out["model_scoreboard"] = board

    # ---------------- Gate E: run01 x run02 -----------------------------------
    ge = {}
    for c, rs in RUNS.items():
        a, b = [load(x) for x in rs]
        ka = {(r["idx"]): r for r in a}
        kb = {(r["idx"]): r for r in b}
        shared = sorted(set(ka) & set(kb))
        ledeq = sum(1 for k in shared
                    if ka[k]["ledger"]["actual_bytes"] == kb[k]["ledger"]["actual_bytes"])
        agree = sum(1 for k in shared
                    if ka[k]["observed"]["regs"] == kb[k]["observed"]["regs"])
        hardA = {k for k in shared if ka[k]["outcome"] in ("hang", "fault",
                                                           "measurement_failure")}
        hardB = {k for k in shared if kb[k]["outcome"] in ("hang", "fault",
                                                           "measurement_failure")}
        dis = [k for k in shared
               if ka[k]["observed"]["regs"] != kb[k]["observed"]["regs"]]
        ge[c] = {"shared": len(shared), "ledger_identical": ledeq,
                 "payload_agree": agree,
                 "pct": round(100.0 * agree / max(len(shared), 1), 4),
                 "hard_a": len(hardA), "hard_b": len(hardB),
                 "hard_flips": len(hardA ^ hardB),
                 "disagreeing_idx": dis[:20]}
    out["gate_e"] = ge
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
