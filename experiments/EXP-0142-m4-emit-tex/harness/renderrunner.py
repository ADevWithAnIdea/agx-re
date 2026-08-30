#!/usr/bin/env python3
"""EXP-0142 driver for harness/renderpersist (persistent RENDER runner).

Same relationship to tools/agxtest/persistrun.py as harness/texrunner.py: reuse
PersistRunner's process management and per-request watchdog (FIELD-SWEEP-PROTOCOL
section 2), override the request encoding for the render protocol
(`<id> <archive> <nin> [idx:file ...]` -> `PIXELS <hex RGBA32F WxH>`).

CLEAN-ROOM: process/protocol plumbing over our own OWN-SHADER runner.
"""
import os
import sys

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(_REPO, "tools", "agxtest"))
from persistrun import PersistRunner  # noqa: E402


class RenderRunner(PersistRunner):
    def __init__(self, source, vertex, fragment, exe, width=4, height=4,
                 restart_hook=None):
        self.vertex, self.fragment = vertex, fragment
        self.width, self.height = width, height
        self.restarts = 0
        super().__init__(source=source, function=fragment, fast_math=True,
                         agxrun_persist=exe, restart_hook=restart_hook)

    def _start(self):
        import subprocess
        cmd = [self.exe, "--source", self.source,
               "--vertex", self.vertex, "--fragment", self.fragment,
               "--width", str(self.width), "--height", str(self.height)]
        self.proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, bufsize=1, start_new_session=True)
        ready = self._read_line(timeout=60)
        if not ready or not ready.startswith("READY"):
            err = self.proc.stderr.read() if self.proc.stderr else ""
            raise RuntimeError(f"renderpersist did not become READY: {ready!r} {err}")
        self.device = ready.split(None, 1)[1].strip() if " " in ready else "?"

    def request(self, archive, ins, timeout=8.0):
        self._reqno += 1
        rid = f"r{self._reqno}"
        parts = [rid, archive, str(len(ins))]
        for idx, path in ins.items():
            parts.append(f"{idx}:{path}")
        line = " ".join(parts) + "\n"
        try:
            self.proc.stdin.write(line)
            self.proc.stdin.flush()
        except (BrokenPipeError, ValueError):
            self._restart_after_wedge()
            self.restarts += 1
            return {"status": "HANG", "pixels": None, "errdom": None,
                    "error": "child pipe broken", "restarted": True}

        resp = {"status": "UNKNOWN", "pixels": None, "errdom": None,
                "error": None, "restarted": False}
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
            elif ln.startswith("PIXELS "):
                resp["pixels"] = bytes.fromhex(ln.split(None, 1)[1])
            elif ln.startswith("ERRDOM "):
                resp["errdom"] = ln.split(None, 1)[1]
            elif ln.startswith("ERROR "):
                resp["error"] = ln.split(None, 1)[1]
            elif ln.startswith("DONE "):
                break
        return resp
