#!/usr/bin/env python3
"""EXP-0173: measure what each tool gate is SENSITIVE TO, by mutation.

A gate that passes is worth nothing until you know what makes it fail. For each
gate we (1) run it unmodified, then (2) inject a defect the gate is *claimed* to
protect against and re-run. If it still passes, the gate does not gate that class.

Nothing here modifies a tool, db.json or validation.json: mutations are applied
to COPIES under ../work/ or by monkeypatching an in-process import.

    python3 experiments/EXP-0173-closure-audit/analysis/gate_sensitivity.py
"""
import copy, json, os, subprocess, sys, shutil, io, contextlib, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(EXP))
ISA = os.path.join(ROOT, "tools", "agx-isa")
WORK = os.path.join(EXP, "work")
RAW = os.path.join(EXP, "raw", "mutation_runs.txt")
results = []


def log(s):
    with open(RAW, "a") as f:
        f.write(s + "\n")
    print(s)


def run_suite_in_subprocess(pycode, cwd):
    """Run roundtrip_test.py under a sabotage shim, in a fresh interpreter."""
    p = subprocess.run([sys.executable, "-c", pycode], cwd=cwd,
                       capture_output=True, text=True, timeout=600)
    return p.returncode, p.stdout, p.stderr


# ---------------------------------------------------------------- gate 1
def gate_roundtrip():
    """roundtrip_test.py: baseline + three sabotages of increasing subtlety."""
    base = subprocess.run([sys.executable, "roundtrip_test.py"], cwd=ISA,
                          capture_output=True, text=True, timeout=600)
    ok = "ALL PASS" in base.stdout
    results.append({"gate": "roundtrip_test.py", "mutation": "none (baseline)",
                    "exit": base.returncode, "passed": ok,
                    "verdict": "baseline passes" if ok else "BASELINE FAILS"})
    log("[roundtrip] baseline exit=%d pass=%s" % (base.returncode, ok))

    # --- M1: the DEF-0166-1 bug itself: assemble() cannot CLEAR a bit.
    m1 = r'''
import sys, isadb
_orig = isadb.assemble
def broken(mnemonic, fields):
    desc = isadb._BY_MNEM[mnemonic]
    v = 0
    for (s, w, val) in desc["match"]:
        v |= (val & ((1 << w) - 1)) << s
    for f in desc["fields"]:
        val = fields.get(f["name"], 0)
        mask = (1 << f["width"]) - 1
        if val & ~mask:
            raise ValueError("width")
        v |= (val & mask) << f["start"]          # BARE OR: cannot clear a bit
    return isadb._bytes_from_int(v, desc["length"])
isadb.assemble = broken
sys.argv = ["roundtrip_test.py"]
g = {"__name__": "__main__", "isadb": isadb}
exec(open("roundtrip_test.py").read(), g)
'''
    rc, so, se = run_suite_in_subprocess(m1, ISA)
    ok = "ALL PASS" in so
    results.append({"gate": "roundtrip_test.py",
                    "mutation": "M1: assemble() reverted to bare-OR (DEF-0166-1) — cannot clear a bit",
                    "exit": rc, "passed": ok,
                    "verdict": "INSENSITIVE — a provably broken assembler passes" if ok
                               else "sensitive (suite failed)",
                    "stderr_tail": se[-400:]})
    log("[roundtrip] M1 bare-OR assemble: exit=%d ALLPASS=%s" % (rc, ok))

    # --- M2: assemble() silently forces one operand field to 0.
    m2 = r'''
import sys, isadb
_orig = isadb.assemble
def broken(mnemonic, fields):
    f2 = dict(fields)
    for k in list(f2):
        if k in ("dst", "srcA", "src"):
            f2[k] = 0                            # silently drop the operand
    return _orig(mnemonic, f2)
isadb.assemble = broken
sys.argv = ["roundtrip_test.py"]
g = {"__name__": "__main__", "isadb": isadb}
exec(open("roundtrip_test.py").read(), g)
'''
    rc, so, se = run_suite_in_subprocess(m2, ISA)
    ok = "ALL PASS" in so
    results.append({"gate": "roundtrip_test.py",
                    "mutation": "M2: assemble() forces dst/srcA/src to 0 (operand silently dropped)",
                    "exit": rc, "passed": ok,
                    "verdict": "INSENSITIVE" if ok else "sensitive (suite failed)",
                    "stderr_tail": se[-400:]})
    log("[roundtrip] M2 zeroed operands: exit=%d ALLPASS=%s" % (rc, ok))

    # --- M3: the fspecial defect class — swap two operand field NAMES in the
    #        descriptor. Both codec directions share the descriptor, so a
    #        symmetric round trip cannot see it. Applied to a db.json COPY.
    shutil.rmtree(os.path.join(WORK, "isa_m3"), ignore_errors=True)
    shutil.copytree(ISA, os.path.join(WORK, "isa_m3"),
                    ignore=shutil.ignore_patterns("__pycache__"))
    dbp = os.path.join(WORK, "isa_m3", "db.json")
    db = json.load(open(dbp))
    swapped = None
    for i in db["instructions"]:
        names = {f["name"]: f for f in i.get("fields", [])}
        if "srcA" in names and "srcB" in names and \
           names["srcA"]["width"] == names["srcB"]["width"]:
            names["srcA"]["name"], names["srcB"]["name"] = "srcB", "srcA"
            swapped = i["mnemonic"]
            break
    json.dump(db, open(dbp, "w"), indent=1)
    rc = subprocess.run([sys.executable, "roundtrip_test.py"],
                        cwd=os.path.join(WORK, "isa_m3"),
                        capture_output=True, text=True, timeout=600)
    ok = "ALL PASS" in rc.stdout
    results.append({"gate": "roundtrip_test.py",
                    "mutation": "M3: db.json copy with %s.srcA <-> srcB swapped "
                                "(the fspecial defect class)" % swapped,
                    "exit": rc.returncode, "passed": ok,
                    "verdict": "INSENSITIVE — an operand SWAP is invisible to a symmetric "
                               "round trip" if ok else "sensitive (suite failed)"})
    log("[roundtrip] M3 %s srcA<->srcB swap: exit=%d ALLPASS=%s"
        % (swapped, rc.returncode, ok))


