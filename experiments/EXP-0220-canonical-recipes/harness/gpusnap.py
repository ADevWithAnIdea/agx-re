#!/usr/bin/env python3
"""EXP-0213 -- one device counter snapshot.  RUNS ON THE NEO.

    python3 gpusnap.py <tag>      # appends one JSON line to stdout

Records the AGXAcceleratorG17P driver-published counters that matter for Gate E:
`recoveryCount` (cumulative DEVICE RESETS -- the event that discards another
context's in-flight command buffers), `fLastSubmissionPID`, `fBusyCount`,
`fSubmissionsSinceLastCheck` and the utilization percentages.

EXP-0210's AMENDMENT-03 showed that "recoveryCount unchanged" is a gate NO
fault-heavy experiment can pass, because our OWN pre-registered illegal encodings
reset the device.  This tool therefore only RECORDS the counters; the gate lives
in quietcheck.py and is stated on foreign attribution, not on the raw delta.

Reading IOKit registry PROPERTIES is black-box data observation (CLAUDE.md
allowed technique 1).  No Apple binary is disassembled or introspected.
"""
import json
import re
import subprocess
import sys
import time

NUM = {
    "device_util": r'"Device Utilization %"=(\d+)',
    "renderer_util": r'"Renderer Utilization %"=(\d+)',
    "tiler_util": r'"Tiler Utilization %"=(\d+)',
    "recovery_count": r'"recoveryCount"=(\d+)',
    "last_recovery_time": r'"lastRecoveryTime"=(\d+)',
    "last_submission_pid": r'"fLastSubmissionPID"=(\d+)',
    "submissions_since_check": r'"fSubmissionsSinceLastCheck"=(\d+)',
    "busy_count": r'"fBusyCount"=(\d+)',
}


def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else "snap"
    rec = {"tag": tag, "ts": round(time.time(), 3),
           "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    try:
        out = subprocess.check_output(
            ["ioreg", "-rc", "AGXAcceleratorG17P", "-d", "1", "-w", "0"],
            text=True, timeout=25, stderr=subprocess.DEVNULL)
    except Exception as e:                                          # noqa: BLE001
        rec["ioreg_error"] = str(e)[:160]
        print(json.dumps(rec, sort_keys=True))
        return 1
    for k, pat in NUM.items():
        m = re.search(pat, out)
        rec[k] = int(m.group(1)) if m else None
    print(json.dumps(rec, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
