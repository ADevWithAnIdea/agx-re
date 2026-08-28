import json, subprocess, sys, os, shutil
sys.path.insert(0, "harness")
import casematrix as CM

BIN = "work/bin_test"
OUT = "work/diag"
shutil.rmtree(OUT, ignore_errors=True)
os.makedirs(OUT, exist_ok=True)

def run_case(c, tag):
    cfgp = f"{OUT}/{c['name']}_{tag}.cfg.json"
    resp = f"{OUT}/{c['name']}_{tag}.res.json"
    dumpdir = f"{OUT}/{c['name']}_{tag}.dumps"
    with open(cfgp, "w") as f: json.dump(c, f)
    env = dict(os.environ)
    env["DYLD_INSERT_LIBRARIES"] = os.path.abspath(f"{BIN}/wtrace.dylib")
    env["WTRACE_LOG"] = os.path.abspath(f"{OUT}/{c['name']}_{tag}.trace.log")
    env["WTRACE_DUMP_DIR"] = os.path.abspath(dumpdir)
    r = subprocess.run([os.path.abspath(f"{BIN}/probe"), cfgp, resp, "--dump"],
                        capture_output=True, text=True, timeout=30, env=env)
    return r.returncode, dumpdir, resp

for c in CM.CASES:
    rc1, d1, res1 = run_case(c, "r1")
    rc2, d2, res2 = run_case(c, "r2")
    # locate dump00 subdir in each
    def inv(d):
        sub = os.path.join(d, "dump00")
        p = os.path.join(sub, "inventory.tsv")
        rows = {}
        if os.path.exists(p):
            with open(p) as f:
                next(f)
                for line in f:
                    parts = line.rstrip("\n").split("\t")
                    va, size, handle, role, captured, sha, tries = parts
                    rows[(va, role)] = (size, captured, sha)
        return sub, rows
    sub1, rows1 = inv(d1)
    sub2, rows2 = inv(d2)
    named1 = {k: v for k, v in rows1.items() if k[1] not in ("unclassified", "unnamed-descriptor-candidate")}
    named2 = {k: v for k, v in rows2.items() if k[1] not in ("unclassified", "unnamed-descriptor-candidate")}
    print(f"=== {c['name']} rc=({rc1},{rc2}) named_roles_r1={sorted(v[1] for v in named1)} ===")
    if set(named1) != set(named2):
        print("   ROLE SET MISMATCH", set(named1) ^ set(named2))
    for k in sorted(set(named1) & set(named2)):
        va, role = k
        s1 = named1[k]; s2 = named2[k]
        if s1[0] != s2[0]:
            print(f"   SIZE MISMATCH {role}@{va}: {s1[0]} vs {s2[0]}")
        if s1[1] != s2[1]:
            print(f"   CAPTURED FLAG MISMATCH {role}@{va}: {s1[1]} vs {s2[1]}")
        if s1[2] != s2[2] and s1[1] == '1' and s2[1] == '1':
            # byte-diff the actual bin files
            f1 = os.path.join(sub1, f"va_{va[2:]}.bin")
            f2 = os.path.join(sub2, f"va_{va[2:]}.bin")
            if os.path.exists(f1) and os.path.exists(f2):
                b1 = open(f1, "rb").read(); b2 = open(f2, "rb").read()
                diffs = [i for i in range(min(len(b1), len(b2))) if b1[i] != b2[i]]
                print(f"   HASH DIFF {role}@{va}: len={len(b1)}/{len(b2)} ndiff={len(diffs)} first_offsets={diffs[:20]}")
