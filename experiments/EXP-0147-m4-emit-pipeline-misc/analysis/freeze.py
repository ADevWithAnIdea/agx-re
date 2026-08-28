#!/usr/bin/env python3
"""Freeze the authored inputs into manifest.json (run before the gated runs)."""
import hashlib, json, os, subprocess, sys, time
EXP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.abspath(os.path.join(EXP, "..", ".."))
FILES = ["kernels/pipe_render.metal", "kernels/pipe_compute.metal",
         "harness/rendersweep.m", "harness/shdump2.m", "harness/run.py",
         "harness/rsdrv.py", "harness/sweepplan.py", "PRE_REGISTRATION.md"]
TOOLS = ["tools/shdump/shdump.m", "tools/shdump/agxparse.py",
         "tools/agxtest/agxrun_persist.m", "tools/agxtest/persistrun.py",
         "tools/agx-isa/db.json", "tools/agx-isa/validation.json"]


def sha(p):
    with open(p, "rb") as f: return hashlib.sha256(f.read()).hexdigest()


def main():
    m = {
        "experiment": "EXP-0147-m4-emit-pipeline-misc",
        "frozen_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "target": {"device": "Apple M4 (G16G)", "gpu_cores": 10,
                   "os": subprocess.run(["sw_vers", "-productVersion"], capture_output=True, text=True).stdout.strip(),
                   "build": subprocess.run(["sw_vers", "-buildVersion"], capture_output=True, text=True).stdout.strip(),
                   "note": "local host only; A18 Pro is hands-off"},
        "git_rev_at_freeze": subprocess.run(["git", "-C", REPO, "rev-parse", "HEAD"],
                                            capture_output=True, text=True).stdout.strip(),
        "git_dirty_at_freeze": bool(subprocess.run(["git", "-C", REPO, "status", "--porcelain"],
                                                   capture_output=True, text=True).stdout.strip()),
        "authored_inputs": {f: sha(os.path.join(EXP, f)) for f in FILES},
        "reference_tools_unmodified": {f: sha(os.path.join(REPO, f)) for f in TOOLS},
        "concurrency": "EXP-0140 and EXP-0144 were sweeping the same GPU during these runs; "
                       "see RESULTS.md section on shared-device contamination.",
        "clean_room": {"provenance": "OWN-SHADER + HW-PROBE",
                       "apple_binary_introspection": "NONE"},
    }
    with open(os.path.join(EXP, "manifest.json"), "w") as f:
        json.dump(m, f, indent=2, sort_keys=True); f.write("\n")
    print(json.dumps(m, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
