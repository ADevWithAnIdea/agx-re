#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""evidence_index.py -- open the RAW and re-derive per-(instruction, field) facts.

Built for EXP-0209 to serve `promotion_check.py` (RE_EXPERIMENT_PROCESS_CORRECTIONS
section 8) and `dashboards.py` (section 9). It is deliberately NOT a label reader: it
never looks at validation.json. It walks an experiment's committed artifacts and
reports what the raw actually contains, so a promotion gate can inspect evidence
rather than citations.

WHY IT IS NOT A .jsonl/`instr`/`field` SCANNER
----------------------------------------------
The corpus is in mixed formats. 29 cited experiments have ZERO records under the
naive "`.jsonl` with `instr`+`field` keys" assumption, because the whole pre-EXP-0138
era writes `.txt`/`.json`/`.hex` or unkeyed `.jsonl`. A field-name index over that
manufactures a FALSE ABSENCE, which is how six validation.json notes came to claim
evidence did not exist (EXP-0197). So this indexer uses four independent keyings,
lifted from experiments/EXP-0197-citation-clause-audit/analysis/scan.py, and reports
each SEPARATELY so a "no" from one is never read as a "no" overall:

  K1 named      record with instr == <mnem> and field == <field>
  K2 byte-span  record with instr == <mnem>, field null/`__`-prefixed, and a
                byte_index inside the field's db.json byte span
  K3 grouping   any record whose arm/carrier/group/case string names the field
                or the mnemonic
  K4 encodings  hex blobs harvested from ANY file format, tokenized with our own
                disassembler (tools/agx-isa/isadb.py). Expensive, so it is opt-in
                (`--deep`) and cached; the promotion checker calls it only for rows
                where K1..K3 found nothing.

Absence under K1..K3 with a nonzero non-record file count is reported as
`format-unreadable`, NOT as zero evidence.

WHAT IT EXTRACTS PER (mnemonic, field)
--------------------------------------
Gate A (actual-byte ledger): requested value, actual bytes, and the value DECODED
back out of those bytes at db.json's own (start, width). `ledger_agree` /
`ledger_disagree` is the Gate A comparison; `distinct_actual_field_values` is the
aliasing check that DEF-0166-1 needed (a sweep can dispatch 256 values while the
hardware sees 8 distinct encodings).

Gate B (detection power): control records -- field names matching `__ladder*`,
`__fals*`, `__ctl_*`, `__power_*`, `__sens_*` -- kept in their own cell per
instruction, never mixed into the swept field's counts.

Gate C (semantics): a semantic check is ONLY a record carrying a host prediction
compared against the observation (`sem_match`, `oracle_match`, or a `predict` that is
not one of the liveness-ladder words). `predict: "move"` is a LIVENESS ladder
prediction and is counted as such, never as a semantic check -- that conflation is
the EXP-0169 Tier-2 error section 3 Gate C exists to prevent.

Gate E (contamination): `victim`, `sentinel_bad`, `restarted`, `timed_out` and the
`measurement_failure` bucket are counted separately from hardware outcomes. Our own
disassembler failing (`undecodable`) is a measurement failure, not hardware movement.

Hard outcomes are never counted as valid payloads. `V` (distinct valid payloads) is
the Case-C test from tools/agx-isa/wave_audit.py: V <= 1 over many legal values means
the field ran legally and was INDISTINGUISHABLE.

CLEAN ROOM: reads only this repository's own committed artifacts.

Usage:
    python3 tools/agx-isa/evidence_index.py --build            # all experiments
    python3 tools/agx-isa/evidence_index.py --build EXP-0169   # one slug prefix
    python3 tools/agx-isa/evidence_index.py --show EXP-0169 falu2 opsel
    python3 tools/agx-isa/evidence_index.py --selftest
