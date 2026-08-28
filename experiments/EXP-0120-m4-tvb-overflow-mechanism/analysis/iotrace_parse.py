"""Parse tools/iotrace/iotrace.c log output (our own DATA-TRACE captures).

Pure parsing, no interpretation. Two things are extracted:
  - selector_histogram: {selector_int: call_count} over the WHOLE log (both
    CALL and its matching RET share one selector; only CALL lines are counted
    so each call counts once).
  - bo_list: every BODUMP line's (handle, gpu_va, cpu, size, read) -- from the
    tool's own dedup'd g_bo[] table, not re-derived from raw struct hex (the
    tool already does that parsing; re-deriving here would just be a second,
    less trustworthy implementation of the same offsets).

GPU VA / CPU address fields are captured but the caller (analyze.py) decides
what is included in the byte-exact gate payload (size-multiset only, per
CAPTURE_CONTRACT.json).
"""
import re

CALL_RE = re.compile(r"^CALL seq=(\d+) fn=(\S+) conn=(\S+) class=(\S+) sel=(\d+)\(0x([0-9a-f]+)\)")
BODUMP_RE = re.compile(
    r"^BODUMP handle=(\d+) gpu_va=0x([0-9a-f]+) cpu=0x([0-9a-f]+) size=0x([0-9a-f]+) read=0x([0-9a-f]+)")
BODUMP_BEGIN_RE = re.compile(r"^BODUMP begin reason=(\S+) n_bo=(\d+)")


def parse_iotrace_log(path):
    selector_histogram = {}
    bo_list = []
    total_calls = 0
    calls_after_first_bodump = 0
    first_bodump_line = None
    with open(path, "r", errors="replace") as f:
        for lineno, line in enumerate(f):
            m = CALL_RE.match(line)
            if m:
                sel = int(m.group(5))
                selector_histogram[sel] = selector_histogram.get(sel, 0) + 1
                total_calls += 1
                if first_bodump_line is not None:
                    calls_after_first_bodump += 1
                continue
            m = BODUMP_BEGIN_RE.match(line)
            if m and first_bodump_line is None:
                first_bodump_line = lineno
                continue
            m = BODUMP_RE.match(line)
            if m:
                bo_list.append({
                    "handle": int(m.group(1)),
                    "gpu_va": int(m.group(2), 16),
                    "cpu": int(m.group(3), 16),
                    "size": int(m.group(4), 16),
                    "read": int(m.group(5), 16),
                })
    return {
        "selector_histogram": selector_histogram,
        "total_calls": total_calls,
        "sel9_calls": selector_histogram.get(9, 0),
        "bo_list": bo_list,
        "n_bo": len(bo_list),
        "size_multiset": sorted(b["size"] for b in bo_list),
        "calls_after_first_bodump": calls_after_first_bodump,
        "had_bodump": first_bodump_line is not None,
    }
