#!/usr/bin/env python3
"""runner3.py -- EXP-0168 persistent render-runner driver (RENDER arm).

LINEAGE, all of it OUR OWN code in this repository:
  experiments/EXP-0143-.../harness/runner.py     first persistent RENDER loop
  experiments/EXP-0155-.../harness/runner.py     texture surfaces
  experiments/EXP-0163-.../harness/runner2.py    <-- DIRECT PARENT: the watchdog,
                                                 the dead-child EOF fix
                                                 (EXP-0153), the InnocentVictim
                                                 retry policy
                                                 (FIELD-SWEEP-PROTOCOL sec.7.2),
                                                 the per-slice / writable-texture
                                                 / OUTBUF surface tags and the
                                                 `PIX<n>_UNAVAILABLE` missing-
                                                 surface record.

Everything runner2.py had is preserved. runner3.py adds exactly what gfrun3.m's
four additions need, plus one robustness fix:

  * `--instances`, `--texw-reset`, `--texwu-reset` on the command line;
  * per-request `@inst=` / `@buf<i>=` overrides on `RenderRunner.render(...)`,
    and the `OVR <idx> applied|skipped` acknowledgements recorded per request so
    a data-ladder case can never be scored as inert because its data silently
    did not change;
  * the startup handshake tolerates (and records) the `TARGET ...` line gfrun3.m
    prints before `READY`, so the capture carries the device identity read from
    the live device rather than a literal;
  * `restarts_at` records the case index of every child restart, because
    EXP-0163's manifest reported only a count and a restart is exactly the event
    that separates two observations that ought to be comparable.

CLEAN-ROOM: process/protocol plumbing over our own OWN-SHADER runners. No Apple
binary is disassembled or introspected.
"""
import os
import signal
import subprocess
import threading
import time

FOREIGN = "InnocentVictim"
MAX_FOREIGN_RETRIES = 8

# Every response line prefix that carries a raw byte surface.
_HEXTAGS = ("PIX", "DEPTH", "TEXW", "OUTBUF")


class _Child:
    def __init__(self, cmd, ready_prefix="READY", ready_timeout=90):
        self.cmd = cmd
        self.ready_prefix = ready_prefix
        self.ready_timeout = ready_timeout
        self.proc = None
        self.restarts = 0
        self.restarts_at = []
        self.target_line = ""
        self._start()

    def _start(self):
        self.proc = subprocess.Popen(
            self.cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, bufsize=1, start_new_session=True)
        # gfrun3.m prints `TARGET <name> registryID=... instances=...` before
        # READY. Skip (and keep) any number of pre-READY informational lines, but
        # bound the loop so a wedged child still fails fast.
        ln = None
        for _ in range(8):
            ln = self._readline(self.ready_timeout)
            if ln is None:
                break
            if ln.startswith("TARGET "):
                self.target_line = ln.strip()
                continue
            break
        if not ln or not ln.startswith(self.ready_prefix):
            err = ""
            try:
                err = self.proc.stderr.read()
            except Exception:
                pass
            raise RuntimeError("child not ready: %r %s" % (ln, err))
        self.device = ln.split(None, 1)[1].strip() if " " in ln else "?"

    def _readline(self, timeout):
        """One line, or None on timeout OR on a dead child (EXP-0153 fix: a
        closed stdout returns '' forever and must read as None, or the caller
        spins at 100% CPU with no timeout)."""
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
        if not box[0]:
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

    def restart(self, at=None):
        self.kill()
        self.restarts += 1
        self.restarts_at.append(at if at is not None else -1)
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
               buf0=None, vname="v_main", fname="f_main"):
    """The EXACT command line for a carrier, used for BOTH --build-archive and
    the persistent run, so MTLPipelineOptionFailOnBinaryArchiveMiss can never
    miss on a descriptor mismatch (sample count, depth format, MRT count)."""
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
    if cfg.get("resolve"):
        cmd.append("--resolve")
    if cfg.get("rt_array"):
        cmd += ["--rt-array", str(cfg["rt_array"])]
    if cfg.get("tex_sample"):
        cmd += ["--tex-sample", "%d,%d" % cfg["tex_sample"]]
    if cfg.get("tex_write"):
        cmd += ["--tex-write", "%d,%d" % cfg["tex_write"]]
    if cfg.get("tex_depth"):
        cmd += ["--tex-depth", "%d,%d" % cfg["tex_depth"]]
    if cfg.get("tex_extra"):
        cmd.append("--tex-extra")
    if cfg.get("tex_write_arr"):
        cmd += ["--tex-write-arr", "%d,%d,%d" % cfg["tex_write_arr"]]
    if cfg.get("tex_write_3d"):
        cmd += ["--tex-write-3d", "%d,%d,%d" % cfg["tex_write_3d"]]
    if cfg.get("tex_write_half"):
        cmd += ["--tex-write-half", "%d,%d" % cfg["tex_write_half"]]
    if cfg.get("tex_write_uint"):
        cmd += ["--tex-write-uint", "%d,%d" % cfg["tex_write_uint"]]
    if cfg.get("clear"):
        cmd += ["--clear", ",".join(str(v) for v in cfg["clear"])]
    if cfg.get("out_buf"):
        cmd += ["--out-buf", "%d=%d" % cfg["out_buf"]]
    # ---- EXP-0168 additions -------------------------------------------------
    if cfg.get("instances"):
        cmd += ["--instances", str(cfg["instances"])]
    if cfg.get("texw_reset"):
        cmd += ["--texw-reset", ",".join(repr(float(v)) for v in cfg["texw_reset"])]
    if cfg.get("texwu_reset"):
        cmd += ["--texwu-reset", ",".join(str(int(v)) for v in cfg["texwu_reset"])]
    if buf0:
        cmd += ["--buf-u32", "0=" + ",".join(str(v) for v in buf0)]
    return cmd


