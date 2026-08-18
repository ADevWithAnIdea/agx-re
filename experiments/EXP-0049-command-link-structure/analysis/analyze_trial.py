#!/usr/bin/env python3
"""Analyze one EXP-0049 trial using only its exact preclassified engine BOs."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct

ALLOW = {
    "va_100000b8000": (0x100000B8000, "cdm-source"),
    "va_10000158000": (0x10000158000, "cdm-target"),
    "va_18000": (0x18000, "vdm-source"),
    "va_88000": (0x88000, "vdm-target"),
}
ENGINE = {
    "cdm": {"source": "va_100000b8000", "target": "va_10000158000",
            "link": (0x20000100, 0x00158000)},
    "vdm": {"source": "va_18000", "target": "va_88000",
            "link": (0x80000000, 0x00088000)},
}

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def load_allowed(state: Path, stem: str) -> bytes | None:
    binary = state / f"{stem}.bin"
    meta = state / f"{stem}.meta"
    if binary.exists() != meta.exists():
        raise AssertionError(f"binary/meta pair mismatch for {stem}")
    if not binary.exists():
        return None
    va, role = ALLOW[stem]
    fields = dict(line.split("=", 1) for line in meta.read_text().splitlines())
    if int(fields["gpu_va"], 0) != va:
        raise AssertionError(f"metadata VA mismatch for {stem}")
    if fields.get("fixed_allowlist") != "1" or fields.get("pointer_following") != "0":
        raise AssertionError(f"clean-room metadata mismatch for {stem}")
    if fields.get("command_mutation") != "0":
        raise AssertionError(f"mutation marker mismatch for {stem}")
    data = binary.read_bytes()
    if len(data) != int(fields["read_size"], 0):
        raise AssertionError(f"read-size mismatch for {stem}")
    if len(data) > 0x10000 or len(data) > int(fields["allocation_size"], 0):
        raise AssertionError(f"read cap mismatch for {stem}")
    return data

def pair_offsets(data: bytes, pair: tuple[int, int]) -> list[int]:
    needle = struct.pack("<II", *pair)
    return [off for off in range(0, len(data) - 7, 4)
            if data[off:off+8] == needle]

def vdm_draws(data: bytes) -> list[int]:
    result = []
    for off in range(0, len(data) - 15, 4):
        w0, count, instances, zero = struct.unpack_from("<4I", data, off)
        if (w0 >> 16) == 0x61C4 and count in (3, 6) and instances == 1 and zero == 0:
            result.append(off)
    return result

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trial", type=Path, required=True)
    ap.add_argument("--engine", choices=("cdm", "vdm"), required=True)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    trial = args.trial.resolve()
    state = trial / "state"
    expected_names = {f"{stem}.{suffix}" for stem in ALLOW for suffix in ("bin", "meta")}
    actual_names = {p.name for p in state.iterdir() if p.is_file()}
    if not actual_names <= expected_names:
        raise AssertionError(f"nonallowlisted state payloads: {sorted(actual_names-expected_names)}")
    spec = ENGINE[args.engine]
    source = load_allowed(state, spec["source"])
    if source is None:
        raise AssertionError(f"missing preclassified {args.engine} source")
    target = load_allowed(state, spec["target"])
    links = pair_offsets(source, spec["link"])
    if len(links) > 1:
        raise AssertionError(f"multiple known first-segment links: {links}")
    if bool(links) != (target is not None):
        raise AssertionError("known link/independently allowlisted target presence mismatch")
    run = json.loads((trial / "run.json").read_text())
    stdout = run.get("stdout", "")
    variant = re.search(r"^VARIANT name=(\S+) engine=(\S+) count=(\d+) mutation=0$", stdout, re.M)
    command = re.search(r"^COMMAND status=(\d+) error=(.*)$", stdout, re.M)
    result = re.search(r"^RESULT ok=(\d+)$", stdout, re.M)
    if not variant or not command or not result:
        raise AssertionError("unparsed harness output")
    if run.get("exit") != 0 or run.get("timeout", False) or command.groups() != ("4", "none") or result[1] != "1":
        raise AssertionError("unsuccessful live workload")
    if variant[2] != args.engine:
        raise AssertionError("engine mismatch")
    out = {
        "schema": 1,
        "trial": trial.name,
        "variant": variant[1],
        "engine": args.engine,
        "count": int(variant[3]),
        "command_status": int(command[1]),
        "readback_ok": True,
        "known_link": bool(links),
        "known_link_words": [f"0x{x:08x}" for x in spec["link"]],
        "link_offsets": [f"0x{x:x}" for x in links],
        "source": {"gpu_va": f"0x{ALLOW[spec['source']][0]:x}",
                   "bytes": len(source), "sha256": sha(source)},
        "target": None if target is None else {
            "gpu_va": f"0x{ALLOW[spec['target']][0]:x}",
            "bytes": len(target), "sha256": sha(target),
        },
    }
    if args.engine == "vdm":
        out["source_draw_packets"] = len(vdm_draws(source))
        out["target_draw_packets"] = 0 if target is None else len(vdm_draws(target))
    rendered = json.dumps(out, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered)
    else:
        print(rendered, end="")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
