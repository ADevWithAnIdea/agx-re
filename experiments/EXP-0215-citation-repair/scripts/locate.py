#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""locate.py -- for every (experiment, mnemonic, field) key, the LOCATOR evidence
needed to justify adding a citation.

This is not a third indexer. It subclasses `evidence_index.Indexer` -- the same
K1/K2/K3 keying, the same Gate A decode, the same control/raw/derived splits --
and only records the extra columns a citation proposal has to name:

  * `first`  : the file and line of the FIRST record, so every proposal can be
               opened by hand.
  * `span_declared` / `span_match` / `span_mismatch`: did the record's own
               `fstart`/`fwidth` agree with db.json's CURRENT span? A record that
               declares a different span swept different bits under the same
               NAME -- the `carry_gen` subop->srcA->srcB hazard.
  * `n_actual_field_values`: distinct values of THIS FIELD'S bits decoded out of
               committed actual bytes at the CURRENT span. EXP-0197 section 4:
               `half_alu.dst` has 256 distinct `bytes` and ONE distinct value of
               its own nibble; EXP-0214 makes the same point for `half_pack.dst`.
  * `bytes_no_value` : records that carry bytes but no requested value -- a
               program-level credit, never a per-field sweep.

Writes work/locators.json. Reads only this repository's committed artifacts.
"""
import collections, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
ROOT = os.path.abspath(os.path.join(EXP, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools", "agx-isa"))
import evidence_index as EI

DBFROZEN = os.path.join(EXP, "work", "db_frozen.json")


def match_ok(spec, mnem, buf):
    """Do these bytes still satisfy the descriptor's own match bits?

    A sweep of a byte that carries match bits produces programs that are no longer
    this instruction at all. EXP-0197 4.4 found `stop.reserved`'s two committed
    cases overwrite byte0 as well, so neither spliced word is a `stop`; EXP-0211's
    P5 refuses the same splice by rule. Applied here to every committed encoding,
    so a distinct-encoding count never includes bytes that decode to something else.
    """
    s = spec.get(mnem) or {}
    L = s.get("length") or len(buf)
    if len(buf) < L:
        return False
    v = int.from_bytes(buf[:L], "little")
    for m in (s.get("match") or []):
        try:
            st, w, val = m[0], m[1], m[2]
        except Exception:
            continue
        if ((v >> st) & ((1 << w) - 1)) != val:
            return False
    return True


def new_cell():
    c = EI._new_cell()
    c.update({"first": None, "first_obs": None, "span_declared": 0, "span_match": 0,
              "span_mismatch": 0, "declared_spans": collections.Counter(),
              "bytes_no_value": 0, "value_no_bytes": 0,
              "byte_indices": collections.Counter(),
              "req_value_ints": set(), "outcome_records": 0,
              "afv_match": set(), "match_bytes": 0, "nonmatch_bytes": 0})
    return c


class Loc(EI.Indexer):
    def _fill(self, cell, rec, keying, run, target, value, blob, mnem, field,
              outcome, hard, bucket, observed, oracle, where, byte_index=None):
        EI.Indexer._fill(self, cell, rec, keying, run, target, value, blob, mnem,
                         field, outcome, hard, bucket, observed, oracle, where,
                         byte_index=byte_index)
        if cell["first"] is None:
            cell["first"] = [where[0], where[1]]
        # A locator must point at an OBSERVATION. `00_manifest.json` records in this
        # corpus carry instr+field+arm+n_cases and no value, bytes or outcome: they
        # are the plan, not the run, and they sort first in the directory. A
        # proposal that cites the plan cites nothing.
        if cell["first_obs"] is None and outcome and (blob or value is not None):
            cell["first_obs"] = [where[0], where[1]]
        declared = (rec.get("fstart"), rec.get("fwidth"))
        if None not in declared:
            cell["span_declared"] += 1
            cell["declared_spans"][str(declared)] += 1
            span = (self.spec.get(mnem, {}).get("fields") or {}).get(field)
            if declared == span:
                cell["span_match"] += 1
            else:
                cell["span_mismatch"] += 1
        if isinstance(byte_index, int):
            cell["byte_indices"][byte_index] += 1
        if blob and value is None:
            cell["bytes_no_value"] += 1
        if value is not None and not blob:
            cell["value_no_bytes"] += 1
        if blob and field:
            h = re.sub(r"[^0-9a-f]", "", str(blob).strip().lower().removeprefix("0x"))
            if h and not len(h) % 2:
                try:
                    buf = bytes.fromhex(h)
                except ValueError:
                    buf = None
                if buf is not None:
                    if match_ok(self.spec, mnem, buf):
                        cell["match_bytes"] += 1
                        av, why = self.decode_actual(mnem, field, blob)
                        if av is not None and len(cell["afv_match"]) < 4096:
                            cell["afv_match"].add(av)
                    else:
                        cell["nonmatch_bytes"] += 1
        if isinstance(value, int) and len(cell["req_value_ints"]) < 4096:
            cell["req_value_ints"].add(value)
        if outcome:
            cell["outcome_records"] += 1


def scan(expdir, spec):
    ix = Loc(spec)
    cells = collections.defaultdict(new_cell)
    ctrl = collections.defaultdict(new_cell)
    d, dc = collections.defaultdict(new_cell), collections.defaultdict(new_cell)
    meta = {"instr_names_seen": collections.Counter(),
            "field_names_seen": collections.Counter(),
            "instr_records": collections.Counter(), "group_strings": set(),
            "run_targets": {}}
    for p, ext in EI.iter_files(expdir):
        rel = os.path.relpath(p, ROOT)
        run = EI._run_of(p, expdir)
        in_raw = (os.sep + "raw" + os.sep) in (p + os.sep)
        if in_raw:
            meta["run_targets"].setdefault(run, EI._target_of_run(run))
        target = meta["run_targets"].get(run) or EI._target_of_run(run)
        if ext not in EI.RECORD_EXT:
            continue
        C, K = (cells, ctrl) if in_raw else (d, dc)
        try:
            if ext == ".jsonl":
                with open(p, errors="replace") as fh:
                    for ln, line in enumerate(fh, 1):
                        line = line.strip()
                        if not line or line[0] not in "{[":
                            continue
                        try:
                            r = json.loads(line)
                        except Exception:
                            continue
                        for rr in (r if isinstance(r, list) else [r]):
                            ix.handle(rr, C, K, meta, (rel, ln), run, target, in_raw)
            else:
                with open(p, errors="replace") as fh:
                    try:
                        doc = json.load(fh)
                    except Exception:
                        continue
                EI._walk_json(doc, ix, C, K, meta, rel, run, target, in_raw=in_raw)
        except (OSError, UnicodeDecodeError, RecursionError):
            continue
    return cells


def slim(c):
    o = {"records": c["records"], "in_raw": c["in_raw"],
         "first_file": c["first"][0] if c["first"] else None,
         "first_line": c["first"][1] if c["first"] else None,
         "obs_file": c["first_obs"][0] if c["first_obs"] else None,
         "obs_line": c["first_obs"][1] if c["first_obs"] else None,
         "keying": dict(c["keying"]),
         "raw_runs": sorted(c["raw_runs"].keys()),
         "targets": dict(c["targets"]),
         "n_req_values": len(c["req_values"]),
         "n_req_value_ints": len(c["req_value_ints"]),
         "n_actual_bytes": len(c["actual_bytes"]),
         "n_actual_field_values": len(c["actual_field_values"]),
         "n_actual_field_values_matching": len(c["afv_match"]),
         "match_bytes": c["match_bytes"], "nonmatch_bytes": c["nonmatch_bytes"],
         "actual_field_values": sorted(c["actual_field_values"])[:32],
         "ledger_records": c["ledger_records"], "ledger_agree": c["ledger_agree"],
         "ledger_disagree": c["ledger_disagree"],
         "byte_ledger_agree": c["byte_ledger_agree"],
         "byte_ledger_disagree": c["byte_ledger_disagree"],
         "span_declared": c["span_declared"], "span_match": c["span_match"],
         "span_mismatch": c["span_mismatch"],
         "declared_spans": dict(c["declared_spans"]),
         "bytes_no_value": c["bytes_no_value"],
         "value_no_bytes": c["value_no_bytes"],
         "byte_indices": {str(k): v for k, v in c["byte_indices"].items()},
         "outcomes": dict(c["outcomes"]), "outcome_records": c["outcome_records"],
         "sem_checks": c["sem_checks"],
         "carriers": sorted(c["carriers"].keys())[:16],
         "files": sorted(c["files"].keys())[:8]}
    return o


def main():
    spec = EI.load_db(DBFROZEN)
    exps = os.path.join(ROOT, "experiments")
    dirs = sorted(x for x in os.listdir(exps) if os.path.isdir(os.path.join(exps, x)))
    only = [a for a in sys.argv[1:] if not a.startswith("-")]
    if only:
        dirs = [x for x in dirs if any(x.startswith(o) for o in only)]
    out = {}
    for i, dname in enumerate(dirs, 1):
        cells = scan(os.path.join(exps, dname), spec)
        if not cells:
            continue
        out[dname] = {"%s.%s" % (m, f): slim(c) for (m, f), c in cells.items()
                      if f != "__UNATTRIBUTED__"}
        print("[%3d/%3d] %-46s keys=%d" % (i, len(dirs), dname, len(out[dname])))
        sys.stdout.flush()
    p = os.path.join(EXP, "work", "locators.json")
    json.dump(out, open(p, "w"), indent=0, default=str)
    print("wrote", p, len(out), "experiments")


if __name__ == "__main__":
    main()
