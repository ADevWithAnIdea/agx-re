#!/usr/bin/env python3
"""EXP-0083 capture runner. Never runs a device operation without --execute.

Device-buffer base-slot census (Part-II MEM-15/MEM-16/MEM-17) on the local
M4 through public Metal only. Each case is ONE fresh harness process (fresh
device, library, pipeline, buffers, queue, command buffer) running ONE
possibly-byte-spliced copy of the archive serialized from OUR OWN kernel
source. The runner records the environment, the host build, the per-kernel
compile + probe-instruction identification, the complete frozen case matrix,
one process receipt per case, and one authoritative observation line per case
into an append-only raw tree.

Harness/process discipline (lessons from EXP-0072/0073/0074/0075, all applied):
  * --selftest must pass immediately before the run gate (no capture under an
    unproven verifier), and the self-test includes the gate-sequence
    state-machine walk (the EXP-0075 fix): every contracted gate is proven
    runnable AND satisfiable at the state where the contract invokes it, and
    fail-correct at states where it must not pass;
  * ONE authoritative record schema: verify.py imports every key set and
    constant from this module, so the runner and the verifier cannot disagree;
  * the harness is single-threaded and synchronous with a flushed,
    error-checked exit, so a record cannot be truncated by a racing exit;
  * a contract-named NON-RECORDED smoke invocation (c31_load_slot_1) runs one
    scratch case into work/ BEFORE the append-only raw tree is created.

Case-fault discipline: an out-of-range/unpopulated base slot is exactly the
unknown under test, so a faulted, hung, or killed case is a RESULT (status
watchdog/proc_fail/proc_timeout), never retried in place; the loop continues
in a fresh process. Only 3 consecutive OS-level spawn failures stop the run.

Successor of QUARANTINED EXP-0078-m4-base-slot-census (see its QUARANTINE.md
and RESULTS.md): run01 there captured clean (351/351 ok, zero faults) but its
frozen verify.py hardcoded the probe-instruction opcode as 0x67 for every
kernel, which is false for storeprobe's device_store (0xe7) -- permanent
`--between-runs` failure, never a real observation defect. Fixed here with
ONE shared definition (`insn_opcode`, this module) taking the expected opcode
from the recorded identification data (`insn_hex[0:2]`) instead of assuming
it; used identically by this runner's own capture-time self-check, by
verify.py's build_record_checks, and by verify.py's selftest synthetic-tree
builder (whose OLD fixture poked a matching-but-wrong 0x67 into the
synthetic storeprobe main, making the bug invisible to --selftest). The nine
kernels and harness/probe.m are otherwise the same frozen design as
EXP-0078; run01's disclosed observations are re-registered in
PRE_REGISTRATION.md as hypotheses to independently re-establish, not as
expectations.
"""
import argparse, datetime, hashlib, json, platform, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
EXP_REL = "experiments/EXP-0083-m4-base-slot-census"
TOOLS = REPO / "tools"
sys.path.insert(0, str(TOOLS / "agx-isa"))
sys.path.insert(0, str(TOOLS / "shdump"))

RUNS = ("m4-20260827-run01", "m4-20260827-run02")

BOUNDARY = ("public Metal API only; runtime MSL compile with fastMathEnabled=YES (matching the "
            "shdump archive build); one archive per case with at most ONE spliced byte in the "
            "base-slot selector of one probe instruction of our own compiled kernel; no "
            "Apple-binary/archive-content/BO introspection beyond our own shader bytes")

TIMEOUTS = {"env_command": 10, "host_build": 120, "kernel_compile": 120,
            "identify_command": 60, "case_process": 120}

AUTH_CODE = ("harness/probe.m", "harness/build.sh", "run.py", "analysis.py",
             "make_manifest.py", "verify.py") + tuple(
    "kernels/%s.metal" % k for k in
    ("census31", "census31_v2", "census4", "census4_v2", "capacity",
     "storeprobe", "storeprobe_v2", "atomicprobe", "atomicprobe_v2"))
AUTH_DOC = ("PRE_REGISTRATION.md", "README.md")

# ---- frozen geometry (single source of truth; imported by verify/analysis) ----
GEOMETRY = {
    "n_buffers": 31,                 # MSL buffer indices 0..30 (the API maximum)
    "words_per_buffer": 16,          # 64 bytes per bound buffer
    "out_dump_bytes": 128,           # out buffer dump (32 words)
    "fill_rule": "word w of buffer k = P(k,w) = 0xC0DE0000 | (k<<8) | w, except the "
                 "idxbuf binding whose word 0 is the frozen probe element index 5",
    "probe_element_index": 5,        # i0: the probe reads word 5 of the selected base
    "store_value": "0x5A17C0DE",     # the frozen store / atomic-exchange operand
    "grid": 1, "threadgroup": 1,
    "idxbuf_index": {"census31": 30, "capacity": 30, "storeprobe": 30,
                     "atomicprobe": 30, "census4": 3},
    "census31_probe_source_buffer": 1,
    "storeprobe_tgt_index": 29,
    "atomicprobe_abuf_index": 29,
    "atomic_selector_rel": 5,        # byte+5 for the emitted atomic form (see PRE_REG)
    "load_store_selector_rel": 4,    # byte+4 for device_load / device_store
}

