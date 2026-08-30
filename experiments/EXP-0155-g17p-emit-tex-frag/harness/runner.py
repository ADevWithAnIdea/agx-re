#!/usr/bin/env python3
"""runner.py -- EXP-0155 persistent-runner drivers with per-request watchdogs.

Derived unchanged in structure from OUR OWN EXP-0143 harness/runner.py; the
additions here are the texture-carrier command-line flags, the buffer(0)
binding, the ERRDOM (OS fault classification) line and the TEXW read-back.

Two thin process drivers:
  RenderRunner  -> harness/gfrun.m  (render + splice + readback + textures)
  ComputeRunner -> tools/agxtest/agxrun_persist.m (compute, EXP-0005 tool)

Both keep ONE live MTLDevice for the process lifetime and kill+restart the child
on a watchdog timeout, so a GPU wedge costs one case, not the sweep.

CLEAN-ROOM: process/protocol plumbing over our own OWN-SHADER runners.
"""
import os
import signal
import subprocess
import threading
import time

# A command buffer discarded as "InnocentVictim" was NOT faulted by our own
# splice: another GPU client on this host faulted and the driver's recovery
# discarded ours as collateral.  Other experiments sweep this GPU concurrently,
# so these are retried (bounded, with backoff) and the retry count is recorded.
FOREIGN = "InnocentVictim"
MAX_FOREIGN_RETRIES = 8


class _Child:
    def __init__(self, cmd, ready_prefix="READY", ready_timeout=60):
        self.cmd = cmd
        self.ready_prefix = ready_prefix
        self.ready_timeout = ready_timeout
        self.proc = None
        self.restarts = 0
        self._start()

    def _start(self):
        self.proc = subprocess.Popen(
            self.cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, bufsize=1, start_new_session=True)
        ln = self._readline(self.ready_timeout)
        if not ln or not ln.startswith(self.ready_prefix):
            err = ""
            try:
                err = self.proc.stderr.read()
            except Exception:
                pass
            raise RuntimeError(f"child not ready: {ln!r} {err}")
        self.device = ln.split(None, 1)[1].strip() if " " in ln else "?"

    def _readline(self, timeout):
        """Read one line, or None on timeout OR on a DEAD CHILD.

        BUG FIX (EXP-0153, 2026-08-29): returning readline()'s raw result meant
        an exited child produced "" -- not None -- forever, which matched none of
        the caller's branches and span at 100% CPU with no timeout.  A closed
        stdout is a wedge, so it must read as None like a timeout does.  The same
        defect was found and fixed in the shared tools/agxtest/persistrun.py."""
        box = [None]

        def rd():
            try:
                box[0] = self.proc.stdout.readline()
            except Exception:
                box[0] = None
        t = threading.Thread(target=rd, daemon=True)
        t.start()
        t.join(timeout)
        if t.is_alive():
            return None
        if not box[0]:          # "" == EOF == the child is gone
            return None
        return box[0]

    def kill(self):
        if self.proc and self.proc.poll() is None:
            try:
                os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
        try:
            self.proc.wait(timeout=10)
        except Exception:
            pass

    def restart(self):
        self.kill()
        self.restarts += 1
        self._start()

    def close(self):
        try:
            if self.proc and self.proc.stdin:
                self.proc.stdin.close()
            if self.proc:
                self.proc.wait(timeout=10)
        except Exception:
            self.kill()


