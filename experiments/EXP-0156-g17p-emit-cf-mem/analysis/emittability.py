#!/usr/bin/env python3
"""EXP-0156: recompute instruction-level emittability from
`tools/agx-isa/validation.json` (READ-ONLY) plus this experiment's proposed
verdicts in `analysis/field_verdicts.json`.

`docs/evidence-classification.md`'s emittable rule: a family is emittable only
if EVERY field an emitter must fill is `hardware-run` or `isolated-byte-diff`.
Instruction-level `emit_unsafe` vetoes in `db.json` are honoured separately and
are NOT lifted by this experiment (the orchestrator owns `db.json`).
"""
import json
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
REPO = EXP.parents[1]
GOOD = {"hardware-run", "isolated-byte-diff"}


def main():
    db = json.load((REPO / "tools/agx-isa/db.json").open())
    val = json.load((REPO / "tools/agx-isa/validation.json").open())["instructions"]
    fv_path = EXP / "analysis" / "field_verdicts.json"
    fv = json.load(fv_path.open()) if fv_path.exists() else {}
    ins = {i["mnemonic"]: i for i in db["instructions"]}
    veto = {m for m, d in ins.items() if d.get("emit_unsafe")}

    def label(m, f, proposed):
        if proposed:
            k = "%s.%s" % (m, f)
            if k in fv and isinstance(fv[k], dict) and "label" in fv[k]:
                return fv[k]["label"]
        return (val.get(m, {}).get(f) or {}).get("label", "untested")

    out = {}
    for tag, proposed in (("before", False), ("after", True)):
        emit, blocked, fg, ft = [], {}, 0, 0
        for m, d in ins.items():
            bad = []
            for f in d["fields"]:
                ft += 1
                lab = label(m, f["name"], proposed)
                if lab in GOOD:
                    fg += 1
                else:
                    bad.append([f["name"], lab])
            if bad:
                blocked[m] = bad
            elif m in veto:
                blocked[m] = [["<instruction-level emit_unsafe veto>", "veto"]]
            else:
                emit.append(m)
        out[tag] = {"emittable": sorted(emit), "n_emittable": len(emit),
                    "n_instructions": len(ins), "fields_emitter_grade": fg,
                    "fields_total": ft, "blocked": blocked}
    delta = sorted(set(out["after"]["emittable"]) - set(out["before"]["emittable"]))
    out["newly_emittable"] = delta
    # TARGET MIXING, stated explicitly (CODEX target discipline): validation.json's
    # existing labels were established on the M4/G16G. This experiment's verdicts are
    # G17P. An instruction that becomes emittable here may still rest on M4 labels for
    # the fields this experiment did not sweep, and that is NOT a G17P claim.
    mix = {}
    for m in delta:
        d = ins[m]
        g17p = [f["name"] for f in d["fields"]
                if "%s.%s" % (m, f["name"]) in fv]
        m4 = [f["name"] for f in d["fields"] if f["name"] not in g17p]
        mix[m] = {"fields_validated_on_G17P_here": sorted(g17p),
                  "fields_still_resting_on_M4_labels": sorted(m4),
                  "fully_G17P": not m4}
    out["target_mixing"] = mix
    out["newly_emittable_on_G17P_evidence_alone"] = sorted(
        m for m in delta if not mix[m]["fields_still_resting_on_M4_labels"])
    out["field_delta"] = out["after"]["fields_emitter_grade"] - \
        out["before"]["fields_emitter_grade"]
    out["loop_instructions"] = {
        m: ("EMITTABLE" if m in out["after"]["emittable"] else
            out["after"]["blocked"].get(m))
        for m in ["if_push_pred", "jump_cond", "if_push", "ret", "jump",
                  "pop_reconverge", "icmp_pred", "iadd2", "device_load",
                  "device_store", "get_sr", "stop"]}
    out["loops_emittable"] = all(
        v == "EMITTABLE" for v in out["loop_instructions"].values())
    print(json.dumps({k: v for k, v in out.items() if k != "before"},
                     indent=1, sort_keys=True)[:4000])
    (EXP / "analysis" / "emittability.json").write_text(
        json.dumps(out, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