STATUS_VALUES = ("ok", "cb_error", "watchdog", "proc_fail", "proc_timeout")
SMOKE_CASE = "c31_load_slot_1"       # identity splice: slot byte patched to its own value
SMOKE_SLOT = 1                       # required to equal ident.census31.orig_value
MAX_CONSECUTIVE_INFRA = 3

# census4 boundary-focused subset (frozen): every MEM-16 boundary plus a
# symmetric interior sample; justification frozen in PRE_REGISTRATION.md.
C4_SUBSET = tuple(list(range(0, 17)) + list(range(24, 41)) + list(range(56, 73))
                  + list(range(120, 137)) + list(range(248, 256)))
MEM17_SLOTS = (3, 31, 32, 63, 127, 128, 255)

# One authoritative frozen key set per record slot (imported by verify.py).
REC_KEYS = {"argv", "cwd", "timeout_seconds", "started_utc", "timed_out", "exit",
            "stdout", "stderr", "exception"}
CASE_KEYS = {"i", "name", "kernel", "op", "slot", "status", "exit", "timed_out",
             "cb_status", "err", "probe_word", "witness_ok", "changed"}
SUMMARY_KEYS = {"schema", "kernel", "op", "slot", "splice_abs_off", "idxbuf", "device",
                "registry_id", "machine", "os", "fast_math", "math_mode_raw",
                "language_version_raw", "library_compile_seconds", "dispatch_seconds",
                "command_buffer_status", "error", "pre_ok", "out_hex", "bufs_hex"}
DISPATCH_KEYS = {"schema", "run_id", "cases_planned", "cases_recorded", "n_ok",
                 "n_cb_error", "n_watchdog", "n_proc_fail", "n_proc_timeout",
                 "results_lines", "results_sha256"}
INPUTS_KEYS = {"schema", "git_revision", "git_dirty", "experiment_tree_dirty_entries",
               "authored_code_sha256", "authored_doc_sha256", "sw_vers", "xcrun_version",
               "python", "machine", "boundary", "timeouts_seconds", "geometry"}
RECEIPT_LINE_KEYS = REC_KEYS | {"i", "name"}
RUN_MANIFEST_KEYS = {"schema", "run_id", "cases_planned", "cases_recorded",
                     "runner_sha256", "harness_sha256", "kernel_sha256",
                     "matrix_sha256", "build_sha256", "results_sha256",
                     "receipts_sha256"}
MATRIX_CASE_KEYS = {"i", "name", "kernel", "op", "slot", "sel_rel", "cls", "spliced"}
BUILD_KEYS = {"schema", "build", "tools_sha256", "kernels", "ident"}
KERNEL_REC_KEYS = {"archive_sha256", "main_off", "main_len", "main_hex"}
IDENT_KEYS = {"method", "probe_main_off", "selector_rel", "orig_value", "v2_value",
              "byte4_value", "insn_hex", "abs_off"}
RAW_FILES = ("00_inputs.json", "01_matrix.json", "02_build.json", "03_dispatch.json",
             "04_results.jsonl", "05_receipts.jsonl", "06_run_manifest.json")
KERNEL_NAMES = ("census31", "census31_v2", "census4", "census4_v2", "capacity",
                "storeprobe", "storeprobe_v2", "atomicprobe", "atomicprobe_v2")


# ---- frozen fill / expectation model ------------------------------------------
def P(k, w):
    return (0xC0DE0000 | ((k & 0xFF) << 8) | (w & 0xFF)) & 0xFFFFFFFF


def idxbuf_index(kernel):
    return GEOMETRY["idxbuf_index"][kernel]


def fillword(kernel, k, w):
    if k == idxbuf_index(kernel) and w == 0:
        return GEOMETRY["probe_element_index"]
    return P(k, w)


def fill_words(kernel, k):
    return [fillword(kernel, k, w) for w in range(GEOMETRY["words_per_buffer"])]


def witness_spec(kernel):
    """(word_index, expected_value) pairs proving every non-probe read is correct."""
    if kernel == "census4":
        return [(1, P(1, 0)), (2, P(2, 0)), (3, GEOMETRY["probe_element_index"])]
    return [(k, fillword(kernel, k, 0)) for k in range(1, 31)]


