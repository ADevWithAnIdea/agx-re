#!/usr/bin/env python3
"""Emit the complete committable EXP-0053 artifact inventory."""

import datetime
import hashlib
import json
import subprocess
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(argv):
    return subprocess.run(argv, check=True, capture_output=True, text=True, timeout=15).stdout.strip()


def main():
    artifacts = []
    for path in sorted(HERE.rglob("*")):
        relative = path.relative_to(HERE)
        if not path.is_file() or relative.as_posix() == "manifest.json" or "__pycache__" in relative.parts:
            continue
        artifacts.append({"path":relative.as_posix(),"bytes":path.stat().st_size,"sha256":digest(path)})
    result = {
        "schema":1,"experiment":"EXP-0053-m4-indirect-api-semantics",
        "generated_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "base_revision_at_manifest":command(["git","-C",str(REPO),"rev-parse","HEAD"]),
        "pre_registration":{"commit":"3dea789d","sha256":"4773ea2764b1fd3479ec2f52881ff7dcb2b1cfe0fa2e1f592db37b57db8bd34f"},
        "run_base_revision":"3dea789d6001444b9d78e7f7bcc7602d690bc169",
        "canonical_runs":["m4_20260817_run05","m4_20260817_run06"],
        "preserved_failed_runs":["m4_20260817_run01","m4_20260817_run02"],
        "preserved_noncanonical_successes":["m4_20260817_run03","m4_20260817_run04"],
        "provenance":{"categories":["HW-PROBE","OWN-SHADER source"],
          "apple_binary_introspection":"NONE","apple_auxiliary_code_inspection":"NONE",
          "compiled_shader_bytes_inspected":"NONE","command_bo_payload_tracing":"NONE",
          "pointer_following":"NONE","mutation_or_splice":"NONE"},
        "artifacts":artifacts,
    }
    (HERE / "manifest.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
