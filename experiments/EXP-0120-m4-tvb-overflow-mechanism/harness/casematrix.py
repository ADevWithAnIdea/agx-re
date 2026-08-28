"""Single source of truth for EXP-0120's frozen case matrix.

Loads experiments/EXP-0120-m4-tvb-overflow-mechanism/CAPTURE_CONTRACT.json (the
frozen pre-registration contract) and expands it into concrete per-case dicts.
Never hand-duplicate the numbers here; always derive from the contract so
run_sweep.py and analysis/analyze.py cannot silently drift from what was
pre-registered.
"""
import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
EXP_ROOT = os.path.dirname(HERE)
REPO_ROOT = os.path.abspath(os.path.join(EXP_ROOT, "..", ".."))
CONTRACT_PATH = os.path.join(EXP_ROOT, "CAPTURE_CONTRACT.json")
BIN = os.path.join(REPO_ROOT, "experiments", "EXP-0118-a18-pro-partial-render-workload",
                    "build", "partial_render")
IOTRACE_DYLIB = os.path.join(HERE, "build", "iotrace.dylib")


def load_contract():
    with open(CONTRACT_PATH) as f:
        return json.load(f)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_pins(contract):
    """Raise if any pinned blob hash no longer matches. Called before any case runs."""
    problems = []
    for relpath, want in contract["pinned_blob_hashes_sha256"].items():
        full = os.path.join(REPO_ROOT, relpath)
        if not os.path.exists(full):
            problems.append(f"MISSING: {relpath}")
            continue
        got = sha256_file(full)
        if got != want:
            problems.append(f"HASH MISMATCH: {relpath} want={want} got={got}")
    if not os.path.exists(IOTRACE_DYLIB):
        problems.append(f"MISSING: {IOTRACE_DYLIB} (run harness/build_iotrace.sh first)")
    return problems


def sweep_A_cases(contract):
    a = contract["sweeps"]["A_timing"]
    cases = []
    slope = a["small_N_slope_method"]
    for n in slope["N"]:
        for tag, s in (("s1", slope["S1"]), ("s2", slope["S2"])):
            cases.append({
                "sweep": "A", "case_id": f"A-slope-N{n}-{tag}",
                "mode": a["mode"], "width": a["width"], "height": a["height"],
                "N": n, "S": s, "interposer": False, "extra_env": {},
                "group": f"A-slope-N{n}", "role": tag,
            })
    single = a["large_N_single"]
    for n in single["N"]:
        cases.append({
            "sweep": "A", "case_id": f"A-single-N{n}",
            "mode": a["mode"], "width": a["width"], "height": a["height"],
            "N": n, "S": single["S"], "interposer": False, "extra_env": {},
            "group": f"A-single-N{n}", "role": "single",
        })
    return cases


def sweep_B_cases(contract):
    b = contract["sweeps"]["B_mechanism_triangle_axis"]
    cases = []
    for n in b["N"]:
        cases.append({
            "sweep": "B", "case_id": f"B-N{n}",
            "mode": b["mode"], "width": b["width"], "height": b["height"],
            "N": n, "S": b["S"], "interposer": True, "extra_env": dict(b["env"]),
            "group": f"B-N{n}", "role": "mechanism",
        })
    return cases


def sweep_C_cases(contract):
    c = contract["sweeps"]["C_mechanism_dimension_axis"]
    cases = []
    for wh in c["WH"]:
        cases.append({
            "sweep": "C", "case_id": f"C-WH{wh}",
            "mode": c["mode"], "width": wh, "height": wh,
            "N": c["N"], "S": c["S"], "interposer": True, "extra_env": dict(c["env"]),
            "group": f"C-WH{wh}", "role": "mechanism",
        })
    return cases


def sweep_D_cases(contract):
    d = contract["sweeps"]["D_limits_exploratory_single_shot"]
    cases = []
    for i, spec in enumerate(d["cases"]):
        cases.append({
            "sweep": "D", "case_id": f"D-{spec['mode']}-N{spec['N']}",
            "mode": spec["mode"], "width": spec["width"], "height": spec["height"],
            "N": spec["N"], "S": spec["S"], "interposer": spec["interposer"],
            "extra_env": {"IOTRACE_MAX_MAP": "0x4000", "G17P_DUMP_BEFORE_COMMIT": "1"} if spec["interposer"] else {},
            "group": f"D-{spec['mode']}-N{spec['N']}", "role": "limits",
        })
    sanity = d["post_case_sanity_check"]
    sanity_case = {
        "sweep": "D", "case_id": "D-sanity-check",
        "mode": sanity["mode"], "width": sanity["width"], "height": sanity["height"],
        "N": sanity["N"], "S": sanity["S"], "interposer": False, "extra_env": {},
        "group": "D-sanity-check", "role": "sanity",
    }
    return cases, sanity_case


def all_cases(contract):
    cases = []
    cases += sweep_A_cases(contract)
    cases += sweep_B_cases(contract)
    cases += sweep_C_cases(contract)
    d_cases, sanity = sweep_D_cases(contract)
    cases += d_cases
    return cases, sanity


if __name__ == "__main__":
    c = load_contract()
    problems = verify_pins(c)
    if problems:
        print("PIN VERIFICATION FAILED:")
        for p in problems:
            print(" -", p)
        raise SystemExit(1)
    cases, sanity = all_cases(c)
    print(f"OK: {len(cases)} cases + 1 sanity-check template loaded, all pins verified.")
    from collections import Counter
    print(Counter(x["sweep"] for x in cases))