def decode_pattern(word):
    """P(k,w) decoder: returns (k, w) if word is a fill word, else None."""
    if (word & 0xFFFF0000) != 0xC0DE0000:
        return None
    k = (word >> 8) & 0xFF
    w = word & 0xFF
    return (k, w) if P(k, w) == word else None


# ---- frozen cross-run repeat gate (single authoritative implementation) --------
def probe_word_value(hexword):
    """probe_word is out_hex[0:8]: the first 4 bytes in memory order, i.e. the
    little-endian image of the 32-bit word."""
    return int.from_bytes(bytes.fromhex(hexword), "little")


def probe_word_hex(word):
    return (word & 0xFFFFFFFF).to_bytes(4, "little").hex()


def probe_word_class(hexword):
    """Class of a probe_word value: 'zero' | 'pattern' | 'garbage'."""
    if not hexword:
        return "none"
    w = probe_word_value(hexword)
    if w == 0:
        return "zero"
    return "pattern" if decode_pattern(w) is not None else "garbage"


def cross_run_problems(qs_a, qs_b):
    """The frozen cross-run gate: every case must have identical status, and
    probe_word must be identical whenever either run's value is in a
    deterministic class (zero or pattern-decodable). Only garbage-class values
    (uninitialized/unmapped reads) may legitimately differ, and the caller
    REPORTS those. Used unchanged by analysis.py and verify.py."""
    problems = []
    for i in range(len(qs_a)):
        qa, qb = qs_a[i], qs_b[i]
        if qa["status"] != qb["status"]:
            problems.append({"case": qa["name"], "kind": "status",
                             "a": qa["status"], "b": qb["status"]})
        elif qa["probe_word"] != qb["probe_word"]:
            if "garbage" not in (probe_word_class(qa["probe_word"]),
                                 probe_word_class(qb["probe_word"])):
                problems.append({"case": qa["name"], "kind": "probe_word",
                                 "a": qa["probe_word"], "b": qb["probe_word"]})
    return problems


# ---- frozen case matrix --------------------------------------------------------
def matrix():
    m = []
    for s in range(256):
        m.append({"i": len(m), "name": "c31_load_slot_%d" % s, "kernel": "census31",
                  "op": "load", "slot": s, "sel_rel": 4, "cls": "census31", "spliced": True})
    for s in C4_SUBSET:
        m.append({"i": len(m), "name": "c4_load_slot_%d" % s, "kernel": "census4",
                  "op": "load", "slot": s, "sel_rel": 4, "cls": "census4", "spliced": True})
    m.append({"i": len(m), "name": "capacity_baseline", "kernel": "capacity",
              "op": "load", "slot": -1, "sel_rel": 4, "cls": "capacity", "spliced": False})
    m.append({"i": len(m), "name": "st_store_baseline", "kernel": "storeprobe",
              "op": "store", "slot": -1, "sel_rel": 4, "cls": "store", "spliced": False})
    for s in MEM17_SLOTS:
        m.append({"i": len(m), "name": "st_store_slot_%d" % s, "kernel": "storeprobe",
                  "op": "store", "slot": s, "sel_rel": 4, "cls": "store", "spliced": True})
    m.append({"i": len(m), "name": "at_axch_baseline", "kernel": "atomicprobe",
              "op": "axch", "slot": -1, "sel_rel": 5, "cls": "atomic_sel", "spliced": False})
    for s in MEM17_SLOTS:
        m.append({"i": len(m), "name": "at_axch_sel_%d" % s, "kernel": "atomicprobe",
                  "op": "axch", "slot": s, "sel_rel": 5, "cls": "atomic_sel", "spliced": True})
    for v in (1, 255):
        m.append({"i": len(m), "name": "at_b4probe_%d" % v, "kernel": "atomicprobe",
                  "op": "axch", "slot": v, "sel_rel": 4, "cls": "atomic_b4", "spliced": True})
    return m


CASES = matrix()
TOTAL = len(CASES)
BY_NAME = {c["name"]: c for c in CASES}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def put(p, o):
    Path(p).write_text(json.dumps(o, indent=2, sort_keys=True) + "\n")


def provenance():
    def git(*a):
        return subprocess.run(["git", *a], cwd=REPO, text=True, capture_output=True, check=True).stdout
    exp = git("status", "--porcelain", "--", EXP_REL)
    return {
        "git_revision": git("rev-parse", "HEAD").strip(),
        "git_dirty": git("status", "--porcelain").strip() != "",
        "experiment_tree_dirty_entries": len([l for l in exp.splitlines() if l.strip()]),
        "authored_code_sha256": {p: sha(HERE / p) for p in AUTH_CODE},
        "authored_doc_sha256": {p: sha(HERE / p) for p in AUTH_DOC},
    }


