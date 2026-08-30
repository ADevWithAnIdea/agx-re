#!/usr/bin/env python3
"""EXP-0165 / DEF-0161-6 and DEF-0161-7 INDEPENDENT RE-DERIVATION.

DEF-0161-6: `carry_gen` byte+2 needs only (v & 0xCD) == 0x05, not the full 0x35.
DEF-0161-7: the low bit of each operand byte is a real SIZE bit -- clear it and
            the compare is 16-bit, not 32-bit.

The bit-rule is checked against EVERY value in the sweep (all 256), not just the
accepted set: the rule must accept exactly the accepted set and reject exactly
the rejected set.  DEF-0161-7 is re-scored from the generated encodings' block
bytes and the authored seed vector, ignoring EXP-0161's own verdict field.
"""
from __future__ import print_function
import json
from pathlib import Path

EXP161 = Path(__file__).resolve().parents[2] / "EXP-0161-g17p-carry-fspecial"
SEED = [0x80112233, 0x8F4E7A15, 0x0A2C51E7, 0xA7D30B49,
        0x161F94AB, 0xC48A2D5D, 0x23654EBF, 0xE2B0C721,
        0x310D3883, 0x47F6A9E5, 0x5613BA47, 0xF5E0CBA9,
        0x64CD1C0B, 0x73BA8D6D, 0xEE9F7ECF, 0x00000000]

def rows(run, arm, field):
    p = EXP161 / "raw" / run / "sweep.jsonl"
    if not p.exists(): return
    for l in p.open():
        r = json.loads(l)
        if r.get("arm") == arm and r.get("field") == field:
            yield r

def mask_rule(acc, rej, mask, want):
    """Does `(v & mask) == want` accept exactly `acc` and reject exactly `rej`?"""
    fp = sorted(v for v in rej if (v & mask) == want)     # rule accepts a rejected value
    fn = sorted(v for v in acc if (v & mask) != want)     # rule rejects an accepted value
    return {"false_accepts": fp, "false_rejects": fn,
            "exact": not fp and not fn}

def search_masks(acc, rej):
    """Every (mask, want) that separates the two sets exactly."""
    out = []
    for mask in range(256):
        wants = {v & mask for v in acc}
        if len(wants) != 1: continue
        want = wants.pop()
        if any((v & mask) == want for v in rej): continue
        out.append(("0x%02X" % mask, "0x%02X" % want, bin(mask).count("1")))
    return sorted(out, key=lambda t: t[2])

def analyse_b2(run, arm):
    acc, rej, other = [], [], []
    for r in rows(run, arm, "__raw_b2"):
        v = r["value"]; oc = r["outcome"]
        if oc == "ok": acc.append(v)
        elif oc in ("wrong_value", "silent_zero", "fault", "undecodable"): rej.append(v)
        else: other.append((v, oc))
    return {"n": len(acc) + len(rej) + len(other),
            "accepted": sorted(acc), "n_accepted": len(acc),
            "n_rejected": len(rej), "excluded": other,
            "rule_0xCD_0x05": mask_rule(acc, rej, 0xCD, 0x05),
            "rule_full_0xFF_0x35": mask_rule(acc, rej, 0xFF, 0x35),
            "all_exact_masks": search_masks(acc, rej)}

def analyse_gen(run):
    """DEF-0161-7: re-score every generated carry_gen case from its own bytes."""
    recs = [json.loads(l) for l in (EXP161 / "raw" / run / "sweep.jsonl").open()]
    base = next((r for r in recs if r.get("gen") == "carry_gen"
                 and r.get("desc") == "__baseline"), None)
    out = {"baseline_r1": ("%08x" % base["regs"][1]) if base and base.get("regs") else None,
           "n": 0, "model32": {}, "model16": {}, "detail": []}
    if not base or not base.get("regs"): return out
    base_hi = base["regs"][1]
    for r in recs:
        if r.get("gen") != "carry_gen" or r.get("desc") == "__baseline": continue
        blk = bytes.fromhex(r["block"])
        # carry_gen sits at offset 10 in the lifted 40-byte block
        va, vb = blk[10 + 1], blk[10 + 3]
        a, b = (va >> 1) & 0x3F, (vb >> 1) & 0x3F
        is32 = va & 1
        assert is32 == (vb & 1), "generated case mixes operand sizes"
        obs = r.get("observed_predicate")
        p32 = int(SEED[a] < SEED[b])
        p16 = int((SEED[a] & 0xFFFF) < (SEED[b] & 0xFFFF))
        # what the hardware actually did, scored two ways
        want_size = p32 if is32 else p16          # DEF-0161-7 model
        want_always32 = p32                       # the "size bit is not real" model
        out["n"] += 1
        k1 = "pass" if obs == want_size else "fail" if obs is not None else "no_obs"
        k2 = "pass" if obs == want_always32 else "fail" if obs is not None else "no_obs"
        out["model16"][k1] = out["model16"].get(k1, 0) + 1
        out["model32"][k2] = out["model32"].get(k2, 0) + 1
        out["detail"].append({"desc": r["desc"], "a": a, "b": b, "is32": is32,
                              "bit7": bool(va & 0x80), "observed_p": obs,
                              "pred_size_aware": want_size,
                              "pred_always32": want_always32,
                              "size_aware": k1, "always32": k2,
                              "harness_verdict": r.get("verdict")})
    return out

def main():
    rep = {}
    for run in ("g17p_20260829_run01", "g17p_20260829_run02"):
        for arm in ("A_CARRY_INPLACE", "A_CARRY_SYNTH"):
            rep["%s/%s byte+2" % (run, arm)] = analyse_b2(run, arm)
    for run in ("g17p_20260830_gen02", "g17p_20260830_gen03"):
        rep["%s carry_gen generation" % run] = analyse_gen(run)
    print(json.dumps(rep, indent=1))

if __name__ == "__main__":
    main()
