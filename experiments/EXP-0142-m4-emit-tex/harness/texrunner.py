#!/usr/bin/env python3
"""EXP-0142 driver for harness/texpersist (persistent texture-capable runner).

Reuses tools/agxtest/persistrun.py's PersistRunner for process management and
its per-request watchdog (the protocol contract of FIELD-SWEEP-PROTOCOL.md
section 2); overrides the request encoding to add texture readback and the
startup argv to add texture geometry.

CLEAN-ROOM: process/protocol plumbing over our own OWN-SHADER runner.
"""
import os
import sys

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(_REPO, "tools", "agxtest"))
from persistrun import PersistRunner  # noqa: E402


class TexRunner(PersistRunner):
    def __init__(self, source, function, exe, fast_math=True,
                 samp_w=16, samp_h=16, write_w=8, write_h=8, restart_hook=None):
        self.samp_w, self.samp_h = samp_w, samp_h
        self.write_w, self.write_h = write_w, write_h
        self.restarts = 0
        super().__init__(source=source, function=function, fast_math=fast_math,
                         agxrun_persist=exe, restart_hook=restart_hook)

    def _start(self):
        import subprocess
        cmd = [self.exe, "--source", self.source, "--function", self.function,
               "--samp-w", str(self.samp_w), "--samp-h", str(self.samp_h),
               "--write-w", str(self.write_w), "--write-h", str(self.write_h)]
        if not self.fast_math:
            cmd.append("--no-fast-math")
        self.proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, bufsize=1, start_new_session=True)
        ready = self._read_line(timeout=60)
        if not ready or not ready.startswith("READY"):
            err = self.proc.stderr.read() if self.proc.stderr else ""
            raise RuntimeError(f"texpersist did not become READY: {ready!r} {err}")
        self.device = ready.split(None, 1)[1].strip() if " " in ready else "?"

    def request(self, archive, grid, tg, ins, outs, texread=False, timeout=8.0):
        self._reqno += 1
        rid = f"r{self._reqno}"
        parts = [rid, archive, str(grid), str(tg), str(len(ins))]
        for idx, path in ins.items():
            parts.append(f"{idx}:{path}")
        parts.append(str(len(outs)))
        for idx, nbytes in outs.items():
            parts.append(f"{idx}:{nbytes}")
        parts.append("1" if texread else "0")
        line = " ".join(parts) + "\n"
        try:
            self.proc.stdin.write(line)
            self.proc.stdin.flush()
        except (BrokenPipeError, ValueError):
            self._restart_after_wedge()
            self.restarts += 1
            return {"status": "HANG", "outs": {}, "tex": None, "gputime_ns": None,
                    "error": "child pipe broken", "restarted": True}

        resp = {"status": "UNKNOWN", "outs": {}, "tex": None,
                "gputime_ns": None, "error": None, "restarted": False}
        while True:
            ln = self._read_line(timeout)
            if ln is None:
                self._restart_after_wedge()
                self.restarts += 1
                resp["status"] = "HANG"
                resp["error"] = f"no response within {timeout}s (GPU wedged)"
                resp["restarted"] = True
                return resp
            ln = ln.rstrip("\n")
            if ln.startswith("STATUS "):
                resp["status"] = ln.split(None, 1)[1]
            elif ln.startswith("GPUTIME_NS "):
                resp["gputime_ns"] = int(ln.split(None, 1)[1])
            elif ln.startswith("OUT "):
                _, idx, hexb = ln.split(None, 2)
                resp["outs"][int(idx)] = bytes.fromhex(hexb)
            elif ln.startswith("TEXOUT "):
                resp["tex"] = bytes.fromhex(ln.split(None, 1)[1])
            elif ln.startswith("ERROR "):
                resp["error"] = ln.split(None, 1)[1]
            elif ln.startswith("DONE "):
                break
        return resp