def rec(argv, timeout, cwd=HERE):
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        p = subprocess.run([str(x) for x in argv], cwd=str(cwd), text=True,
                           capture_output=True, timeout=timeout)
        return {"argv": [str(x) for x in argv], "cwd": str(cwd), "timeout_seconds": timeout,
                "started_utc": started, "timed_out": False, "exit": p.returncode,
                "stdout": p.stdout, "stderr": p.stderr, "exception": None}
    except subprocess.TimeoutExpired as e:
        return {"argv": [str(x) for x in argv], "cwd": str(cwd), "timeout_seconds": timeout,
                "started_utc": started, "timed_out": True, "exit": None,
                "stdout": e.stdout or "", "stderr": e.stderr or "", "exception": "TimeoutExpired"}
    except OSError as e:
        return {"argv": [str(x) for x in argv], "cwd": str(cwd), "timeout_seconds": timeout,
                "started_utc": started, "timed_out": False, "exit": None,
                "stdout": "", "stderr": "", "exception": type(e).__name__}


def build_argv(work_dir):
    return ["sh", HERE / "harness/build.sh", work_dir / "bin"]


# ---- probe-instruction identification (pre-raw; recorded in 02_build) ---------
def locate_main(archive):
    out = subprocess.check_output(
        [sys.executable, "-B", str(TOOLS / "shdump/agxparse.py"), str(archive),
         "--locate", "_agc.main"], text=True, timeout=TIMEOUTS["identify_command"])
    parts = out.split()
    return int(parts[0]), int(parts[1])


def extract_main(archive):
    out = subprocess.check_output(
        [sys.executable, "-B", str(TOOLS / "shdump/agxparse.py"), str(archive),
         "--extract-hex"], text=True, timeout=TIMEOUTS["identify_command"])
    return bytes.fromhex(out.strip())


def walk_insns(a):
    """Walk our own bytes with the read-only Apple9 DB; tolerate a partial walk."""
    import isadb
    off, out = 0, []
    while off < len(a):
        L = isadb.instr_length(a, off)
        if not L or off + L > len(a):
            break
        d = isadb.decode_one(a, off)[0]
        out.append((off, d["mnemonic"], d["fields"]))
        off += L
    return out, off


def insn_opcode(insn_hex):
    """The probe instruction's opcode byte, taken from the RECORDED
    identification data (byte 0 of insn_hex) rather than assumed per
    kernel/op-class. EXP-0078 defect class (fixed here): the quarantined
    predecessor's verifier and its selftest synthetic-tree builder each
    independently hardcoded the assumption "every probe opcode is 0x67",
    which is true for the load/atomic-family probes (census31, census4,
    atomicprobe) but false for storeprobe's device_store (0xe7) -- an
    assumption baked into two places that agreed with EACH OTHER but not
    with reality, so --selftest could not see it. There is now exactly ONE
    definition of what a recorded ident record's opcode byte IS, imported
    by run.py itself (self-check below), verify.py's build_record_checks,
    and verify.py's synthetic-tree builder (_build_kernel_records) -- no
    second, independent, op-class-specific opcode table anywhere."""
    return int(insn_hex[0:2], 16)