"""
import argparse
import collections
import glob
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
EXPS = os.path.join(ROOT, "experiments")
CACHE = os.path.join(EXPS, "EXP-0209-dashboards", "work", "index")

# ---------------------------------------------------------------- vocabularies

# Outcomes that are NOT a valid payload. Keeping this list separate from the
# semantic buckets is the point: wave_audit.py found two gates in this corpus that
# scored a GPU fault, and our own disassembler failing to decode, as movement.
HARD = {"fault", "no_draw", "hang", "undecodable", "timeout", "timed_out",
        "cmdbuf_error", "wedge", "malformed", "innocent_victim", "crash",
        "measurement_failure", "invalid_run", "baseline_fail"}

# Section 3 Gate C requires the predictor to distinguish at least these buckets.
BUCKETS = ("correct", "coherent_other", "silent", "fault", "measurement_failure")
_BUCKET_OF = {
    "ok": "correct", "match": "correct", "correct": "correct", "pass": "correct",
    "hit": "correct", "expected": "correct",
    "wrong_value": "coherent_other", "different": "coherent_other",
    "mismatch": "coherent_other", "other": "coherent_other",
    "silent_zero": "silent", "no_write": "silent", "not_written": "silent",
    "zero": "silent", "no_store": "silent", "no_draw": "silent", "dead": "silent",
    "fault": "fault", "hang": "fault", "cmdbuf_error": "fault", "wedge": "fault",
    "crash": "fault", "reject": "fault", "rejected": "fault",
    "timeout": "measurement_failure", "timed_out": "measurement_failure",
    "malformed": "measurement_failure", "undecodable": "measurement_failure",
    "innocent_victim": "measurement_failure", "invalid_run": "measurement_failure",
    "measurement_failure": "measurement_failure", "baseline_fail": "measurement_failure",
    "error": "measurement_failure",
}

# `predict` values that are LIVENESS ladder/falsifier predictions, not semantics.
LIVENESS_PREDICTIONS = {"", "none", "move", "must_move", "not_ok", "unknown", "null"}

# Control-field prefixes: Gate B detection-power arms. Never mixed into a swept
# field's own counts.
CTRL_RX = re.compile(r"^__(ladder|fals|falsifier|ctl|power|sens|baseline|control)")

INSTR_KEYS = ("instr", "mnem", "mnemonic", "insn", "opcode_name")
FIELD_KEYS = ("field", "fld", "field_name")
VALUE_KEYS = ("value", "val", "requested_value")
BYTES_KEYS = ("bytes", "hex", "enc", "encoding", "actual_bytes", "instr_bytes")
GROUPKEYS = ("group", "carrier", "arm", "name", "item", "case", "case_name",
             "kernel", "label", "test", "op", "tag", "func", "function", "family")

SKIPDIRS = {"__pycache__", ".git", "node_modules"}
RECORD_EXT = {".jsonl", ".json"}
TEXT_EXT = {".txt", ".log", ".hex", ".out", ".stdout", ".stderr", ".md", ".meta",
            ".trace"}
BINARY_EXT = {".png", ".jpg", ".gz", ".zip", ".bin", ".o", ".dylib", ".metallib",
              ".air", ".pyc"}

SETCAP = 4096          # distinct-value sets are capped; counts above this do not
                       # change any threshold in the gates that consume them.

# ------------------------------------------------------------------- utilities


def _target_of_run(name):
    """Which silicon a run directory names. Absence is reported, never guessed."""
    n = (name or "").lower()
    if "g17p" in n or "a18" in n or "neo" in n:
        return "G17P"
    if "g16g" in n or re.search(r"(^|[^a-z0-9])m4([^a-z0-9]|$)", n):
        return "G16G"
    if "g17g" in n or re.search(r"(^|[^a-z0-9])m5([^a-z0-9]|$)", n):
        return "M5"
    return None


def _first(rec, keys):
    for k in keys:
        if k in rec and rec[k] is not None:
            return rec[k]
    return None


def _outcome_of(rec):
    o = rec.get("outcome")
    if o is None:
        at = rec.get("attempts")
        if isinstance(at, list) and at and isinstance(at[0], dict):
            o = at[0].get("outcome") or at[0].get("status")
    if o is None:
        o = rec.get("verdict") or rec.get("exec_status") or rec.get("status")
    return str(o).lower() if o is not None else None


def _is_hard(rec, outcome):
    if outcome in HARD:
        return True
    for k in ("outcome", "status", "class", "fault_class", "verdict"):
        v = rec.get(k)
        if isinstance(v, str) and v.lower() in HARD:
            return True
    return False


def bucket_of(outcome):
    if outcome is None:
        return None
    return _BUCKET_OF.get(outcome.lower())


def _digest(obj):
    try:
        return hashlib.blake2b(json.dumps(obj, sort_keys=True, default=str).encode(),
                               digest_size=8).hexdigest()
    except Exception:
        return None


def load_db(path=None):
    db = json.load(open(path or os.path.join(HERE, "db.json")))
    spec = {}
    for i in db["instructions"]:
        spec[i["mnemonic"]] = {
            "length": i.get("length"),
            "match": i.get("match") or [],
            "emitter_role": i.get("emitter_role"),
            "fields": {f["name"]: (f["start"], f["width"])
                       for f in i.get("fields", [])},
        }
    return spec


# --------------------------------------------------------------- the cell type


def _new_cell():
    return {
        "records": 0,
        "in_raw": 0,               # records that came from raw/ (append-only evidence)
        "keying": collections.Counter(),        # k1 / k2 / k3
        "runs": collections.Counter(),
        "raw_runs": collections.Counter(),      # raw/ run dirs only
        "targets": collections.Counter(),
        "req_values": set(),
        "actual_bytes": set(),
        "actual_field_values": set(),
        "ledger_records": 0,       # record carried actual bytes
        "ledger_decoded": 0,       # bytes decoded at db.json's (start,width)
        "ledger_agree": 0,
        "ledger_disagree": 0,
        "ledger_examples": [],
        "outcomes": collections.Counter(),
        "hard": collections.Counter(),
        "valid_payloads": set(),
        "oracle_digests": set(),
        "sem_checks": 0,
        "sem_true": 0,
        "sem_false": 0,
        "sem_buckets": collections.Counter(),
        "liveness_predictions": 0,
        "victim": 0,
        "sentinel_bad": 0,
        "contamination": collections.Counter(),
        "files": collections.Counter(),
        "capped": False,
    }


def _add(cell, s, v):
    if len(cell[s]) < SETCAP:
        cell[s].add(v)
    else:
        cell["capped"] = True


def _finish(cell):
    out = dict(cell)
    for s in ("req_values", "actual_bytes", "actual_field_values",
              "valid_payloads", "oracle_digests"):
        out["n_" + s] = len(cell[s])
        out[s] = sorted(list(cell[s]))[:64]
    for c in ("keying", "runs", "raw_runs", "targets", "outcomes", "hard",
              "sem_buckets", "contamination", "files"):
        out[c] = dict(cell[c])
    out["V"] = out["n_valid_payloads"]
    out["L"] = out["n_req_values"]
    return out


# ------------------------------------------------------------------ the walker


def iter_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIPDIRS]
        for fn in sorted(filenames):
            ext = os.path.splitext(fn)[1].lower()
            if ext in BINARY_EXT:
                continue
            p = os.path.join(dirpath, fn)
            try:
                if os.path.getsize(p) == 0:
                    continue
            except OSError:
                continue
            yield p, ext


def _run_of(path, expdir):
    rel = os.path.relpath(path, expdir)
    parts = rel.split(os.sep)
    if parts and parts[0] == "raw" and len(parts) > 2:
        return parts[1]
    return parts[0] if parts else "?"


class Indexer(object):
    def __init__(self, spec):
        self.spec = spec
        # byte -> set of (mnem, field) for the K2 span keying
        self.byte_map = collections.defaultdict(set)
        for m, s in spec.items():
            for f, (st, w) in s["fields"].items():
                for b in range(st // 8, (st + w - 1) // 8 + 1):
                    self.byte_map[(m, b)].add(f)

    # -- Gate A -----------------------------------------------------------
    def decode_actual(self, mnem, field, blob):
        """Value of <field> read back out of the ACTUAL dispatched bytes.

        Returns (value, why). `why` is None on success and names the reason on
        failure, so 'no ledger' and 'ledger disagreed' never collapse together.
        """
        s = self.spec.get(mnem)
        if not s:
            return None, "mnemonic-not-in-db"
        span = s["fields"].get(field)
        if not span:
            return None, "field-not-in-db"
        if not isinstance(blob, str):
            return None, "no-bytes"
        h = blob.strip().lower()
        if h.startswith("0x"):
            h = h[2:]
        h = re.sub(r"[^0-9a-f]", "", h)
        if not h or len(h) % 2:
            return None, "unparsable-bytes"
        try:
            buf = bytes.fromhex(h)
        except ValueError:
            return None, "unparsable-bytes"
        L = s["length"] or len(buf)
        if len(buf) < L:
            return None, "bytes-shorter-than-instruction"
        st, w = span
        v = int.from_bytes(buf[:L], "little")
        return (v >> st) & ((1 << w) - 1), None

    # -- one record -------------------------------------------------------
    def handle(self, rec, cells, ctrl_cells, meta, where, run, target,
               in_raw=False):
        if not isinstance(rec, dict):
            return
        if in_raw:
            rec = dict(rec)
            rec["_in_raw"] = True
        mnem = _first(rec, INSTR_KEYS)
        if isinstance(mnem, str):
            meta["instr_names_seen"][mnem] += 1
        field = _first(rec, FIELD_KEYS)
        if isinstance(field, str):
            meta["field_names_seen"][field] += 1
        for gk in GROUPKEYS:
            gv = rec.get(gk)
            if isinstance(gv, str) and gv:
                meta["group_strings"].add("%s=%s" % (gk, gv[:64]))
        if not isinstance(mnem, str) or mnem not in self.spec:
            return
        meta["instr_records"][mnem] += 1

        outcome = _outcome_of(rec)
        hard = _is_hard(rec, outcome)
        bucket = bucket_of(outcome)
        value = _first(rec, VALUE_KEYS)
        blob = _first(rec, BYTES_KEYS)
        observed = rec.get("observed", rec.get("regs", rec.get("record")))
        oracle = rec.get("oracle")

        # Gate B: control arms live in their own cell, per instruction.
        if isinstance(field, str) and CTRL_RX.match(field):
            c = ctrl_cells[(mnem, field)]
            self._fill(c, rec, "ctrl", run, target, value, blob, mnem, None,
                       outcome, hard, bucket, observed, oracle, where)
            return

        targets = []
        if isinstance(field, str) and field and not field.startswith("_"):
            targets.append((field, "k1"))
        else:
            bi = rec.get("byte_index")
            if bi is None and isinstance(field, str):
                mo = re.search(r"b(?:yte)?[_+]?(\d+)$", field)
                if mo:
                    bi = int(mo.group(1))
            if isinstance(bi, int):
                for f in self.byte_map.get((mnem, bi), ()):
                    targets.append((f, "k2"))
        if not targets:
            # K3: an arm/carrier/group string that names a field of this
            # instruction. Weakest keying; recorded so a "no" from K1/K2 is not
            # read as absence, never relied on alone.
            for gk in GROUPKEYS:
                gv = rec.get(gk)
                if not isinstance(gv, str):
                    continue
                for f in self.spec[mnem]["fields"]:
                    if f and f in gv:
                        targets.append((f, "k3"))
        if not targets:
            targets = [("__UNATTRIBUTED__", "k0")]

        # One record counts ONCE per field, under its strongest keying.
        best = {}
        for f, keying in targets:
            if f not in best or keying < best[f]:
                best[f] = keying
        for f, keying in sorted(best.items()):
            cell = cells[(mnem, f)]
            self._fill(cell, rec, keying, run, target, value, blob, mnem, f,
                       outcome, hard, bucket, observed, oracle, where)

    def _fill(self, cell, rec, keying, run, target, value, blob, mnem, field,
              outcome, hard, bucket, observed, oracle, where):
        cell["records"] += 1
        cell["keying"][keying] += 1
        cell["runs"][run] += 1
        if rec.get("_in_raw"):
            cell["in_raw"] += 1
            cell["raw_runs"][run] += 1
        if target:
            cell["targets"][target] += 1
        cell["files"][where[0]] += 1
        if value is not None:
            _add(cell, "req_values", json.dumps(value, sort_keys=True, default=str))
        if isinstance(blob, str) and blob:
            _add(cell, "actual_bytes", blob.strip().lower())
            cell["ledger_records"] += 1
            if field:
                av, why = self.decode_actual(mnem, field, blob)
                if av is not None:
                    cell["ledger_decoded"] += 1
                    _add(cell, "actual_field_values", av)
                    if isinstance(value, int):
                        if av == value:
                            cell["ledger_agree"] += 1
                        else:
                            cell["ledger_disagree"] += 1
                            if len(cell["ledger_examples"]) < 8:
                                cell["ledger_examples"].append(
                                    {"file": where[0], "line": where[1],
                                     "requested": value, "actual_bytes": blob[:48],
                                     "decoded": av})
        if outcome:
            cell["outcomes"][outcome] += 1
        if hard:
            cell["hard"][outcome or "?"] += 1
        else:
            d = _digest(observed)
            if d:
                _add(cell, "valid_payloads", d)
        if oracle is not None:
            d = _digest(oracle)
            if d:
                _add(cell, "oracle_digests", d)

        # Gate C. Only an explicit host prediction compared against the observation
        # counts. A liveness ladder prediction is counted as liveness.
        sem = None
        for k in ("sem_match", "oracle_match", "sem_ok", "pred_match"):
            if isinstance(rec.get(k), bool):
                sem = rec[k]
                break
        if sem is None:
            p = rec.get("predict")
            if isinstance(p, str) and p.strip().lower() not in LIVENESS_PREDICTIONS \
                    and outcome:
                sem = (p.strip().lower() == outcome)
            elif isinstance(p, str):
                cell["liveness_predictions"] += 1
        if sem is not None:
            cell["sem_checks"] += 1
            if sem:
                cell["sem_true"] += 1
            else:
                cell["sem_false"] += 1
            if bucket:
                cell["sem_buckets"][bucket] += 1
        if rec.get("victim") is True:
            cell["victim"] += 1
            cell["contamination"]["victim"] += 1
        if rec.get("sentinel_bad") is True or rec.get("sentinel_ok") is False:
            cell["sentinel_bad"] += 1
            cell["contamination"]["sentinel_bad"] += 1
        for k in ("restarted", "timed_out", "unstable"):
            if rec.get(k):
                cell["contamination"][k] += 1


# ------------------------------------------------------------- per-experiment


def fingerprint(expdir):
    h = hashlib.blake2b(digest_size=16)
    n = 0
    for p, ext in iter_files(expdir):
        try:
            st = os.stat(p)
        except OSError:
            continue
        h.update(("%s|%d|%d;" % (os.path.relpath(p, expdir), st.st_size,
                                 int(st.st_mtime))).encode())
        n += 1
    h.update(b"|schema=4")
    return h.hexdigest(), n


def index_experiment(expdir, spec, verbose=False):
    ix = Indexer(spec)
    cells = collections.defaultdict(_new_cell)
    ctrl = collections.defaultdict(_new_cell)
    meta = {
        "dir": os.path.basename(expdir),
        "instr_names_seen": collections.Counter(),
        "field_names_seen": collections.Counter(),
        "instr_records": collections.Counter(),
        "group_strings": set(),
        "files": collections.Counter(),
        "bytes": collections.Counter(),
        "runs": collections.Counter(),
        "run_targets": {},
        "parse_failures": 0,
    }
    for p, ext in iter_files(expdir):
        rel = os.path.relpath(p, ROOT)
        run = _run_of(p, expdir)
        meta["files"][ext or "(none)"] += 1
        try:
            meta["bytes"][ext or "(none)"] += os.path.getsize(p)
        except OSError:
            pass
        if os.sep + "raw" + os.sep in p + os.sep:
            meta["runs"][run] += 1
            meta["run_targets"].setdefault(run, _target_of_run(run))
        target = meta["run_targets"].get(run) or _target_of_run(run)
        in_raw = (os.sep + "raw" + os.sep) in (p + os.sep)
        if ext not in RECORD_EXT:
            continue
        try:
            if ext == ".jsonl":
                with open(p, errors="replace") as fh:
                    for ln, line in enumerate(fh, 1):
                        line = line.strip()
                        if not line or line[0] not in "{[":
                            continue
                        try:
                            rec = json.loads(line)
                        except Exception:
                            meta["parse_failures"] += 1
                            continue
                        if isinstance(rec, list):
                            for rr in rec:
                                ix.handle(rr, cells, ctrl, meta, (rel, ln), run,
                                          target, in_raw)
                        else:
                            ix.handle(rec, cells, ctrl, meta, (rel, ln), run,
                                      target, in_raw)
            else:
                with open(p, errors="replace") as fh:
                    try:
                        doc = json.load(fh)
                    except Exception:
                        meta["parse_failures"] += 1
                        continue
                _walk_json(doc, ix, cells, ctrl, meta, rel, run, target,
                           in_raw=in_raw)
        except (OSError, UnicodeDecodeError, RecursionError):
            meta["parse_failures"] += 1
            continue

    out = {
        "_meta": {
            "dir": meta["dir"],
            "files": dict(meta["files"]),
            "bytes": dict(meta["bytes"]),
            "record_files": meta["files"].get(".jsonl", 0) + meta["files"].get(".json", 0),
            "nonrecord_files": sum(v for k, v in meta["files"].items()
                                   if k in TEXT_EXT),
            "runs": dict(meta["runs"]),
            "run_targets": meta["run_targets"],
            "targets": sorted({t for t in meta["run_targets"].values() if t}),
            "parse_failures": meta["parse_failures"],
            "instr_names_seen": dict(meta["instr_names_seen"].most_common(40)),
            "field_names_seen": dict(meta["field_names_seen"].most_common(40)),
            "instr_records": dict(meta["instr_records"]),
            "n_group_strings": len(meta["group_strings"]),
            "has_raw": os.path.isdir(os.path.join(expdir, "raw")),
            "has_prereg": os.path.exists(os.path.join(expdir, "PRE_REGISTRATION.md")),
            "has_contract": os.path.exists(os.path.join(expdir, "CAPTURE_CONTRACT.json")),
            "has_results": os.path.exists(os.path.join(expdir, "RESULTS.md")),
            "has_manifest": bool(glob.glob(os.path.join(expdir, "manifest*.json"))),
            "has_verdicts": os.path.exists(os.path.join(expdir, "analysis",
                                                        "field_verdicts.json")),
            "quarantined": os.path.exists(os.path.join(expdir, "QUARANTINE.md")),
        },
        "cells": {"%s.%s" % (m, f): _finish(c) for (m, f), c in cells.items()},
        "controls": {"%s.%s" % (m, f): _finish(c) for (m, f), c in ctrl.items()},
    }
    return out


def _walk_json(doc, ix, cells, ctrl, meta, rel, run, target, depth=0,
               in_raw=False):
    """A .json artifact may be a record, a list of records, or a dict of lists."""
    if depth > 6:
        return
    if isinstance(doc, list):
        for i, rr in enumerate(doc):
            if isinstance(rr, dict):
                ix.handle(rr, cells, ctrl, meta, (rel, i), run, target, in_raw)
            else:
                _walk_json(rr, ix, cells, ctrl, meta, rel, run, target, depth + 1,
                           in_raw)
    elif isinstance(doc, dict):
        ix.handle(doc, cells, ctrl, meta, (rel, 0), run, target, in_raw)
        for k, v in doc.items():
            if isinstance(v, (list, dict)):
                _walk_json(v, ix, cells, ctrl, meta, rel, run, target, depth + 1,
                           in_raw)


# -------------------------------------------------------- K4, the deep keying


def deep_scan(expdir, mnem, field, spec, maxfiles=4000):
    """K4: harvest hex blobs from ANY format and tokenize with our own disassembler.

    Decisive for the pre-2026-08 experiments, whose raw is text logs and per-case
    .json -- formats in which "a record keyed by field name" cannot exist at all, so
    a K1/K2 zero there says nothing. Lifted from EXP-0197's scan.py.
    """
    sys.path.insert(0, HERE)
    import isadb  # our own clean-room disassembler
    s = spec.get(mnem) or {}
    L = s.get("length") or 4
    span = (s.get("fields") or {}).get(field)
    hexrun = re.compile(r"[0-9a-fA-F]{%d,}" % (2 * L))
    hextok = re.compile(r"^(?:0x)?[0-9a-fA-F]+$")
    seen, vals, anchored, nfiles = set(), set(), 0, 0

    def runs(text):
        out, cur = [], []
        for tok in text.split():
            t = tok.strip()
            if t.endswith(":"):
                if cur:
                    h = "".join(cur)
                    if len(h) // 2 >= L:
                        out.append(h)
                    cur = []
                continue
            core = t[2:] if t[:2] in ("0x", "0X") else t
            if core and len(core) % 2 == 0 and len(core) <= 32 and hextok.match(t):
                cur.append(core.lower())
            else:
                if cur:
                    h = "".join(cur)
                    if len(h) // 2 >= L:
                        out.append(h)
                    cur = []
        if cur:
            h = "".join(cur)
            if len(h) // 2 >= L:
                out.append(h)
        for mo in hexrun.finditer(text):
            h = mo.group(0)
            if len(h) % 2 == 0:
                out.append(h.lower())
        return out

    for p, ext in iter_files(expdir):
        nfiles += 1
        if nfiles > maxfiles:
            break
        try:
            data = open(p, errors="replace").read(8 << 20)
        except OSError:
            continue
        for line in data.splitlines():
            if len(line) > 200000:
                line = line[:200000]
            for h in runs(line):
                if h in seen or len(seen) > 200000:
                    continue
                seen.add(h)
                try:
                    buf = bytes.fromhex(h)
                except ValueError:
                    continue
                try:
                    recs, _ = isadb.disassemble(buf)
                except Exception:
                    continue
                off = 0
                for r in recs:
                    if r.get("error"):
                        break
                    if r.get("mnemonic") == mnem:
                        anchored += 1
                        fl = r.get("fields") or {}
                        if field in fl:
                            vals.add(fl[field])
                    off += r.get("length") or 0
    return {"files_scanned": nfiles, "unique_blobs": len(seen),
            "anchored_hits": anchored, "distinct_field_values": len(vals),
            "values": sorted(vals)[:64], "span": span}


# ------------------------------------------------------------------- the cache


def cache_path(slug):
    return os.path.join(CACHE, slug + ".json")


def build(only=None, verbose=True, force=False):
    spec = load_db()
    os.makedirs(CACHE, exist_ok=True)
    dirs = sorted(d for d in os.listdir(EXPS)
                  if os.path.isdir(os.path.join(EXPS, d)))
    if only:
        dirs = [d for d in dirs if any(d.startswith(o) for o in only)]
    built = skipped = 0
    for i, d in enumerate(dirs, 1):
        expdir = os.path.join(EXPS, d)
        fp, nf = fingerprint(expdir)
        cp = cache_path(d)
        if not force and os.path.exists(cp):
            try:
                if json.load(open(cp)).get("_fingerprint") == fp:
                    skipped += 1
                    continue
            except Exception:
                pass
        doc = index_experiment(expdir, spec, verbose)
        doc["_fingerprint"] = fp
        doc["_files"] = nf
        json.dump(doc, open(cp, "w"), indent=1, default=str)
        built += 1
        if verbose:
            m = doc["_meta"]
            print("  [%3d/%3d] %-46s cells=%-5d ctrl=%-4d rec_files=%-5d "
                  "nonrec=%-5d targets=%s"
                  % (i, len(dirs), d, len(doc["cells"]), len(doc["controls"]),
                     m["record_files"], m["nonrecord_files"],
                     ",".join(m["targets"]) or "-"))
            sys.stdout.flush()
    if verbose:
        print("built %d, cached %d, total %d experiments" % (built, skipped, len(dirs)))
    return built, skipped


def load(slug):
    """Index for one experiment directory (exact name)."""
    cp = cache_path(slug)
    if not os.path.exists(cp):
        return None
    try:
        return json.load(open(cp))
    except Exception:
        return None


def resolve(slug):
    """The project validator's own rule: glob(experiments/<slug>*)."""
    return sorted(os.path.basename(d)
                  for d in glob.glob(os.path.join(EXPS, slug.split("/")[0] + "*"))
                  if os.path.isdir(d))