# ---------------------------------------------------------------- gate 2
def gate_validate_labels():
    base = subprocess.run([sys.executable, "validate_labels.py"], cwd=ISA,
                          capture_output=True, text=True, timeout=600)
    results.append({"gate": "validate_labels.py", "mutation": "none (baseline)",
                    "exit": base.returncode, "passed": base.returncode == 0,
                    "verdict": "baseline passes (exit 0)"})
    log("[validate_labels] baseline exit=%d" % base.returncode)

    shutil.rmtree(os.path.join(WORK, "isa_vl"), ignore_errors=True)
    shutil.copytree(ISA, os.path.join(WORK, "isa_vl"),
                    ignore=shutil.ignore_patterns("__pycache__"))
    vp = os.path.join(WORK, "isa_vl", "validation.json")

    # V1: promote a genuinely untested field to hardware-run with a fabricated
    #     evidence string and range. Does the structural checker notice?
    val = json.load(open(vp))
    victim = None
    for m, e in val["instructions"].items():
        for n, row in e.items():
            if n.startswith("_"):
                continue
            if row.get("label") == "untested":
                victim = (m, n)
                break
        if victim:
            break
    m, n = victim
    val["instructions"][m][n] = {"label": "hardware-run",
                                 "evidence": ["EXP-9999/raw/does_not_exist/run.json"],
                                 "range": "0..255 dense",
                                 "target": "G17P",
                                 "note": "fabricated by EXP-0173 gate-sensitivity test"}
    json.dump(val, open(vp, "w"), indent=1)
    r = subprocess.run([sys.executable, "validate_labels.py"],
                       cwd=os.path.join(WORK, "isa_vl"),
                       capture_output=True, text=True, timeout=600)
    # coverage block will now disagree, which IS a real check; look for that
    ok = r.returncode == 0
    results.append({"gate": "validate_labels.py",
                    "mutation": "V1: %s.%s promoted untested -> hardware-run with a "
                                "NON-EXISTENT evidence path" % (m, n),
                    "exit": r.returncode, "passed": ok,
                    "verdict": ("INSENSITIVE to fabricated evidence — exits 0" if ok else
                                "fails, but check WHY (coverage arithmetic, not evidence existence)"),
                    "stdout": r.stdout, "stderr": r.stderr})
    log("[validate_labels] V1 fabricated promotion of %s.%s: exit=%d" % (m, n, r.returncode))

    # V1b: same but ALSO fix the coverage block, so only the evidence path is wrong.
    val2 = json.load(open(vp))
    cov = val2.get("coverage", {})
    # recompute the coverage block the way merge_verdicts does
    dbf = {i["mnemonic"]: [f["name"] for f in i.get("fields", [])]
           for i in json.load(open(os.path.join(WORK, "isa_vl", "db.json")))["instructions"]}
    LB = ["hardware-run", "isolated-byte-diff", "corpus-correlation", "tokenization-only",
          "single-template-inference", "api-accept-reject", "host-private", "untested"]
    counts = {l: 0 for l in LB}
    total = 0
    for mm, entry in val2["instructions"].items():
        for nn in dbf.get(mm, []):
            if nn in entry:
                counts[entry[nn]["label"]] += 1
                total += 1
    cov["by_label"] = counts
    cov["total_fields"] = total
    cov["by_label_pct"] = {k: round(100.0 * c / total, 1) for k, c in counts.items()}
    json.dump(val2, open(vp, "w"), indent=1)
    r2 = subprocess.run([sys.executable, "validate_labels.py"],
                        cwd=os.path.join(WORK, "isa_vl"),
                        capture_output=True, text=True, timeout=600)
    ok2 = r2.returncode == 0
    results.append({"gate": "validate_labels.py",
                    "mutation": "V1b: same fabricated promotion, coverage block recomputed "
                                "so ONLY the evidence path is false",
                    "exit": r2.returncode, "passed": ok2,
                    "verdict": ("INSENSITIVE — a hardware-run label whose cited raw file "
                                "DOES NOT EXIST passes the validator" if ok2
                                else "sensitive"),
                    "stdout": r2.stdout, "stderr": r2.stderr})
    log("[validate_labels] V1b coverage-corrected fabrication: exit=%d" % r2.returncode)

    # V1c: fabricated promotion with the ENTIRE coverage block (label counts AND
    #      the emittable list/counts) recomputed, so every arithmetic check the
    #      validator makes is satisfied and the ONLY falsehood left is that the
    #      cited raw evidence file does not exist.
    val3 = json.load(open(vp))
    db3 = json.load(open(os.path.join(WORK, "isa_vl", "db.json")))
    dbf3 = {i["mnemonic"]: [f["name"] for f in i.get("fields", [])] for i in db3["instructions"]}
    dw = {i["mnemonic"] for i in db3["instructions"] if i.get("emitter_role") == "data-word"}
    EMIT_OK = {"hardware-run", "isolated-byte-diff"}
    counts3 = {l: 0 for l in LB}
    total3 = 0
    emit3 = []
    for mm, entry in val3["instructions"].items():
        names = dbf3.get(mm, [])
        for nn in names:
            if nn in entry:
                counts3[entry[nn]["label"]] += 1
                total3 += 1
        labs = [entry[nn]["label"] for nn in names if nn in entry]
        ok = bool(names) and len(labs) == len(names) and all(l in EMIT_OK for l in labs)
        if "EMITTABLE VETO" in ((entry.get("_instruction") or {}).get("note", "") or ""):
            ok = False
        if ok:
            emit3.append(mm)
    c3 = val3["coverage"]
    c3["by_label"] = counts3
    c3["total_fields"] = total3
    c3["by_label_pct"] = {k: round(100.0 * c / total3, 1) for k, c in counts3.items()}
    c3["emittable_mnemonics"] = sorted(emit3)
    c3["emittable_instructions"] = len(emit3)
    c3["emittable_of_emitter_relevant"] = len(emit3)
    c3["emitter_relevant_instructions"] = len(db3["instructions"]) - len(dw)
    c3["decodable_not_yet_emittable"] = len(db3["instructions"]) - len(emit3) - len(dw) + len(dw)
    json.dump(val3, open(vp, "w"), indent=1)
    r3 = subprocess.run([sys.executable, "validate_labels.py"],
                        cwd=os.path.join(WORK, "isa_vl"),
                        capture_output=True, text=True, timeout=600)
    ok3 = r3.returncode == 0
    results.append({"gate": "validate_labels.py",
                    "mutation": "V1c: fabricated hardware-run promotion of %s.%s, ALL coverage "
                                "arithmetic recomputed; the only remaining falsehood is that the "
                                "cited evidence file EXP-9999/raw/does_not_exist/run.json "
                                "does not exist" % (m, n),
                    "exit": r3.returncode, "passed": ok3,
                    "verdict": ("INSENSITIVE — an emitter-grade label citing a NON-EXISTENT raw "
                                "artifact passes; the validator never opens an evidence path"
                                if ok3 else "sensitive"),
                    "stdout": r3.stdout, "stderr": r3.stderr})
    log("[validate_labels] V1c full-arithmetic fabrication: exit=%d PASS=%s" % (r3.returncode, ok3))


