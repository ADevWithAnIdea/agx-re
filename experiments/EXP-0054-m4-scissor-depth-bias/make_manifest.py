#!/usr/bin/env python3
"""Generate the complete committable EXP-0054 artifact manifest."""

from __future__ import annotations

import datetime
import hashlib
import json
import subprocess
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
RUNS = {"m4_20260817_run01","m4_20260817_run02","m4_20260817_run03","m4_20260817_run04"}
EXPECTED_DIRS = {"analysis","harness","raw"} | {f"raw/{run_id}" for run_id in RUNS}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(argv: list[object]) -> str:
    return subprocess.run([str(x) for x in argv],check=True,capture_output=True,
                          text=True,timeout=15).stdout.strip()


def main() -> None:
    entries = list(HERE.rglob("*"))
    for path in entries:
        if path.is_symlink():
            raise RuntimeError(f"symlink forbidden: {path.relative_to(HERE)}")
        if not (path.is_file() or path.is_dir()):
            raise RuntimeError(f"special entry forbidden: {path.relative_to(HERE)}")
    directories = {path.relative_to(HERE).as_posix() for path in entries if path.is_dir()}
    if directories != EXPECTED_DIRS:
        raise RuntimeError(f"unexpected directory set: {sorted(directories)}")
    artifacts = []
    for path in sorted(entries):
        relative = path.relative_to(HERE)
        if not path.is_file() or relative.as_posix() == "manifest.json":
            continue
        artifacts.append({"path":relative.as_posix(),"bytes":path.stat().st_size,
                          "sha256":digest(path)})
    result = {
        "schema":1,
        "experiment":"EXP-0054-m4-scissor-depth-bias",
        "generated_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "base_revision_at_manifest":command(["git","-C",REPO,"rev-parse","HEAD"]),
        "pre_registrations":[
            {"commit":"13d200c5aeae67182b4555c51eb728a413a954aa",
             "path":"PRE_REGISTRATION.md",
             "sha256":"7bff360264354961cd0d22f043e65a0d800f4d23efd1b8c516e9ee564cad8953"},
            {"commit":"7a7fde9c53a7765accb62c5896a3e8c404b4e0d8",
             "path":"PRE_REGISTRATION_AMENDMENT.md",
             "sha256":"c8ccd2144a0423a9a48fd3f7754228e4665f931996cbeb1a5406114782379517"},
            {"commit":"4c43187a807e8323fc6227471795f2d868d578de",
             "path":"PRE_REGISTRATION_FOLLOWUP.md",
             "sha256":"11b52fec26751be0752340786b98573ba16e50fcfef9741531f176ec7e7c640d"},
        ],
        "run_revisions":{"initial":"7a7fde9c53a7765accb62c5896a3e8c404b4e0d8",
                         "final":"4c43187a807e8323fc6227471795f2d868d578de"},
        "canonical_runs":["m4_20260817_run03","m4_20260817_run04"],
        "preserved_initial_successes":["m4_20260817_run01","m4_20260817_run02"],
        "source_versions":{
            "initial":{"harness":"c8bbbf188009884b70e099a26453802b7104b2841edd6b7c641c453f125e8101",
                       "runner":"5757f632e6be65c0276a667093d69f8923e0bfd4a0149c3a3554e4b1b6e3acd2"},
            "final":{"harness":"898352c0b82b5bb5055e6907b890ba5047c1ec87751ca6a5e4fb935fb31a5b78",
                     "runner":"4717f025f284bc7ae5c41e03d18c51336e3b0c6875c66c424239163409e313c6"},
        },
        "target":{"qualification":"local M4/G16G-class only; A18 Pro untested",
                  "model":"Mac16,10","os":"macOS 26.6.2 (25G82)"},
        "provenance":{"categories":["HW-PROBE","OWN-SHADER source","PUBLIC"],
            "apple_binary_introspection":"NONE","apple_auxiliary_code_inspection":"NONE",
            "compiled_shader_bytes_inspected":"NONE","command_or_state_bo_payload_tracing":"NONE",
            "pointer_following":"NONE","generic_memory_scan":"NONE","mutation_splice_replay":"NONE"},
        "artifacts":artifacts,
    }
    (HERE/"manifest.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")


if __name__ == "__main__":
    main()
