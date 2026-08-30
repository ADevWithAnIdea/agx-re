#!/usr/bin/env python3
"""EXP-0195 step 3: join the two UNCHANGED-gate runs onto the 132-row population.

  verdicts_e0195_rerun.json    EXP-0194/analysis/adjudicate2.py, full record stream
                               (reproduces EXP-0194's headline 1/46/519 exactly)
  verdicts_uncited_only.json   the SAME script, stream restricted to non-cited experiments

A row is a RECOVERY only if it passes the gate on evidence its own label does not cite,
i.e. DESK-PROMOTABLE in verdicts_uncited_only.json.
"""
import json, os, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
E0194 = os.path.join(ROOT, "experiments", "EXP-0194-desk-promotion-audit", "analysis")

rows = json.load(open(os.path.join(HERE, "uncited_rows.json")))
full = {(r["instr"], r["field"]): r for r in json.load(open(os.path.join(HERE, "verdicts_e0195_rerun.json")))}
unco = {(r["instr"], r["field"]): r for r in json.load(open(os.path.join(HERE, "verdicts_uncited_only.json")))}
xc = json.load(open(os.path.join(E0194, "verdict_crosscheck.json")))
refus = json.load(open(os.path.join(HERE, "documented_refusals.json")))

out = []
for r in rows:
    k = (r["instr"], r["field"])
    f, u = full[k], unco[k]
    fg, ug = f.get("group") or {}, u.get("group") or {}
    x = xc.get("%s.%s" % k, [])
    xu = [h for h in x if h.get("primary") and h.get("exp") in r["uncited_exps"]]
    out.append(dict(
        instr=k[0], field=k[1], label=r["label"], evidence=r["evidence"],
        uncited_exps=r["uncited_exps"], cited_exps_with_raw=r["cited_exps_with_raw"],
        verdict_full_stream=f["verdict"], stop_full=fg.get("stop"),
        best_group_full=fg.get("carrier"),
        verdict_uncited_only=u["verdict"], stop_uncited=ug.get("stop"),
        best_group_uncited=ug.get("carrier"),
        n_clean_uncited=ug.get("n_clean"), n_enc_uncited=ug.get("n_encoded_values"),
        n_payloads_uncited=ug.get("n_payloads"), n_runs_uncited=ug.get("n_runs"),
        reason_uncited=u.get("reason"),
        crosscheck_emittergrade_in_uncited_exp=[dict(exp=h["exp"], label=h["label"],
                                                     target=h.get("target"), file=h["file"])
                                                for h in xu],
        documented_refusal=refus.get("%s.%s" % k, []),
        note=r["target_note"]))

json.dump(out, open(os.path.join(HERE, "classification.json"), "w"), indent=1)

print("EXP-0195 population: %d blocked field rows with raw in a non-cited experiment\n" % len(out))
print("A) Gate verdict on the FULL record stream (cited + uncited), unchanged adjudicate2.py:")
for k, v in collections.Counter(r["verdict_full_stream"] for r in out).most_common():
    print("     %-18s %d" % (k, v))
print("\nB) Gate verdict on the UNCITED-ONLY stream -- the recovery question:")
for k, v in collections.Counter(r["verdict_uncited_only"] for r in out).most_common():
    print("     %-18s %d" % (k, v))
print("\nC) HARDWARE-BLOCKED (uncited-only), by stop gate / reason:")
for k, v in collections.Counter(
        (r["stop_uncited"] or "G1") for r in out if r["verdict_uncited_only"] == "HARDWARE-BLOCKED").most_common():
    print("     stop=%-5s %d" % (k, v))
print("\nD) AMBIGUOUS (uncited-only) rows, and whether a documented refusal already exists:")
amb = [r for r in out if r["verdict_uncited_only"] == "AMBIGUOUS"]
print("     total AMBIGUOUS                     %d" % len(amb))
print("     ... with a documented refusal       %d" % sum(1 for r in amb if r["documented_refusal"]))
print("     ... without                         %d" % sum(1 for r in amb if not r["documented_refusal"]))
print("\nE) RECOVERIES (DESK-PROMOTABLE on uncited-only evidence):")
rec = [r for r in out if r["verdict_uncited_only"] == "DESK-PROMOTABLE"]
for r in rec:
    print("     %s.%s   label=%s cites=%s   passed on %s"
          % (r["instr"], r["field"], r["label"], ",".join(r["evidence"]), r["best_group_uncited"]))
if not rec:
    print("     (none)")
print("\nF) Second method -- uncited experiment's OWN field_verdicts*.json is emitter-grade:")
for r in out:
    if r["crosscheck_emittergrade_in_uncited_exp"]:
        print("     %-20s %-14s %s -> %s" % (r["instr"], r["field"],
              [h["exp"] for h in r["crosscheck_emittergrade_in_uncited_exp"]],
              [h["label"] + "/" + str(h["target"]) for h in r["crosscheck_emittergrade_in_uncited_exp"]]))