def identify(kern_main, v2_main, kernel):
    """Locate the probe instruction + its base-slot selector byte. Pure."""
    if kernel in ("census31", "census4"):
        if len(kern_main) != len(v2_main):
            raise SystemExit("ident %s: variant length differs" % kernel)
        diffs = [i for i in range(len(kern_main)) if kern_main[i] != v2_main[i]]
        if len(diffs) != 1:
            raise SystemExit("ident %s: expected exactly 1 diff byte, got %s"
                             % (kernel, diffs))
        p = diffs[0]
        if p < 4 or kern_main[p - 4] != 0x67:
            raise SystemExit("ident %s: diff byte is not +4 of a 0x67 load" % kernel)
        return {"method": "diff_single_byte", "probe_main_off": p - 4, "selector_rel": 4,
                "orig_value": kern_main[p], "v2_value": v2_main[p],
                "byte4_value": kern_main[p],
                "insn_hex": kern_main[p - 4:p + 10].hex(), "abs_off": None}
    if kernel == "storeprobe":
        insns, end = walk_insns(kern_main)
        stores = [(o, f) for (o, m, f) in insns if m == "device_store"
                  and f.get("base_slot") not in (0, None)]
        if len(stores) != 1:
            raise SystemExit("ident storeprobe: expected 1 non-out store, got %d"
                             % len(stores))
        o, f = stores[0]
        insns2, _ = walk_insns(v2_main)
        stores2 = [(o2, f2) for (o2, m, f2) in insns2 if m == "device_store"
                   and f2.get("base_slot") not in (0, None)]
        if len(stores2) != 1:
            raise SystemExit("ident storeprobe_v2: expected 1 non-out store")
        return {"method": "decode_unique_nonout_store", "probe_main_off": o,
                "selector_rel": 4, "orig_value": f["base_slot"],
                "v2_value": stores2[0][1]["base_slot"], "byte4_value": f["base_slot"],
                "insn_hex": kern_main[o:o + 14].hex(), "abs_off": None}
    if kernel == "atomicprobe":
        insns, end = walk_insns(kern_main)
        if end != len(kern_main):
            raise SystemExit("ident atomicprobe: main walk ended at %d/%d" % (end, len(kern_main)))
        at = [(o, f) for (o, m, f) in insns if m in ("atomic_rmw", "atomic_mem")]
        if len(at) != 1:
            raise SystemExit("ident atomicprobe: expected 1 atomic, got %d" % len(at))
        o, f = at[0]
        insns2, end2 = walk_insns(v2_main)
        at2 = [(o2, f2) for (o2, m, f2) in insns2 if m in ("atomic_rmw", "atomic_mem")]
        if end2 != len(v2_main) or len(at2) != 1:
            raise SystemExit("ident atomicprobe_v2: walk/atomic count")
        return {"method": "decode_unique_atomic", "probe_main_off": o, "selector_rel": 5,
                "orig_value": kern_main[o + 5], "v2_value": v2_main[at2[0][0] + 5],
                "byte4_value": kern_main[o + 4],
                "insn_hex": kern_main[o:o + 14].hex(), "abs_off": None}
    raise SystemExit("identify: unknown kernel " + kernel)


def compile_and_identify(work):
    """shdump every kernel; extract mains; identify probes. Returns (kernels, ident)."""
    arch_dir = work / "archives"
    arch_dir.mkdir(parents=True)
    kernels, mains = {}, {}
    for k in KERNEL_NAMES:
        src = HERE / ("kernels/%s.metal" % k)
        arc = arch_dir / ("%s.bin" % k)
        z = rec([work / "bin/shdump", "-o", arc, src], TIMEOUTS["kernel_compile"])
        if z["timed_out"] or z["exit"] != 0 or z["exception"] is not None:
            raise SystemExit("kernel compile failed: %s (%s)" % (k, z["stderr"][-400:]))
        off, ln = locate_main(arc)
        main = extract_main(arc)
        if ln != len(main):
            raise SystemExit("kernel %s: locate/extract length mismatch" % k)
        kernels[k] = {"archive_sha256": sha(arc), "main_off": off, "main_len": ln,
                      "main_hex": main.hex()}
        mains[k] = main
    ident = {}
    for a, b in (("census31", "census31_v2"), ("census4", "census4_v2"),
                 ("storeprobe", "storeprobe_v2"), ("atomicprobe", "atomicprobe_v2")):
        r = identify(mains[a], mains[b], a)
        r["abs_off"] = kernels[a]["main_off"] + r["probe_main_off"] + r["selector_rel"]
        # Self-check with the ONE shared opcode definition (insn_opcode): the
        # byte identify() actually found at the probe offset must equal the
        # opcode recorded in its own insn_hex. Never assume a fixed opcode
        # across op classes here either -- this is a coupling check, not an
        # op-class assumption.
        if mains[a][r["probe_main_off"]] != insn_opcode(r["insn_hex"]):
            raise SystemExit("ident %s: opcode/insn_hex coupling mismatch" % a)
        ident[a] = r
    if ident["census31"]["orig_value"] != SMOKE_SLOT:
        raise SystemExit("ident census31 orig_value %d != frozen SMOKE_SLOT %d"
                         % (ident["census31"]["orig_value"], SMOKE_SLOT))
    return kernels, ident


# ---- per-case plumbing ---------------------------------------------------------
def write_case_archive(work, c, ident):
    """Write the per-case archive: the kernel's archive with at most ONE spliced
    byte (the probe instruction's selector byte for this case). Side-effectful;
    called by the runner immediately before the case process."""
    src = work / "archives" / ("%s.bin" % c["kernel"])
    data = bytearray(src.read_bytes())
    off = -1
    if c["spliced"]:
        base_abs = ident[c["kernel"]]["abs_off"] - ident[c["kernel"]]["selector_rel"]
        off = base_abs + c["sel_rel"]
        data[off] = c["slot"]
    dst = work / ("case_%04d.bin" % c["i"])
    dst.write_bytes(bytes(data))
    return dst, off


