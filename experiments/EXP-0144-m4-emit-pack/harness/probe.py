#!/usr/bin/env python3
"""EXP-0144 splice-and-run probe.

Thin driver over the EXISTING repo tools (tools/shdump/shdump.m + agxparse.py,
tools/agxtest/agxrun_persist.m + persistrun.py). Nothing is rebuilt: this file
only (a) compiles one of OUR OWN MSL entry points to a Metal binary archive,
(b) locates `_agc.main` in it, (c) writes a copy of that archive with caller-
chosen bytes overwritten in place, (d) issues it to the persistent runner.

CLEAN-ROOM: every byte spliced or executed is the compiled form of MSL authored
in this experiment (kernels/*.metal). No Apple binary is disassembled.
"""
import importlib.util, os, subprocess, struct, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
REPO = EXP.parents[1]
sys.path.insert(0, str(REPO / "tools" / "agx-isa"))
sys.path.insert(0, str(REPO / "tools" / "shdump"))
import isadb          # noqa: E402  read-only
import agxparse       # noqa: E402  read-only

def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

PersistRunner = _load("persistrun", REPO / "tools" / "agxtest" / "persistrun.py").PersistRunner


class Carrier:
    """One compiled entry point of our own MSL, ready for in-place splicing."""

    def __init__(self, source, function, bindir, workdir, fast_math=False):
        self.source, self.function = str(source), function
        self.workdir = Path(workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)
        base = self.workdir / ("base_%s.bin" % function)
        cmd = [str(Path(bindir) / "shdump"), "-o", str(base), "-f", function]
        if not fast_math:
            cmd.append("--no-fast-math")
        cmd.append(str(source))
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if r.returncode != 0 or not base.exists():
            raise RuntimeError("shdump %s failed: %s" % (function, r.stderr[:400]))
        self.archive = base.read_bytes()
        loc = agxparse.locate_region(self.archive, "_agc.main")
        if loc is None:
            raise RuntimeError("no _agc.main in %s" % function)
        self.region_off, self.region_len = loc
        _, pieces = agxparse.extract_agx(self.archive)
        self.main = pieces["_agc.main"]
        # EXP-0141 found that REUSING one splice-archive path across persistent-
        # runner requests produces ~8% phantom CMDBUF_ERROR (28/360 shared path vs
        # 0/360 unique paths). Every request therefore gets its own path, with a
        # rolling delete so the sweep does not fill the disk.
        self._spdir = self.workdir / ("sp_%s" % function)
        self._spdir.mkdir(parents=True, exist_ok=True)
        for old in self._spdir.glob("*.bin"):
            old.unlink()
        self._spn = 0
        self._keep = 64

    def tokens(self):
        """[(offset, mnemonic, bytes, fields)] as far as the DB can tokenize."""
        recs, _ = isadb.disassemble(self.main)
        out, off = [], 0
        for rec in recs:
            L = rec.get("length") or isadb.instr_length(self.main, off) or 0
            if not L:
                out.append((off, rec.get("mnemonic", "<unknown>"), self.main[off:], {}))
                break
            out.append((off, rec["mnemonic"], self.main[off:off + L], rec.get("fields", {})))
            off += L
        return out

    def find(self, mnemonic, which=0):
        """(offset_in_main, bytes) of the `which`-th instance of `mnemonic`."""
        hits = [(o, b) for (o, m, b, _f) in self.tokens() if m == mnemonic]
        if len(hits) <= which:
            raise KeyError("%s #%d not found in %s" % (mnemonic, which, self.function))
        return hits[which]

    def splice_path(self, overrides):
        """overrides: {offset_in__agc.main: byte}. Writes a UNIQUE path per call
        (see the note in __init__) and returns it."""
        buf = bytearray(self.archive)
        for off, val in overrides.items():
            if not (0 <= off < self.region_len):
                raise ValueError("offset 0x%x outside _agc.main (len %d)" % (off, self.region_len))
            buf[self.region_off + off] = val & 0xFF
        self._spn += 1
        p = self._spdir / ("%08d.bin" % self._spn)
        p.write_bytes(bytes(buf))
        stale = self._spdir / ("%08d.bin" % (self._spn - self._keep))
        if stale.exists():
            try:
                stale.unlink()
            except OSError:
                pass
        return str(p)


class Bench:
    """A Carrier + a live persistent runner + fixed input/output buffers."""

    SENTINEL0 = 0xA5C3F00D

    def __init__(self, carrier, bindir, in_buf, in_bytes, out_buf, out_nbytes,
                 grid=1, tg=1, timeout=8.0, sent_buf=2, sent_nbytes=16):
        self.c = carrier
        self.in_buf, self.out_buf = in_buf, out_buf
        self.out_nbytes, self.grid, self.tg, self.timeout = out_nbytes, grid, tg, timeout
        self.sent_buf, self.sent_nbytes = sent_buf, sent_nbytes
        self.in_path = carrier.workdir / ("in_%s.bin" % carrier.function)
        self.in_path.write_bytes(in_bytes)
        self._cur_in = in_bytes
        self.hangs = 0
        self.runner = PersistRunner(source=carrier.source, function=carrier.function,
                                    fast_math=False,
                                    agxrun_persist=str(Path(bindir) / "agxrun_persist"))

    def set_input(self, in_bytes):
        if in_bytes != self._cur_in:
            self.in_path.write_bytes(in_bytes)
            self._cur_in = in_bytes

    def run(self, overrides):
        """-> (status, out_bytes, sentinel_bytes, gputime_ns, error)"""
        arch = self.c.splice_path(overrides)
        r = self.runner.request(archive=arch, grid=self.grid, tg=self.tg,
                                ins={self.in_buf: str(self.in_path)},
                                outs={self.out_buf: self.out_nbytes,
                                      self.sent_buf: self.sent_nbytes},
                                timeout=self.timeout)
        if r["status"] == "HANG":
            self.hangs += 1
        return (r["status"], r["outs"].get(self.out_buf, b""),
                r["outs"].get(self.sent_buf, b""), r.get("gputime_ns"), r.get("error"))

    def close(self):
        try:
            self.runner.close()
        except Exception:
            pass
