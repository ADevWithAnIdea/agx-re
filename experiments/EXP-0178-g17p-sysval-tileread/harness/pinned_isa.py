#!/usr/bin/env python3
"""EXP-0178 PINNED toolchain resolver.

FIELD-SWEEP-PROTOCOL / dispatch rule, 2026-08-30: *pin your own `db.json`* and
resolve it EXPLICITLY. The neo's shared `~/agxre/tools/agx-isa/db.json` is stale
and a path-search fallback silently resolved it for another experiment. A
harness must **FAIL when its pinned toolchain is absent, not quietly resolve
something else** -- so this module never searches, never falls back, and exits
non-zero if either pinned blob is missing or its sha256 does not match the value
frozen in CAPTURE_CONTRACT.json.

`isadb.py` loads `db.json` from ITS OWN directory, so pinning means pinning the
PAIR into `pinned/` and importing `pinned/isadb.py` by absolute path.
"""
import hashlib
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
PINNED = os.path.join(EXP, "pinned")

# Frozen at pre-registration. These are also written into CAPTURE_CONTRACT.json
# -> pinned_inputs_sha256, and re-verified there by analysis/selfcheck.py.
EXPECT = {
    "isadb.py":    "9cda47a1d4b3857c9f20423ab5d63c38050d37220da06bc5d2dc12a77d6ef1a8",
    "db.json":     "a77f8cfa163fcf720c0c1093e4ddc5815ceb43c218bb64a87c86d3dcf975dc22",
    "agxparse.py": "72911ee524fa1e327914445a0b38837b4a71e8525565a03f2cb7f520733c6a0f",
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def verify():
    """Hard gate. Returns the resolved {name: (path, sha)} or exits non-zero."""
    out = {}
    for name, want in EXPECT.items():
        p = os.path.join(PINNED, name)
        if not os.path.exists(p):
            sys.stderr.write(
                "FATAL: pinned toolchain blob missing: %s\n"
                "       This harness does NOT fall back to a path search.\n" % p)
            raise SystemExit(4)
        got = sha256(p)
        if got != want:
            sys.stderr.write(
                "FATAL: pinned toolchain blob CHANGED: %s\n"
                "       expected %s\n       actual   %s\n" % (p, want, got))
            raise SystemExit(4)
        out[name] = (p, got)
    return out


def load_isadb():
    """Import pinned/isadb.py by absolute path, NEVER by name."""
    verify()
    spec = importlib.util.spec_from_file_location(
        "exp0178_pinned_isadb", os.path.join(PINNED, "isadb.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    doc = json.load(open(os.path.join(PINNED, "db.json")))
    # Prove the module really bound to the pinned table, not another one.
    assert len(mod.DB) == len(doc["instructions"]), "isadb bound to a foreign db.json"
    return mod


def agxparse_path():
    verify()
    return os.path.join(PINNED, "agxparse.py")


def field_geometry(mnemonic, field):
    """(start, width, encodable_range) for a field, from the PINNED db only."""
    doc = json.load(open(os.path.join(PINNED, "db.json")))
    for i in doc["instructions"]:
        if i["mnemonic"] == mnemonic:
            for f in i["fields"]:
                if f["name"] == field:
                    return f["start"], f["width"], 1 << f["width"]
            raise KeyError("%s has no field %s in the pinned db" % (mnemonic, field))
    raise KeyError("no instruction %s in the pinned db" % mnemonic)


if __name__ == "__main__":
    r = verify()
    for k, (p, s) in sorted(r.items()):
        print("%-14s %s  %s" % (k, s, p))
    m = load_isadb()
    print("pinned isadb OK: %d instructions" % len(m.DB))
