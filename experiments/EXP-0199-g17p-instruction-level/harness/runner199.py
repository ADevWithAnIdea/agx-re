#!/usr/bin/env python3
"""runner199.py -- EXP-0199 persistent-runner drivers.

Derived from OUR OWN experiments/EXP-0172-g17p-onefield-tail/harness/runner2.py
(render protocol, InnocentVictim retry, response parsing) and OUR OWN
tools/agxtest/saferunner.py (the DEF-0178-1 fix).  Written fresh here rather
than imported so this experiment's harness is hash-pinned.

THE ONE THING THAT IS NOT COPIED: runner2.py's `_readline` starts a FRESH reader
thread per line and ABANDONS it on timeout, and the abandoned thread re-resolves
`self.proc` at execution time, so after the first watchdog timeout it wakes on
the REPLACEMENT child's stdout and races the foreground reader.  Per
FIELD-SWEEP-PROTOCOL sec.3(d) that defect manufactures a cascade of false
`hang`s from a single timeout -- a real hang is not even required.  Here there is
exactly ONE pump thread per child, tagged with the child it belongs to, and a
line from a dead child is discarded rather than mixed into the current response.

A truncated or unparseable response is returned with status MALFORMED and the
raw lines retained.  Per the same section it is a MEASUREMENT FAILURE: the
caller must score it `measurement_failed`, drop it from agreement and from
values_dispatched, and never as ok / fault / inert.

CLEAN-ROOM: process and protocol plumbing over our own OWN-SHADER runners.  No
Apple binary is inspected.
"""
import os
import queue
import signal
import subprocess
import threading
import time

FOREIGN = "InnocentVictim"
MAX_FOREIGN_RETRIES = 6
_HEXTAGS = ("PIX", "DEPTH", "TEXW", "OUTBUF", "OUT")


class _Child:
    """A persistent runner child with ONE pump thread, tagged by owner."""

    def __init__(self, cmd, ready_prefix="READY", ready_timeout=120):
        self.cmd = cmd
        self.ready_prefix = ready_prefix
        self.ready_timeout = ready_timeout
        self.proc = None
        self.restarts = 0
        self._q = queue.Queue()
        self._start()

    def _install_pump(self, proc):
        q = self._q

        def pump():
            try:
                for ln in iter(proc.stdout.readline, ""):
                    q.put((proc, ln))
            except Exception:
                pass
            q.put((proc, None))          # explicit EOF marker (DEF-0153-2)
        t = threading.Thread(target=pump, daemon=True)
        t.start()

    def _start(self):
        self.proc = subprocess.Popen(
            self.cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, bufsize=1, start_new_session=True)
        self._install_pump(self.proc)
        ln = self._read_line(self.ready_timeout)
        if not ln or not ln.startswith(self.ready_prefix):
            err = ""
            try:
                err = self.proc.stderr.read()
            except Exception:
                pass
            raise RuntimeError("child not ready: %r %s" % (ln, err))
        self.device = ln.split(None, 1)[1].strip() if " " in ln else "?"

    def _read_line(self, timeout):
        """One line from the CURRENT child, or None on timeout/EOF.  Lines from
        an earlier (killed) child are discarded, never mixed in."""
        deadline = time.time() + timeout
        while True:
            left = deadline - time.time()
            if left <= 0:
                return None
            try:
                owner, ln = self._q.get(timeout=left)
            except queue.Empty:
                return None
            if owner is not self.proc:
                continue                  # leftover from a dead child
            if ln is None:
                return None               # EOF
            return ln

    def kill(self):
        if self.proc and self.proc.poll() is None:
            try:
                os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
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


def render_cmd(frun, source, cfg, archive=None, scratch=None, build=None,
               vname="v_main", fname="f_main"):
    cmd = [frun, "--source", source, "--vertex", vname, "--fragment", fname,
           "--color-format", str(cfg["color_format"]),
           "--width", str(cfg["width"]), "--height", str(cfg["height"]),
           "--samples", str(cfg.get("samples", 1)),
           "--rt-count", str(cfg.get("rt_count", 1))]
    if build:
        cmd += ["--build-archive", build]
    else:
        cmd += ["--archive", archive, "--scratch", scratch, "--persist"]
    if cfg.get("depth"):
        cmd.append("--depth")
    if cfg.get("depth_clear") is not None:
        cmd += ["--depth-clear", str(cfg["depth_clear"])]
    if cfg.get("depth_compare") is not None:
        cmd += ["--depth-compare", str(cfg["depth_compare"])]
    if cfg.get("clear"):
        cmd += ["--clear", ",".join(str(v) for v in cfg["clear"])]
    return cmd


