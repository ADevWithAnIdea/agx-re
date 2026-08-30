#!/usr/bin/env python3
"""EXP-0180 remote-blob verification. A SEPARATE, UNCHAINED step: run it after every push
and before every capture.

WHY (EXP-0179's stale-harness incident, and EXP-0178's verifier catching the identical
failure against ITSELF on first run -- 11 of 18 blobs matched, five stale, two missing, so
every amendment since its first push had silently failed to reach the neo):

    A FROZEN CONTRACT HASHES WHAT YOU AUTHORED, NOT WHAT THE DEVICE IS RUNNING.

Every hash in CAPTURE_CONTRACT.json can be correct while the neo executes a pre-amendment
harness. This experiment has two amendments, a subclassed runner and a pinned db.json that
must travel with it, so it is exactly the profile that bites.

Compares the sha256 of every file in CAPTURE_CONTRACT.json:authored_source_sha256 against
the sha256 the NEO computes for its own copy. Exit code 1 means DO NOT CAPTURE.
Writes work/remote_verify.json. Uses SSHPASS only; the password is never written anywhere.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
NEO = os.environ.get("NEO", "192.168.10.243")
USR = os.environ.get("NEO_USER", "user")
REMOTE = "agxre/EXP-0180"


def main():
    if not os.environ.get("SSHPASS"):
        print("SSHPASS is not set", file=sys.stderr)
        return 2
    want = json.loads((EXP / "CAPTURE_CONTRACT.json").read_text())["authored_source_sha256"]["files"]
    paths = sorted(want)
    cmd = "cd %s && shasum -a 256 %s 2>&1" % (REMOTE, " ".join("'%s'" % p for p in paths))
    r = subprocess.run(["sshpass", "-e", "ssh", "-o", "StrictHostKeyChecking=no",
                        "-o", "ConnectTimeout=20", "%s@%s" % (USR, NEO), cmd],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
    got = {}
    for ln in r.stdout.decode().splitlines():
        parts = ln.split(None, 1)
        if len(parts) == 2 and len(parts[0]) == 64:
            got[parts[1].strip()] = parts[0]
    rows, ok = [], True
    for p in paths:
        g = got.get(p)
        state = "MATCH" if g == want[p] else ("MISSING" if g is None else "STALE")
        ok &= (state == "MATCH")
        rows.append({"path": p, "state": state, "local": want[p][:16],
                     "remote": (g or "-")[:16]})
    (EXP / "work" / "remote_verify.json").write_text(json.dumps(
        {"neo": NEO, "remote_dir": REMOTE, "all_match": ok, "n": len(paths),
         "n_match": sum(1 for x in rows if x["state"] == "MATCH"), "rows": rows,
         "stderr": r.stderr.decode()[-400:]}, indent=1, sort_keys=True))
    for x in rows:
        if x["state"] != "MATCH":
            print("%-8s %-34s local=%s remote=%s" % (x["state"], x["path"], x["local"], x["remote"]))
    print("%d/%d blobs match on the neo -- %s"
          % (sum(1 for x in rows if x["state"] == "MATCH"), len(rows),
             "OK TO CAPTURE" if ok else "DO NOT CAPTURE"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
