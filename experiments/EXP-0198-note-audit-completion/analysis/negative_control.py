#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0198 -- FALSIFIABILITY CONTROL.  "If your criterion cannot return 'no',
it is broken."  Thirteen such checks were found in this corpus this week, so
every instrument here is required to demonstrate that it CAN say no.

Method: write a perturbed copy of tools/agx-isa/validation.json into work/ in
which ONE number in ONE note per family is changed by +1, point the family's
check script at it via EXP0198_VALIDATION, and require the row to flip
SUPPORTED -> CONTRADICTED.  The real validation.json is never touched.

Read-only w.r.t. everything outside this experiment.
Writes work/validation.perturbed.json and analysis/negative_control.json.
"""
import copy, json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(EXP, "..", ".."))
WORK = os.path.join(EXP, "work")
PERT = os.path.join(WORK, "validation.perturbed.json")

# (script, row, regex whose first numeric group is bumped by 1)
CASES = [
    ("check_0139.py", "ibfe.b4", r"(126) values return a silent zero"),
    ("check_0157.py", "h_coord_hi.mods", r"outcomes ok=(1), wrong_value=254"),
    ("check_0162.py", "cvt_bf16.b7", r"'ok': (128)"),
    ("check_0155.py", "tex_write.coord_pack", r"^(2)/256 values disagree"),
    ("check_e0189_nonzero.py", "copysign.operands", r"UNSTABLE\): (256) values dispatched"),
    ("check_0140.py", "psel.flag", r"^(512)/512 comparable"),
    ("check_0138.py", "falu2_ext.mod_hi", r"^(8)/16 pre-registered"),
    ("check_0141.py", "atomic_rmw.oper_reg_hi", r"byte\+6 values 0x30 and 0x(31)"),
    ("check_0147.py", "pixel_order.flags", r"\((112)/256\)"),
    ("check_fspecial.py", "fspecial.roundmode", r"(128)/128 odd values"),
    ("check_misc.py", "carry_gen.srcB", r"fit (22)/22"),
]
OUTFILE = {"check_0139.py": "check_0139.json", "check_0157.py": "check_0157.json",
           "check_0162.py": "check_0162.json", "check_0155.py": "check_0155.json",
           "check_e0189_nonzero.py": "check_e0189_nonzero.json",
           "check_0140.py": "check_0140.json", "check_0138.py": "check_0138.json",
           "check_0141.py": "check_0141.json", "check_0147.py": "check_0147.json",
           "check_fspecial.py": "check_fspecial.json", "check_misc.py": "check_misc.json"}


def main():
    base = json.load(open(os.path.join(ROOT, "tools/agx-isa/validation.json")))
    results = []
    for script, key, rx in CASES:
        m, f = key.split(".", 1)
        v = copy.deepcopy(base)
        note = v["instructions"][m][f]["note"]
        mo = re.search(rx, note, re.M)
        if not mo:
            results.append({"script": script, "row": key, "status": "REGEX-DID-NOT-MATCH"})
            continue
        old = mo.group(1)
        new = str(int(old) + 1)
        v["instructions"][m][f]["note"] = (note[:mo.start(1)] + new + note[mo.end(1):])
        os.makedirs(WORK, exist_ok=True)
        json.dump(v, open(PERT, "w"))
        env = dict(os.environ, EXP0198_VALIDATION=PERT)
        p = subprocess.run([sys.executable, os.path.join(HERE, script)],
                           env=env, capture_output=True, text=True)
        out = json.load(open(os.path.join(HERE, OUTFILE[script])))
        if script == "check_0162.py":
            out = out["per_note"]
        got = out.get(key, {}).get("verdict")
        results.append({"script": script, "row": key, "perturbed": "%s -> %s" % (old, new),
                        "verdict_under_perturbation": got,
                        "control_passes": got == "CONTRADICTED",
                        "stderr": p.stderr[-200:] if p.returncode else ""})
    json.dump(results, open(os.path.join(HERE, "negative_control.json"), "w"), indent=1)
    ok = sum(1 for r in results if r.get("control_passes"))
    print("FALSIFIABILITY CONTROL: %d/%d instruments flipped to CONTRADICTED "
          "under a one-digit perturbation" % (ok, len(results)))
    for r in results:
        print("  %-26s %-26s %-14s %s" % (r["script"], r["row"],
                                          r.get("perturbed", "-"),
                                          r.get("verdict_under_perturbation",
                                                r.get("status"))))
    print("\nNOTE: the perturbed file is work/validation.perturbed.json; every check "
          "output in analysis/ must be REGENERATED from the real validation.json "
          "afterwards (the reproduction script does this).")


if __name__ == "__main__":
    main()