class RenderRunner(_Child):
    def __init__(self, frun, source, archive, scratch, cfg):
        self._n = 0
        super().__init__(render_cmd(frun, source, cfg, archive=archive,
                                    scratch=scratch))

    def render(self, splices, timeout=20.0):
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

    def _render1(self, splices, timeout):
        self._n += 1
        rid = "r%d" % self._n
        parts = [rid, str(len(splices))] + ["%d=%s" % (o, h) for o, h in splices]
        try:
            self.proc.stdin.write(" ".join(parts) + "\n")
            self.proc.stdin.flush()
        except (BrokenPipeError, ValueError):
            self.restart()
            return {"status": "HANG", "error": "child pipe broken",
                    "restarted": True, "surf": {}, "raw": []}
        out = {"status": "UNKNOWN", "restarted": False, "surf": {},
               "missing": [], "raw": []}
        while True:
            ln = self._read_line(timeout)
            if ln is None:
                self.restart()
                out["status"] = "HANG"
                out["error"] = "no response within %ss" % timeout
                out["restarted"] = True
                return out
            ln = ln.rstrip("\n")
            out["raw"].append(ln)
            if ln.startswith("STATUS "):
                out["status"] = ln.split(None, 1)[1]
            elif ln.startswith("ACTUAL "):
                # GATE A: the bytes actually present in the dispatched file.
                q = ln.split(None, 2)
                if len(q) == 3:
                    try:
                        out.setdefault("actual", {})[int(q[1])] = bytes.fromhex(q[2])
                    except ValueError:
                        out["status"] = "MALFORMED"
                        out["error"] = "unparseable ACTUAL payload"
                        return out
            elif ln.startswith("SENTINEL "):
                out["sentinel"] = ln.split(None, 1)[1]
            elif ln.startswith("ERRDOM "):
                out["errdom"] = ln.split(None, 1)[1]
            elif ln.startswith("ERROR "):
                out["error"] = ln.split(None, 1)[1]
            elif ln.startswith("DONE "):
                return out
            elif any(ln.startswith(t) for t in _HEXTAGS):
                tag, _, rest = ln.partition(" ")
                if tag.endswith("_UNAVAILABLE"):
                    out["missing"].append(tag)
                    continue
                try:
                    out["surf"][tag] = bytes.fromhex(rest)
                except ValueError:
                    out["status"] = "MALFORMED"
                    out["error"] = "unparseable %s payload" % tag
                    return out


def compute_cmd(crun, source, function, archive, scratch, in_file, out_bytes,
                grid, tg, fast_math=True):
    cmd = [crun, "--source", source, "--function", function,
           "--archive", archive, "--scratch", scratch,
           "--grid", str(grid), "--tg", str(tg),
           "--in", "1=%s" % in_file, "--out", "0=%d" % out_bytes, "--persist"]
    if not fast_math:
        cmd.append("--no-fast-math")
    return cmd


class ComputeRunner(_Child):
    """harness/crun199.m protocol: `<reqid> <nsplices> [<off>=<hex> ...]`."""

    def __init__(self, crun, source, function, archive, scratch, in_file,
                 out_bytes, grid, tg, fast_math=True):
        self._n = 0
        super().__init__(compute_cmd(crun, source, function, archive, scratch,
                                     in_file, out_bytes, grid, tg, fast_math))

    def run(self, splices, timeout=20.0):
        for attempt in range(MAX_FOREIGN_RETRIES + 1):
            out = self._run1(splices, timeout)
            if not (out.get("status") == "CMDBUF_ERROR"
                    and FOREIGN in out.get("error", "")):
                if attempt:
                    out["foreign_retries"] = attempt
                return out
            time.sleep(0.25 * (attempt + 1))
        out["foreign_retries"] = MAX_FOREIGN_RETRIES
        out["status"] = "FOREIGN_FAULT"
        return out

    def _run1(self, splices, timeout):
        self._n += 1
        rid = "c%d" % self._n
        parts = [rid, str(len(splices))] + ["%d=%s" % (o, h) for o, h in splices]
        try:
            self.proc.stdin.write(" ".join(parts) + "\n")
            self.proc.stdin.flush()
        except (BrokenPipeError, ValueError):
            self.restart()
            return {"status": "HANG", "error": "child pipe broken",
                    "restarted": True, "surf": {}, "raw": []}
        out = {"status": "UNKNOWN", "restarted": False, "surf": {}, "raw": []}
        while True:
            ln = self._read_line(timeout)
            if ln is None:
                self.restart()
                out["status"] = "HANG"
                out["error"] = "no response within %ss" % timeout
                out["restarted"] = True
                return out
            ln = ln.rstrip("\n")
            out["raw"].append(ln)
            if ln.startswith("STATUS "):
                out["status"] = ln.split(None, 1)[1]
            elif ln.startswith("ACTUAL "):
                # GATE A: the bytes actually present in the dispatched file.
                q = ln.split(None, 2)
                if len(q) == 3:
                    try:
                        out.setdefault("actual", {})[int(q[1])] = bytes.fromhex(q[2])
                    except ValueError:
                        out["status"] = "MALFORMED"
                        out["error"] = "unparseable ACTUAL payload"
                        return out
            elif ln.startswith("SENTINEL "):
                out["sentinel"] = ln.split(None, 1)[1]
            elif ln.startswith("OUT "):
                p = ln.split(None, 2)
                if len(p) < 3:
                    # DEF-0178-1: a truncated OUT is a MEASUREMENT FAILURE, not
                    # an observation and not a hang.  Keep the raw lines.
                    out["status"] = "MALFORMED"
                    out["error"] = "truncated OUT line"
                    return out
                try:
                    out["surf"]["OUT%s" % p[1]] = bytes.fromhex(p[2])
                except ValueError:
                    out["status"] = "MALFORMED"
                    out["error"] = "unparseable OUT payload"
                    return out
            elif ln.startswith("ERRDOM "):
                out["errdom"] = ln.split(None, 1)[1]
            elif ln.startswith("ERROR "):
                out["error"] = ln.split(None, 1)[1]
            elif ln.startswith("GPUTIME_NS "):
                out["gputime"] = int(ln.split()[1])
            elif ln.startswith("DONE "):
                return out