def case_argv(work, c, ident):
    """Pure: the exact argv of case c's harness process (mirrors write_case_archive)."""
    arc = work / ("case_%04d.bin" % c["i"])
    off = -1
    if c["spliced"]:
        k = ident[c["kernel"]]
        off = k["abs_off"] - k["selector_rel"] + c["sel_rel"]
    return [work / "bin/probe", "--source", HERE / ("kernels/%s.metal" % c["kernel"]),
            "--function", c["kernel"], "--archive", arc, "--op", c["op"],
            "--slot", str(c["slot"]), "--splice-abs-off", str(off),
            "--idxbuf", str(idxbuf_index(c["kernel"]))]


def _hex_ok(s, n):
    return isinstance(s, str) and len(s) == n and all(ch in "0123456789abcdef" for ch in s)


def case_line(c, z):
    """Build the one authoritative observation line for case c from receipt z.

    Pure function (used unchanged by verify.py's selftest). Hardware-level
    anomalies (command-buffer error, watchdog, kill, timeout) map to recorded
    statuses; a witness mismatch or an unexpected buffer change is an
    OBSERVATION recorded in the line; only harness-level defects (echo
    mismatch, malformed record) raise, because those make the record itself
    untrustworthy.
    """
    line = {k: None for k in CASE_KEYS}
    line.update({"i": c["i"], "name": c["name"], "kernel": c["kernel"], "op": c["op"],
                 "slot": c["slot"], "exit": z["exit"], "timed_out": z["timed_out"]})
    if z["timed_out"]:
        line.update({"status": "proc_timeout", "cb_status": None, "err": None,
                     "probe_word": "", "witness_ok": None, "changed": []})
        return line
    if z["exception"] is not None or z["exit"] is None:
        line.update({"status": "proc_fail", "cb_status": None, "err": None,
                     "probe_word": "", "witness_ok": None, "changed": []})
        return line
    p = None
    try:
        q = json.loads(z["stdout"])
        if isinstance(q, dict):
            p = q
    except ValueError:
        p = None
    if p is None:
        if z["exit"] in (97, 98):
            line.update({"status": "watchdog", "cb_status": None, "err": None,
                         "probe_word": "", "witness_ok": None, "changed": []})
        else:
            line.update({"status": "proc_fail", "cb_status": None, "err": None,
                         "probe_word": "", "witness_ok": None, "changed": []})
        return line
    if set(p) != SUMMARY_KEYS or p["schema"] != 1 or p["kernel"] != c["kernel"] \
            or p["op"] != c["op"] or p["slot"] != c["slot"] \
            or not _hex_ok(p["out_hex"], 2 * GEOMETRY["out_dump_bytes"]) \
            or set(p["bufs_hex"]) != {str(k) for k in range(GEOMETRY["n_buffers"])} \
            or not all(_hex_ok(p["bufs_hex"][str(k)], 2 * 4 * GEOMETRY["words_per_buffer"])
                       for k in range(GEOMETRY["n_buffers"])) \
            or not isinstance(p["pre_ok"], bool) or not isinstance(p["error"], str) \
            or not isinstance(p["command_buffer_status"], int) \
            or p["idxbuf"] != idxbuf_index(c["kernel"]) \
            or p["fast_math"] is not True:
        raise SystemExit("harness record defect for case %s: shape mismatch" % c["name"])
    out_words = [int.from_bytes(bytes.fromhex(p["out_hex"][2 * i * 4:2 * i * 4 + 8]),
                                "little") for i in range(GEOMETRY["out_dump_bytes"] // 4)]
    witness_ok = all(out_words[idx] == val for idx, val in witness_spec(c["kernel"]))
    changed = []
    for k in range(1, GEOMETRY["n_buffers"]):
        want = b"".join(v.to_bytes(4, "little") for v in fill_words(c["kernel"], k))
        if p["bufs_hex"][str(k)] != want.hex():
            changed.append(k)
    line.update({"status": "ok" if p["command_buffer_status"] == 4 else "cb_error",
                 "cb_status": p["command_buffer_status"], "err": p["error"],
                 "probe_word": p["out_hex"][0:8], "witness_ok": witness_ok,
                 "changed": changed})
    return line


def smoke_problems(z, c):
    """Pre-capture smoke validator (pure; exercised by verify.py --selftest).

    Asserts RECORD SHAPE ONLY plus integrity of the harness's own upload
    (pre_ok) -- no expectation on probe_word or witness_ok, which are the
    observations under test. Failure classes are pre-capture stops.
    """
    bad = []
    if z.get("timed_out") is not False:
        bad.append("smoke invocation timed out")
    if z.get("exception") is not None:
        bad.append("smoke OS exception: %r" % (z.get("exception"),))
    if z.get("exit") != 0:
        bad.append("smoke exit code %r" % (z.get("exit"),))
    out = z.get("stdout") or ""
    try:
        p = json.loads(out)
    except ValueError:
        return bad + ["smoke stdout is not exactly one JSON object (%d bytes)" % len(out)]
    if not isinstance(p, dict):
        return bad + ["smoke stdout is not a JSON object"]
    missing, extra = sorted(SUMMARY_KEYS - set(p)), sorted(set(p) - SUMMARY_KEYS)
    if missing or extra:
        return bad + ["smoke payload key set differs: missing=%s extra=%s" % (missing, extra)]
    if (p["schema"], p["kernel"], p["op"], p["slot"]) != (1, c["kernel"], c["op"], c["slot"]):
        bad.append("smoke identity mismatch")
    if p["device"] != "Apple M4" or p["machine"] != "arm64" or not isinstance(p["os"], str) or not p["os"]:
        bad.append("smoke device identity %r/%r" % (p.get("device"), p.get("machine")))
    if p["fast_math"] is not True or not isinstance(p["math_mode_raw"], int) \
            or not isinstance(p["language_version_raw"], int):
        bad.append("smoke compile record %r/%r/%r"
                   % (p.get("fast_math"), p.get("math_mode_raw"), p.get("language_version_raw")))
    if p["command_buffer_status"] != 4 or p["error"] != "":
        bad.append("smoke command buffer status %r error %r"
                   % (p.get("command_buffer_status"), p.get("error")))
    if p["pre_ok"] is not True:
        bad.append("smoke upload integrity pre_ok=%r" % (p.get("pre_ok"),))
    if not _hex_ok(p["out_hex"], 2 * GEOMETRY["out_dump_bytes"]):
        bad.append("smoke out_hex is not %d lowercase hex chars" % (2 * GEOMETRY["out_dump_bytes"]))
    if set(p["bufs_hex"]) != {str(k) for k in range(GEOMETRY["n_buffers"])} or \
            not all(_hex_ok(p["bufs_hex"][str(k)], 2 * 4 * GEOMETRY["words_per_buffer"])
                    for k in range(GEOMETRY["n_buffers"])):
        bad.append("smoke bufs_hex shape")
    if not isinstance(p["library_compile_seconds"], (int, float)) \
            or not isinstance(p["dispatch_seconds"], (int, float)) \
            or not isinstance(p["registry_id"], int):
        bad.append("smoke timing/registry grammar")
    return bad


def env_problems(env):
    bad = []
    for name in ("sw_vers", "xcrun_version"):
        z = env[name]
        if z["timed_out"] or z["exit"] != 0 or z["exception"] is not None:
            bad.append("environment command failed: " + name)
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id")
    ap.add_argument("--execute", action="store_true")
    a = ap.parse_args()
    if not a.execute:
        raise SystemExit("refusing device operation: pass --execute only after approved pre-GPU review")
    if a.run_id not in RUNS:
        raise SystemExit("run-id must be one contracted append-only ID: " + ", ".join(RUNS))
    for g in (("--selftest",), ("--preflight" if a.run_id == RUNS[0] else "--between-runs",)):
        if subprocess.run([sys.executable, "-B", "verify.py", g[0]], cwd=HERE).returncode:
            raise SystemExit("run gate failed: " + g[0])
    current = provenance()
    if a.run_id == RUNS[1]:
        first = json.loads((HERE / "raw" / RUNS[0] / "00_inputs.json").read_text())
        for k in ("git_revision", "git_dirty", "authored_code_sha256", "authored_doc_sha256"):
            if first.get(k) != current[k]:
                raise SystemExit("run02 provenance differs from closed run01: " + k)
    raw = HERE / "raw" / a.run_id
    work_root = HERE / "work"
    work = work_root / a.run_id
    if raw.exists():
        raise SystemExit("append-only raw path already exists")
    if work.exists() or (work_root.exists() and any(work_root.iterdir())):
        raise SystemExit("scratch path already exists or work is not empty")
    work.mkdir(parents=True)
    # --- everything up to raw.mkdir() is PRE-CAPTURE: a failure here writes a
    # retained work/<run-id>/STOP.json and never creates the append-only tree.
    try:
        env = {"schema": 1, **current,
               "sw_vers": rec(["sw_vers"], TIMEOUTS["env_command"]),
               "xcrun_version": rec(["xcrun", "--version"], TIMEOUTS["env_command"]),
               "python": sys.version.split()[0], "machine": platform.machine(),
               "boundary": BOUNDARY, "timeouts_seconds": TIMEOUTS, "geometry": GEOMETRY}
        if env_problems(env):
            put(work / "STOP.json", {"schema": 1, "phase": "environment",
                                     "problems": env_problems(env),
                                     "automatic_retry": False, "raw_created": False})
            raise SystemExit("pre-capture stop: environment")
        build = rec(build_argv(work), TIMEOUTS["host_build"])
        if build["timed_out"] or build["exit"] != 0 or build["exception"] is not None:
            put(work / "STOP.json", {"schema": 1, "phase": "host_build",
                                     "problems": ["host build failed"], "receipt": build,
                                     "automatic_retry": False, "raw_created": False})
            raise SystemExit("pre-capture stop: host build")
        try:
            kernels, ident = compile_and_identify(work)
        except SystemExit as e:
            put(work / "STOP.json", {"schema": 1, "phase": "identify",
                                     "problems": [str(e)], "automatic_retry": False,
                                     "raw_created": False})
            raise
        build_rec = {"schema": 1, "build": build,
                     "tools_sha256": {"tools/shdump/shdump.m": sha(TOOLS / "shdump/shdump.m"),
                                      "tools/shdump/agxparse.py": sha(TOOLS / "shdump/agxparse.py"),
                                      "tools/agx-isa/isadb.py": sha(TOOLS / "agx-isa/isadb.py")},
                     "kernels": kernels, "ident": ident}
        smoke_case = BY_NAME[SMOKE_CASE]
        d = work / "smoke"
        d.mkdir(parents=True)
        write_case_archive(work, smoke_case, ident)
        z = rec(case_argv(work, smoke_case, ident), TIMEOUTS["case_process"])
        put(d / "smoke.json", z)
        problems = smoke_problems(z, smoke_case)
        if problems:
            put(work / "STOP.json", {"schema": 1, "phase": "pre_capture_smoke",
                                     "case": SMOKE_CASE, "problems": problems,
                                     "automatic_retry": False, "raw_created": False})
            raise SystemExit("pre-capture stop: smoke gate (raw tree not created; "
                             "pre-capture repair authorized)")

        # The smoke gate passed: the capture may begin (append-only from here).
        raw.mkdir(parents=True)
        put(raw / "00_inputs.json", env)
        put(raw / "01_matrix.json", {"schema": 1, "run_id": a.run_id, "cases": CASES})
        put(raw / "02_build.json", build_rec)

        lines, receipts = [], []
        infra = 0
        stopped = None
        for c in CASES:
            write_case_archive(work, c, ident)
            z = rec(case_argv(work, c, ident), TIMEOUTS["case_process"])
            line = case_line(c, z)
            lines.append(json.dumps(line, sort_keys=True))
            receipts.append(json.dumps({"i": c["i"], "name": c["name"], **z}, sort_keys=True))
            if z["exception"] is not None:
                infra += 1
                if infra >= MAX_CONSECUTIVE_INFRA:
                    stopped = {"schema": 1, "phase": "consecutive_infra_failures",
                               "at_case": c["name"], "automatic_retry": False}
                    break
            else:
                infra = 0

        results_txt = "\n".join(lines) + "\n"
        receipts_txt = "\n".join(receipts) + "\n"
        (work / "results.jsonl").write_text(results_txt)
        (work / "receipts.jsonl").write_text(receipts_txt)
        counts = {s: sum(1 for l in lines if json.loads(l)["status"] == s)
                  for s in STATUS_VALUES}
        put(raw / "03_dispatch.json", {
            "schema": 1, "run_id": a.run_id, "cases_planned": TOTAL,
            "cases_recorded": len(lines), **{"n_%s" % s: counts[s] for s in STATUS_VALUES},
            "results_lines": len(lines), "results_sha256": sha(work / "results.jsonl")})
        shutil.move(str(work / "results.jsonl"), str(raw / "04_results.jsonl"))
        shutil.move(str(work / "receipts.jsonl"), str(raw / "05_receipts.jsonl"))
        put(raw / "06_run_manifest.json", {
            "schema": 1, "run_id": a.run_id, "cases_planned": TOTAL,
            "cases_recorded": len(lines), "runner_sha256": sha(HERE / "run.py"),
            "harness_sha256": sha(HERE / "harness/probe.m"),
            "kernel_sha256": {k: kernels[k]["archive_sha256"] for k in KERNEL_NAMES},
            "matrix_sha256": sha(raw / "01_matrix.json"),
            "build_sha256": sha(raw / "02_build.json"),
            "results_sha256": sha(raw / "04_results.jsonl"),
            "receipts_sha256": sha(raw / "05_receipts.jsonl")})
        if stopped is not None:
            put(raw / "STOP.json", stopped)
    finally:
        if not (work / "STOP.json").exists():
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