class RenderRunner(_Child):
    def __init__(self, frun, source, archive, scratch, cfg, buf0=None,
                 vname="v_main", fname="f_main"):
        self._n = 0
        self.cfg = cfg
        super().__init__(render_cmd(frun, source, cfg, archive=archive,
                                    scratch=scratch, buf0=buf0,
                                    vname=vname, fname=fname))

    def render(self, splices, timeout=15.0, bufs=None, instances=None, at=None):
        """`splices`  : [(abs_off, hexbytes), ...]
        `bufs`     : {buffer_index: bytes}  -- overwrite the leading bytes of
                     that --buf-u32 buffer for THIS request only (data ladder)
        `instances`: override the instance count for THIS request only
        """
        for attempt in range(MAX_FOREIGN_RETRIES + 1):
            out = self._render1(splices, timeout, bufs, instances, at)
            if not (out.get("status") == "CMDBUF_ERROR"
                    and FOREIGN in out.get("error", "")):
                if attempt:
                    out["foreign_retries"] = attempt
                return out
            time.sleep(0.25 * (attempt + 1))
        out["foreign_retries"] = MAX_FOREIGN_RETRIES
        out["status"] = "FOREIGN_FAULT"
        return out

    def _render1(self, splices, timeout=15.0, bufs=None, instances=None, at=None):
        self._n += 1
        rid = "r%d" % self._n
        parts = [rid, str(len(splices))] + ["%s=%s" % (o, h) for o, h in splices]
        if instances is not None:
            parts.append("@inst=%d" % instances)
        for idx in sorted(bufs or {}):
            parts.append("@buf%d=%s" % (idx, bufs[idx].hex()))
        try:
            self.proc.stdin.write(" ".join(parts) + "\n")
            self.proc.stdin.flush()
        except (BrokenPipeError, ValueError):
            self.restart(at)
            return {"status": "HANG", "error": "child pipe broken", "restarted": True,
                    "surf": {}, "missing": [], "ovr": []}
        out = {"status": "UNKNOWN", "restarted": False, "surf": {}, "missing": [],
               "ovr": []}
        while True:
            ln = self._readline(timeout)
            if ln is None:
                self.restart(at)
                out["status"] = "HANG"
                out["error"] = "no response within %ss" % timeout
                out["restarted"] = True
                return out
            ln = ln.rstrip("\n")
            if ln.startswith("STATUS "):
                out["status"] = ln.split(None, 1)[1]
            elif ln.startswith("SENTINEL "):
                out["sentinel"] = ln.split(None, 1)[1]
            elif ln.startswith("OVR "):
                out["ovr"].append(ln.split(None, 1)[1])
            elif ln.startswith("ERRDOM "):
                out["errdom"] = ln.split(None, 1)[1]
            elif ln.startswith("ERROR "):
                out["error"] = ln.split(None, 1)[1]
            elif ln.startswith("OCC "):
                out["occ"] = int(ln.split()[1])
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
                    out["missing"].append(tag)