class RenderRunner(_Child):
    """One live render device; requests are `<id> <nsplices> [off=hex ...]`."""

    def __init__(self, frun, source, archive, scratch, cfg, buf0=None):
        cmd = [frun, "--source", source, "--vertex", "v_main", "--fragment", "f_main",
               "--archive", archive, "--scratch", scratch,
               "--color-format", str(cfg["color_format"]),
               "--width", str(cfg["width"]), "--height", str(cfg["height"]),
               "--samples", str(cfg.get("samples", 1)), "--persist"]
        if cfg.get("depth"):
            cmd.append("--depth")
        if cfg.get("resolve"):
            cmd.append("--resolve")
        if cfg.get("tex_sample"):
            cmd += ["--tex-sample", "%d,%d" % cfg["tex_sample"]]
        if cfg.get("tex_write"):
            cmd += ["--tex-write", "%d,%d" % cfg["tex_write"]]
        if cfg.get("tex_depth"):
            cmd += ["--tex-depth", "%d,%d" % cfg["tex_depth"]]
        if cfg.get("tex_extra"):
            cmd.append("--tex-extra")
        if cfg.get("clear"):
            cmd += ["--clear", ",".join(str(v) for v in cfg["clear"])]
        if cfg.get("buf0") and buf0:
            cmd += ["--buf-u32", "0=" + ",".join(str(v) for v in buf0)]
        self._n = 0
        super().__init__(cmd)

    def render(self, splices, timeout=15.0):
        for attempt in range(MAX_FOREIGN_RETRIES + 1):
            out = self._render1(splices, timeout)
            if not (out.get("status") == "CMDBUF_ERROR"
                    and FOREIGN in out.get("error", "")):
                if attempt:
                    out["foreign_retries"] = attempt
                return out
            time.sleep(0.25 * (attempt + 1))
        out["foreign_retries"] = MAX_FOREIGN_RETRIES
        out["status"] = "FOREIGN_FAULT"
        return out

    def _render1(self, splices, timeout=15.0):
        self._n += 1
        rid = f"r{self._n}"
        parts = [rid, str(len(splices))] + [f"{o}={h}" for o, h in splices]
        try:
            self.proc.stdin.write(" ".join(parts) + "\n")
            self.proc.stdin.flush()
        except (BrokenPipeError, ValueError):
            self.restart()
            return {"status": "HANG", "error": "child pipe broken", "restarted": True}
        out = {"status": "UNKNOWN", "restarted": False}
        while True:
            ln = self._readline(timeout)
            if ln is None:
                self.restart()
                out["status"] = "HANG"
                out["error"] = f"no response within {timeout}s"
                out["restarted"] = True
                return out
            ln = ln.rstrip("\n")
            if ln.startswith("STATUS "):
                out["status"] = ln.split(None, 1)[1]
            elif ln.startswith("SENTINEL "):
                out["sentinel"] = ln.split(None, 1)[1]
            elif ln.startswith("PIX"):
                tag, hexs = ln.split(None, 1)
                out.setdefault("pix", {})[tag] = bytes.fromhex(hexs)
            elif ln.startswith("DEPTH "):
                out["depth"] = bytes.fromhex(ln.split(None, 1)[1])
            elif ln.startswith("OCC "):
                out["occ"] = int(ln.split()[1])
            elif ln.startswith("TEXW "):
                out["texw"] = bytes.fromhex(ln.split(None, 1)[1])
            elif ln.startswith("ERRDOM "):
                out["errdom"] = ln.split(None, 1)[1]
            elif ln.startswith("ERROR "):
                out["error"] = ln.split(None, 1)[1]
            elif ln.startswith("DONE "):
                return out


class ComputeRunner(_Child):
    """tools/agxtest/agxrun_persist protocol."""

    def __init__(self, exe, source, function, in_file, out_bytes, grid, tg):
        self.in_file = in_file
        self.out_bytes = out_bytes
        self.grid = grid
        self.tg = tg
        self._n = 0
        super().__init__([exe, "--source", source, "--function", function])

    def run(self, archive, timeout=15.0):
        for attempt in range(MAX_FOREIGN_RETRIES + 1):
            out = self._run1(archive, timeout)
            if not (out.get("status") == "CMDBUF_ERROR"
                    and FOREIGN in out.get("error", "")):
                if attempt:
                    out["foreign_retries"] = attempt
                return out
            time.sleep(0.25 * (attempt + 1))
        out["foreign_retries"] = MAX_FOREIGN_RETRIES
        out["status"] = "FOREIGN_FAULT"
        return out

    def _run1(self, archive, timeout=15.0):
        self._n += 1
        rid = f"c{self._n}"
        line = f"{rid} {archive} {self.grid} {self.tg} 1 1:{self.in_file} 1 0:{self.out_bytes}\n"
        try:
            self.proc.stdin.write(line)
            self.proc.stdin.flush()
        except (BrokenPipeError, ValueError):
            self.restart()
            return {"status": "HANG", "error": "child pipe broken", "restarted": True}
        out = {"status": "UNKNOWN", "restarted": False}
        while True:
            ln = self._readline(timeout)
            if ln is None:
                self.restart()
                out["status"] = "HANG"
                out["error"] = f"no response within {timeout}s"
                out["restarted"] = True
                return out
            ln = ln.rstrip("\n")
            if ln.startswith("STATUS "):
                out["status"] = ln.split(None, 1)[1]
            elif ln.startswith("OUT "):
                _, idx, hexs = ln.split(None, 2)
                out["out"] = bytes.fromhex(hexs)
            elif ln.startswith("ERROR "):
                out["error"] = ln.split(None, 1)[1]
            elif ln.startswith("DONE "):
                return out
