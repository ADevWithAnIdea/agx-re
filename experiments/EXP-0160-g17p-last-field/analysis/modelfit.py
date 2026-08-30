#!/usr/bin/env python3
"""EXP-0160 model fitting: value -> behaviour models for a swept field.

Frozen model class (PRE_REGISTRATION section 7):

  M1  MASK      ok <=> (v & M) == V, exactly, over the dense range.
  M2  RELEVANT  the set R of bits that are NOT inert (flipping bit i changes
                the observed 16-register digest for at least one v). If
                |R| <= w-2 -- i.e. every equivalence class of the map is
                confirmed by >= 4 distinct field values -- the complete class
                table IS the field's semantics.
  M3  REGMAP    value -> register-index model over the release/write dump.
  M4  ARITH     value -> operation, identified from the written value against a
                host-computed library of functions of the seeds, required to
                agree across BOTH seed sets.

Nothing here touches hardware; it is a pure function of committed raw records.
"""
from __future__ import print_function

import json
from collections import Counter, defaultdict

POISON = 0xDEADBEEF
NREG = 16

REG_MODELS = {
    "reg = v>>1  ((reg<<1)|size)": lambda v: v >> 1,
    "reg = (v>>1)&63": lambda v: (v >> 1) & 63,
    "reg = v>>2  (reg<<2)": lambda v: v >> 2,
    "reg = v&127": lambda v: v & 127,
    "reg = v&63": lambda v: v & 63,
    "reg = v&15": lambda v: v & 15,
    "reg = v": lambda v: v,
}


def sig(regs, base):
    """Structural signature of one dump, independent of the seed VALUES:
    per register, one of  same / zeroed / poison / changed."""
    if regs is None:
        return None
    out = []
    for i in range(NREG):
        if regs[i] == POISON:
            out.append("P")
        elif regs[i] == base[i]:
            out.append(".")
        elif regs[i] == 0:
            out.append("Z")
        else:
            out.append("C")
    return "".join(out)


def mask_rule(ok, allv, w):
    ok = set(ok)
    if not ok:
        return None, None, None
    m = val = 0
    for b in range(w):
        s = set((v >> b) & 1 for v in ok)
        if len(s) == 1:
            m |= 1 << b
            val |= s.pop() << b
    pred = set(v for v in allv if (v & m) == val)
    return m, val, len(pred ^ ok)


def relevant_bits(sigmap, w):
    """Bit i is INERT iff sig(v) == sig(v ^ (1<<i)) for every v where both are
    observed. Returns the sorted list of relevant (non-inert) bits."""
    rel = []
    for i in range(w):
        for v, s in sigmap.items():
            o = v ^ (1 << i)
            if o in sigmap and sigmap[o] != s:
                rel.append(i)
                break
    return rel


def class_table(sigmap, rel, w):
    """Collapse the map onto the relevant bits; verify it is a FUNCTION of
    them (0 exceptions) and report the per-class support."""
    def key(v):
        k = 0
        for j, b in enumerate(sorted(rel)):
            k |= ((v >> b) & 1) << j
        return k
    tab = defaultdict(set)
    for v, s in sigmap.items():
        tab[key(v)].add(s)
    exceptions = sum(1 for k in tab if len(tab[k]) > 1)
    support = min(len(set(v for v in sigmap if key(v) == k)) for k in tab) if tab else 0
    return ({k: sorted(vs)[0] for k, vs in tab.items()},
            exceptions, support, sorted(rel))


def regmap_score(dumps, base):
    """dumps: value -> regs. Score every candidate register model on which
    single register was zeroed (released) and which single one was written."""
    rel, wrt = {}, {}
    for v, regs in dumps.items():
        if regs is None or POISON in regs:
            continue
        rel[v] = [i for i in range(NREG) if base[i] != 0 and regs[i] == 0]
        wrt[v] = [i for i in range(NREG) if regs[i] != base[i] and regs[i] not in (0, POISON)]

    def score(m):
        out = {}
        for name, f in REG_MODELS.items():
            hits = wrong = silent = multi = 0
            regs = set()
            for v, got in m.items():
                p = f(v)
                if p >= NREG:
                    continue
                if not got:
                    silent += 1
                elif len(got) > 1:
                    multi += 1
                elif got[0] == p:
                    hits += 1; regs.add(p)
                else:
                    wrong += 1
            den = hits + wrong
            if den:
                out[name] = {"hits": hits, "wrong": wrong, "silent": silent,
                             "multi": multi, "identified": den,
                             "rate": round(hits / float(den), 3),
                             "distinct_regs": len(regs)}
        return out
    return {"released": score(rel), "written": score(wrt)}


def best_regmodel(tab, min_rate=0.90, min_regs=6):
    best = None
    for n, s in tab.items():
        if s["rate"] >= min_rate and s["distinct_regs"] >= min_regs:
            k = (s["distinct_regs"], s["hits"])
            if best is None or k > (best[1]["distinct_regs"], best[1]["hits"]):
                best = (n, s)
    return best
