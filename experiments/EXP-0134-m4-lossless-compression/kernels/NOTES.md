MSL kernel/shader sources for this experiment are generated inline (per-case, with
runtime parameters such as clear color / outlier position / format-appropriate return
type baked into the string) in `harness/cprobe.m`'s `fsrc()`/`vsrc()` and the read-kernel
builder — matching the established precedent in EXP-0017 (`texprobe.m`) and EXP-M4-07
(`typrobe2.m`, `wbtest.m`, `mssync.m`), all of which build MSL source strings in ObjC
rather than committing static `.metal` files, since these probes are parametric per case
rather than fixed. See `harness/cprobe.m`'s header comment and `README.md`'s Method
section for the full account of what MSL is authored and how it is compiled
(`newLibraryWithSource:`, runtime, no `metal` CLI).