# ---------------------------------------------------------------- gate 3
def gate_merge_verdicts():
    r = subprocess.run([sys.executable, os.path.join(ROOT, "work", "merge_verdicts.py"),
                        "--dry-run"] +
                       __import__("glob").glob(os.path.join(
                           ROOT, "experiments", "EXP-01*", "analysis", "field_verdicts.json")),
                       cwd=ROOT, capture_output=True, text=True, timeout=600)
    results.append({"gate": "work/merge_verdicts.py --dry-run",
                    "mutation": "none (baseline over every EXP-01*/analysis/field_verdicts.json)",
                    "exit": r.returncode, "passed": r.returncode == 0,
                    "verdict": "see stdout_tail",
                    "stdout_tail": r.stdout[-2500:], "stderr_tail": r.stderr[-800:]})
    log("[merge_verdicts] baseline --dry-run exit=%d" % r.returncode)


def main():
    open(RAW, "a").write("\n=== EXP-0173 gate sensitivity run %s ===\n"
                         % subprocess.check_output(["date", "-u", "+%FT%TZ"]).decode().strip())
    gate_roundtrip()
    gate_validate_labels()
    gate_merge_verdicts()
    out = os.path.join(HERE, "gate_sensitivity.json")
    json.dump({"_meta": {"experiment": "EXP-0173",
                         "what": "each gate run unmodified, then with an injected defect it is "
                                 "claimed to protect against"},
               "runs": results}, open(out, "w"), indent=1)
    print("\nwrote", out)
    for r in results:
        print("  %-34s %-72s %s" % (r["gate"], r["mutation"][:72], r["verdict"][:60]))


if __name__ == "__main__":
    sys.exit(main())
