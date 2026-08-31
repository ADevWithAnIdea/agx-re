#!/usr/bin/env python3
"""EXP-0218 shared helpers — READ-ONLY over committed artifacts.

Never writes into raw/. Never touches tools/agx-isa/, docs/ or PROVENANCE.md.
Never contacts a device.

Every quantity here is decoded from the record's own `bytes` column by BYTE
POSITION. The record's `field` key, its `instr` string and its `fstart`/`fwidth`
are carried through as UNTRUSTED LABELS so they can be tested; they are never
used to decide which bits were swept.
"""
from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
EXP = Path(__file__).resolve().parents[1]

M32 = 0xFFFFFFFF
POISON = 0xDEADBEEF

# ---------------------------------------------------------------- carriers ---
# C-G17P: SYNTH+LIFTED k_imad in carrier_dag, 16 GPRs seeded by us.
SEED_I = {0: 10, 1: 21, 2: 34, 3: 47, 4: 58, 5: 65, 6: 71, 7: 83,
          8: 94, 9: 101, 10: 113, 11: 119, 12: 125, 13: 127, 14: 3, 15: 0}
SEED_I2 = {0: 7, 1: 13, 2: 19, 3: 29, 4: 37, 5: 43, 6: 53, 7: 61,
           8: 73, 9: 79, 10: 89, 11: 97, 12: 103, 13: 109, 14: 5, 15: 0}
SEEDS = {1: SEED_I, 2: SEED_I2}
ANCHOR_G17P = "9f00560002080060d02e0a00"

# C-M4: NATURAL k_imad (o[i] = a[i]*b[i] + 7u), 8 lanes.
A_IN = [0x12345678, 0xFFFFFFFF, 0x0000FF00, 0xDEADBEEF,
        0x00000001, 0x00000000, 0x80000000, 0x7FFFFFFF]
B_IN = [3, 5, 8, 1, 31, 32, 2, 0]
PROD_M4 = [(a * b) & M32 for a, b in zip(A_IN, B_IN)]
ANCHOR_M4 = "9f00560002080038d0260a00"

G17P_FILES = (
    "EXP-0154-g17p-emit-alu/raw/g17p_20260829_run02/sweep.jsonl",
    "EXP-0154-g17p-emit-alu/raw/g17p_20260829_run04/sweep.jsonl",
    "EXP-0160-g17p-last-field/raw/g17p_20260830_run01/sweep.jsonl",
    "EXP-0160-g17p-last-field/raw/g17p_20260830_run02/sweep.jsonl",
    "EXP-0160-g17p-last-field/raw/g17p_20260830_confirm01/confirm.jsonl",
    "EXP-0160-g17p-last-field/raw/g17p_20260830_confirm02/confirm.jsonl",
    "EXP-0160-g17p-last-field/raw/g17p_20260830_confirm03/confirm.jsonl",
    "EXP-0160-g17p-last-field/raw/g17p_20260830_confirm04/confirm.jsonl",
    "EXP-0160-g17p-last-field/raw/g17p_20260830_confirm06/confirm.jsonl",
)
M4_FILES = (
    "EXP-0139-m4-emit-ialu/raw/m4_20260828_run01/sweep.jsonl",
    "EXP-0139-m4-emit-ialu/raw/m4_20260828_run02/sweep.jsonl",
    "EXP-0139-m4-emit-ialu/raw/m4_20260828_reval01/revalidate.jsonl",
    "EXP-0139-m4-emit-ialu/raw/m4_20260828_reval02/revalidate.jsonl",
)


def _load(rel):
    p = REPO / "experiments" / rel
    with p.open() as fh:
        for i, line in enumerate(fh, 1):
            line = line.strip()
            if not line or line[0] != "{":
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("instr") != "imad":
                continue
            yield rel, i, r


def outcome_of(r):
    o = r.get("outcome")
    if o is None:
        a = r.get("attempts") or []
        if a and isinstance(a[0], dict):
            o = a[0].get("outcome")
    return o


def victim(r):
    if r.get("victim"):
        return True
    e = r.get("error") or ""
    if "InnocentVictim" in e:
        return True
    for a in (r.get("attempts") or []):
        if isinstance(a, dict) and (a.get("victim") or
                                    "InnocentVictim" in (a.get("error") or "")):
            return True
    return False


EXCLUDE_FIELDS = ("__falsifier", "_poscontrol", "_baseline")
BAD_OUTCOMES = ("fault", "hang", "timeout", "undecodable", None)


def cases_g17p():
    """Yield dicts for every C-G17P imad case with usable state.

    keys: src (file:line), raw (bytes object), sset, outcome, regs, excl (reason
    or None), field (untrusted), exp, run.
    """
    for rel in G17P_FILES:
        exp = rel.split("/")[0]
        run = rel.split("/")[2]
        for _, ln, r in _load(rel):
            bh = r.get("bytes")
            if not bh:
                continue
            raw = bytes.fromhex(bh)
            fld = str(r.get("field"))
            oc = outcome_of(r)
            regs = (r.get("observed") or {}).get("regs")
            excl = None
            if any(fld.startswith(x) for x in EXCLUDE_FIELDS):
                excl = "control_case"
            elif victim(r):
                excl = "measurement_failure_victim"
            elif oc in BAD_OUTCOMES:
                excl = "outcome_" + str(oc)
            elif not regs:
                excl = "no_register_dump"
            elif (raw[1] & 1) != (bytes.fromhex(ANCHOR_G17P)[1] & 1):
                excl = "lenbit_framing_break"
            yield {"src": f"{rel}:{ln}", "exp": exp, "run": run, "raw": raw,
                   "hex": bh, "sset": r.get("sset") or 1, "outcome": oc,
                   "regs": regs, "excl": excl, "field": fld}


def cases_m4():
    """Yield dicts for every C-M4 imad case. `words` is the 8-lane result."""
    for rel in M4_FILES:
        exp = rel.split("/")[0]
        run = rel.split("/")[2]
        for _, ln, r in _load(rel):
            bh = r.get("bytes")
            if not bh:
                continue
            raw = bytes.fromhex(bh)
            fld = str(r.get("field"))
            oc = outcome_of(r)
            obs = r.get("observed")
            words = None
            if isinstance(obs, str) and len(obs) >= 64:
                words = [int(obs[i:i + 8], 16) for i in range(0, 64, 8)]
            excl = None
            if any(fld.startswith(x) for x in EXCLUDE_FIELDS):
                excl = "control_case"
            elif victim(r):
                excl = "measurement_failure_victim"
            elif oc in BAD_OUTCOMES:
                excl = "outcome_" + str(oc)
            elif words is None:
                excl = "no_output_words"
            elif (raw[1] & 1) != (bytes.fromhex(ANCHOR_M4)[1] & 1):
                excl = "lenbit_framing_break"
            yield {"src": f"{rel}:{ln}", "exp": exp, "run": run, "raw": raw,
                   "hex": bh, "outcome": oc, "words": words, "excl": excl,
                   "field": fld, "status": r.get("status")}


def swept_byte(raw, anchor_hex):
    """Which byte positions differ from the arm anchor. Returns a tuple."""
    a = bytes.fromhex(anchor_hex)
    return tuple(i for i in range(min(len(a), len(raw))) if raw[i] != a[i])


def dump(obj, name):
    p = EXP / "analysis" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=1, sort_keys=True, default=str) + "\n")
    print("wrote", p.relative_to(REPO))
