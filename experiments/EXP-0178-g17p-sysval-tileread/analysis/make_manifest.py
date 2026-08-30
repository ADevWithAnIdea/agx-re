#!/usr/bin/env python3
"""EXP-0178 manifest: target/tool/revision metadata plus artifact hashes."""
import hashlib, json, os, subprocess, time

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 16), b""):
            h.update(c)
    return h.hexdigest()


def main():
    c = json.load(open(os.path.join(EXP, "CAPTURE_CONTRACT.json")))
    arts, raws = {}, {}
    for root, dirs, files in os.walk(EXP):
        dirs[:] = [d for d in dirs if d not in ("work", "__pycache__", ".git")]
        for fn in sorted(files):
            p = os.path.join(root, fn)
            rel = os.path.relpath(p, EXP)
            (raws if rel.startswith("raw/") else arts)[rel] = sha(p)
    env = {}
    for rid in sorted(os.listdir(os.path.join(EXP, "raw"))):
        f = os.path.join(EXP, "raw", rid, "00_env.json")
        if os.path.exists(f):
            e = json.load(open(f))
            env[rid] = {k: e.get(k) for k in ("utc", "host", "sw_vers", "xcrun",
                                              "python", "pinned_db_instructions")}
            env[rid]["records"] = sum(1 for _ in open(
                os.path.join(EXP, "raw", rid, "sweep.jsonl")))
    m = {
        "experiment": "EXP-0178-g17p-sysval-tileread",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "target": c["target"],
        "clean_room": c["clean_room"],
        "capture_contract_sha256": sha(os.path.join(EXP, "CAPTURE_CONTRACT.json")),
        "repo_revision_at_freeze": c["repo_revision_at_freeze"],
        "repo_revision_now": subprocess.run(["git", "rev-parse", "HEAD"],
                                            capture_output=True, text=True,
                                            cwd=EXP).stdout.strip(),
        "pinned_inputs_sha256": c["pinned_inputs_sha256"],
        "gated_runs": c["gated_runs"],
        "defective_runs": c.get("defective_runs", {}),
        "amendments": [a["id"] for a in c.get("amendments", [])],
        "run_environment": env,
        "artifacts": arts,
        "raw": raws,
    }
    json.dump(m, open(os.path.join(EXP, "manifest.json"), "w"), indent=1, sort_keys=True)
    print("manifest: %d artifacts, %d raw files, runs %s"
          % (len(arts), len(raws), sorted(env)))


if __name__ == "__main__":
    main()