# --------------------------------------------------------------------- selftest


def selftest():
    """Every extractor must be able to return BOTH answers.

    A gate that refuses everything is as broken as one that refuses nothing, so each
    check below asserts a positive AND a negative case.
    """
    ok = True

    def chk(name, cond):
        nonlocal ok
        print("%-4s %s" % ("PASS" if cond else "FAIL", name))
        if not cond:
            ok = False

    spec = {"tst": {"length": 2, "match": [], "emitter_role": None,
                    "fields": {"f": (4, 4)}}}
    ix = Indexer(spec)
    # Gate A both ways: 0x59 0x01 little-endian -> field at bit 4 width 4 == 5.
    got, why = ix.decode_actual("tst", "f", "5901")
    chk("Gate A decodes a requested value out of actual bytes (5)", got == 5 and why is None)
    got2, why2 = ix.decode_actual("tst", "f", "0901")
    chk("Gate A returns a DIFFERENT value for different bytes (0)", got2 == 0)
    chk("Gate A refuses bytes it cannot parse", ix.decode_actual("tst", "f", "zz")[0] is None)
    chk("Gate A refuses a field db.json does not have",
        ix.decode_actual("tst", "nope", "5901")[1] == "field-not-in-db")

    # Gate C both ways: a liveness ladder prediction must NOT count as semantics.
    cells = collections.defaultdict(_new_cell)
    ctrl = collections.defaultdict(_new_cell)
    meta = {"instr_names_seen": collections.Counter(),
            "field_names_seen": collections.Counter(),
            "instr_records": collections.Counter(), "group_strings": set()}
    ix.handle({"instr": "tst", "field": "f", "value": 5, "bytes": "5901",
               "predict": "move", "outcome": "ok"}, cells, ctrl, meta, ("x", 1),
              "r1", "G17P")
    chk("a `predict: move` ladder record scores 0 semantic checks",
        cells[("tst", "f")]["sem_checks"] == 0
        and cells[("tst", "f")]["liveness_predictions"] == 1)
    ix.handle({"instr": "tst", "field": "f", "value": 5, "bytes": "5901",
               "sem_match": True, "outcome": "ok"}, cells, ctrl, meta, ("x", 2),
              "r1", "G17P")
    chk("an explicit sem_match record DOES score a semantic check",
        cells[("tst", "f")]["sem_checks"] == 1)

    # Gate A disagreement must be recorded as disagreement, not silently dropped.
    ix.handle({"instr": "tst", "field": "f", "value": 7, "bytes": "5901",
               "outcome": "ok"}, cells, ctrl, meta, ("x", 3), "r1", "G17P")
    c = cells[("tst", "f")]
    chk("requested 7 vs decoded 5 is counted as a ledger DISAGREEMENT",
        c["ledger_disagree"] == 1 and c["ledger_agree"] == 2)

    # Gate B: a control arm never lands in the swept field's cell.
    ix.handle({"instr": "tst", "field": "__ladder_L_f", "value": 5, "bytes": "5901",
               "predict": "move", "outcome": "ok"}, cells, ctrl, meta, ("x", 4),
              "r1", "G17P")
    chk("a __ladder control record goes to the CONTROL cell, not the field cell",
        ("tst", "__ladder_L_f") in ctrl and cells[("tst", "f")]["records"] == 3)

    # Hard outcomes are not valid payloads -- the two defects wave_audit found.
    before = cells[("tst", "f")]["V" if "V" in cells[("tst", "f")] else "valid_payloads"]
    n_before = len(cells[("tst", "f")]["valid_payloads"])
    ix.handle({"instr": "tst", "field": "f", "value": 1, "bytes": "1901",
               "outcome": "fault", "observed": {"z": 99}}, cells, ctrl, meta,
              ("x", 5), "r1", "G17P")
    chk("a GPU fault is NOT counted as a valid payload",
        len(cells[("tst", "f")]["valid_payloads"]) == n_before)
    ix.handle({"instr": "tst", "field": "f", "value": 2, "bytes": "2901",
               "outcome": "undecodable", "observed": {"z": 98}}, cells, ctrl, meta,
              ("x", 6), "r1", "G17P")
    chk("`undecodable` (our own disassembler) is NOT counted as a valid payload",
        len(cells[("tst", "f")]["valid_payloads"]) == n_before)
    ix.handle({"instr": "tst", "field": "f", "value": 3, "bytes": "3901",
               "outcome": "ok", "observed": {"z": 1}}, cells, ctrl, meta,
              ("x", 7), "r1", "G17P")
    chk("a clean record IS counted as a valid payload",
        len(cells[("tst", "f")]["valid_payloads"]) == n_before + 1)

    # K2: an unkeyed byte sweep must reach the field whose span covers that byte.
    cells2 = collections.defaultdict(_new_cell)
    ix.handle({"instr": "tst", "field": None, "byte_index": 0, "value": 3,
               "bytes": "3901", "outcome": "ok"}, cells2, ctrl, meta, ("y", 1),
              "r1", "G17P")
    chk("K2: a field:null byte-0 sweep reaches field f (span bit 4..7 = byte 0)",
        cells2[("tst", "f")]["records"] == 1)
    cells3 = collections.defaultdict(_new_cell)
    ix.handle({"instr": "tst", "field": None, "byte_index": 9, "value": 3,
               "bytes": "3901", "outcome": "ok"}, cells3, ctrl, meta, ("y", 2),
              "r1", "G17P")
    chk("K2 does NOT attribute a byte-9 sweep to a byte-0 field",
        ("tst", "f") not in cells3)

    chk("target of a g17p run dir is G17P", _target_of_run("g17p_20260830_run01") == "G17P")
    chk("target of an m4 run dir is G16G", _target_of_run("m4-20260827-run02") == "G16G")
    chk("an unnamed run dir yields NO target rather than a guess",
        _target_of_run("pilot01") is None)
    chk("bucket map separates fault from silent",
        bucket_of("fault") == "fault" and bucket_of("silent_zero") == "silent")
    chk("bucket map calls our own disassembler a MEASUREMENT failure",
        bucket_of("undecodable") == "measurement_failure")

    print("\nEVIDENCE-INDEX SELFTEST %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", nargs="*", metavar="SLUG")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--show", nargs=3, metavar=("EXPDIR", "MNEM", "FIELD"))
    ap.add_argument("--deep", nargs=3, metavar=("EXPDIR", "MNEM", "FIELD"))
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.build is not None:
        build(a.build or None, force=a.force)
        return 0
    if a.show:
        d, m, f = a.show
        doc = load(d) or {}
        print(json.dumps(doc.get("cells", {}).get("%s.%s" % (m, f), {}),
                         indent=1, default=str))
        return 0
    if a.deep:
        d, m, f = a.deep
        print(json.dumps(deep_scan(os.path.join(EXPS, d), m, f, load_db()),
                         indent=1, default=str))
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
