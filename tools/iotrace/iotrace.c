/*
 * iotrace.c — clean-room DATA-TRACE interposer for the IOKit user-client surface.
 *
 * Part of the A18 Pro GPU clean-room RE project (EXP-0009, ROADMAP 0.5).
 *
 * A DYLD_INSERT_LIBRARIES library that interposes (dyld DYLD_INTERPOSE) the IOKit
 * user<->kernel entry points our OWN Metal program uses to talk to the GPU kernel
 * driver, and logs the DATA that crosses the boundary:
 *   - IOServiceOpen            : which user-client class each connection belongs to
 *   - IOConnectCallMethod      : selector, scalar in/out, struct in/out (full hex)
 *   - IOConnectCallScalarMethod: scalar-only calls
 *   - IOConnectCallStructMethod: struct-only calls
 *   - IOConnectCallAsyncMethod : async submit/kick calls + reference args
 *   - IOConnectMapMemory64     : shared-memory regions mapped into our address space
 *
 * On demand it snapshots the *contents* of the mapped shared-memory regions
 * (the command-buffer / control-stream rings) so we can locate where our own
 * shader+buffers get encoded.  Reads are done with mach_vm_read_overwrite so a
 * torn-down region can never crash the traced process.
 *
 * CLEAN-ROOM: this logs DATA ONLY (call selectors, struct payload bytes, mapped
 * memory contents crossing the userspace<->kernel boundary).  Command buffers,
 * descriptors and register values are non-copyrightable per the Asahi clean-room
 * policy.  It NEVER disassembles, decompiles or introspects the CODE of Metal,
 * AGX* or IOGPU.  The interposer technique and the DYLD_INTERPOSE macro are the
 * public ones from Apple dyld / the MIT/APSL Asahi `wrap.c`; this is our own
 * independent implementation written from the interface, not copied.
 *
 * Build (on the A18 device, Command Line Tools only):
 *   clang -dynamiclib -o iotrace.dylib iotrace.c -framework IOKit -framework CoreFoundation
 *
 * Use:
 *   IOTRACE_LOG=trace.log DYLD_INSERT_LIBRARIES=./iotrace.dylib ./iohello_compute
 *
 * Environment:
 *   IOTRACE_LOG        log file path                 (default: stderr)
 *   IOTRACE_DUMP_DIR   dir for map snapshots         (default: ./iotrace_maps)
 *   IOTRACE_DUMP_ON_SEL  comma list of selectors: dump ALL maps before+after any
 *                        IOConnectCall* with a matching selector (the submit/kick)
 *   IOTRACE_DUMP_ATEXIT  =1 : dump all maps once at process exit (fallback)
 *   IOTRACE_MAX_STRUCT   cap struct-payload hex bytes (default 65536)
 *   IOTRACE_MAX_MAP      cap per-region snapshot bytes(default 1048576)
 *   IOTRACE_ONLY_CONN    hex connection id : only log this connection (optional)
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <unistd.h>
#include <pthread.h>
#include <signal.h>
#include <sys/stat.h>

#include <mach/mach.h>
#include <mach/mach_vm.h>
#include <IOKit/IOKitLib.h>

/* ---- dyld interpose macro (public, from Apple dyld sources) --------------- */
#define DYLD_INTERPOSE(_replacement, _replacee) \
    __attribute__((used)) static struct { const void *replacement; const void *replacee; } \
    _interpose_##_replacee __attribute__((section("__DATA,__interpose"))) = \
    { (const void *)(unsigned long)&_replacement, (const void *)(unsigned long)&_replacee };

/* ---- global state --------------------------------------------------------- */
static FILE          *g_log      = NULL;
static pthread_mutex_t g_lock    = PTHREAD_MUTEX_INITIALIZER;
static const char    *g_dump_dir = NULL;
static unsigned long   g_max_struct = 65536;
static unsigned long   g_max_map    = 1048576;
static uint64_t        g_only_conn  = 0;     /* 0 = log all connections     */
static int             g_dump_atexit = 0;
static uint64_t        g_call_seq   = 0;     /* monotonically increasing    */

/* selectors that trigger a full map snapshot (from IOTRACE_DUMP_ON_SEL) */
#define MAX_DUMP_SEL 32
static uint32_t g_dump_sel[MAX_DUMP_SEL];
static int      g_n_dump_sel = 0;

/* connection -> user-client class name, captured at IOServiceOpen */
#define MAX_CONN 256
static struct { uint64_t conn; char cls[128]; } g_conn[MAX_CONN];
static int g_n_conn = 0;

/* registry of mapped shared-memory regions (the candidate rings/cmdbufs) */
#define MAX_MAP 512
static struct { uint64_t conn; uint32_t memType; uint64_t addr; uint64_t size; } g_map[MAX_MAP];
static int g_n_map = 0;

/* registry of GPU buffer objects (BOs) discovered from the resource-map call
 * (selector 9 on AGXAcceleratorG17P): userspace memory registered into the GPU
 * VM.  Metal encodes the control/command stream into some of these BOs, so
 * dumping their CPU-side contents after a submit captures the command stream. */
#define MAX_BO 4096
static struct { uint64_t cpu; uint64_t size; uint64_t gpu_va; uint32_t handle; } g_bo[MAX_BO];
static int g_n_bo = 0;
static uint32_t g_bo_sel = 9;         /* AGX resource-map selector (overridable) */
static int      g_dump_on_usr1 = 1;   /* dump all BOs on SIGUSR1 (from harness)  */

/* plausible userspace BO CPU-address window on this platform (heuristic gate) */
static int looks_cpu(uint64_t v) { return v >= 0x100000000ULL && v < 0x400000000ULL; }

/* ---- helpers -------------------------------------------------------------- */
static const char *conn_class(uint64_t conn)
{
    for (int i = 0; i < g_n_conn; i++)
        if (g_conn[i].conn == conn) return g_conn[i].cls;
    return "?";
}

static void hexdump_line(const uint8_t *p, size_t n)
{
    /* one long hex string; caller already holds the lock */
    static const char H[] = "0123456789abcdef";
    for (size_t i = 0; i < n; i++) {
        fputc(H[p[i] >> 4],  g_log);
        fputc(H[p[i] & 0xf], g_log);
    }
}

/* structured hex block: 16 bytes/line with byte offset, easy to read+grep */
static void hexdump_block(const char *tag, const uint8_t *p, size_t n)
{
    for (size_t off = 0; off < n; off += 16) {
        fprintf(g_log, "%s %06zx: ", tag, off);
        size_t line = (n - off < 16) ? (n - off) : 16;
        for (size_t i = 0; i < 16; i++) {
            if (i < line) fprintf(g_log, "%02x", p[off + i]);
            else          fprintf(g_log, "  ");
            if ((i & 1) == 1) fputc(' ', g_log);
        }
        fputc('\n', g_log);
    }
}

/* crash-safe read of a foreign/mapped region into a heap buffer */
static uint8_t *safe_read(uint64_t addr, uint64_t size, uint64_t *got)
{
    uint8_t *buf = malloc(size);
    if (!buf) { *got = 0; return NULL; }
    mach_vm_size_t out = 0;
    kern_return_t kr = mach_vm_read_overwrite(mach_task_self(),
                                              (mach_vm_address_t)addr,
                                              (mach_vm_size_t)size,
                                              (mach_vm_address_t)buf,
                                              &out);
    if (kr != KERN_SUCCESS) { free(buf); *got = 0; return NULL; }
    *got = out;
    return buf;
}

/* snapshot every registered mapped region to a text (.hex) file + note it */
static void dump_all_maps(const char *reason)
{
    if (!g_dump_dir) return;
    for (int i = 0; i < g_n_map; i++) {
        uint64_t addr = g_map[i].addr, size = g_map[i].size;
        if (size == 0) continue;
        uint64_t cap = size < g_max_map ? size : g_max_map;
        uint64_t got = 0;
        uint8_t *buf = safe_read(addr, cap, &got);
        char path[512];
        snprintf(path, sizeof(path), "%s/map_seq%06llu_conn%llx_type%08x_at%llx_sz%llx.hex",
                 g_dump_dir, (unsigned long long)g_call_seq,
                 (unsigned long long)g_map[i].conn, g_map[i].memType,
                 (unsigned long long)addr, (unsigned long long)size);
        FILE *f = fopen(path, "w");
        if (f) {
            fprintf(f, "# MAPDUMP reason=%s seq=%llu conn=%llx class=%s memType=0x%08x addr=0x%llx size=0x%llx read=0x%llx\n",
                    reason, (unsigned long long)g_call_seq,
                    (unsigned long long)g_map[i].conn, conn_class(g_map[i].conn),
                    g_map[i].memType, (unsigned long long)addr,
                    (unsigned long long)size, (unsigned long long)got);
            if (buf && got) {
                static const char H[] = "0123456789abcdef";
                for (uint64_t off = 0; off < got; off += 16) {
                    fprintf(f, "%08llx: ", (unsigned long long)off);
                    uint64_t line = (got - off < 16) ? (got - off) : 16;
                    for (uint64_t j = 0; j < line; j++) {
                        uint8_t b = buf[off + j];
                        fputc(H[b >> 4], f); fputc(H[b & 0xf], f);
                        if ((j & 3) == 3) fputc(' ', f);
                    }
                    fputc('\n', f);
                }
            }
            fclose(f);
        }
        fprintf(g_log, "MAPDUMP reason=%s seq=%llu conn=%llx memType=0x%08x addr=0x%llx size=0x%llx read=0x%llx -> %s\n",
                reason, (unsigned long long)g_call_seq,
                (unsigned long long)g_map[i].conn, g_map[i].memType,
                (unsigned long long)addr, (unsigned long long)size,
                (unsigned long long)got, path);
        if (buf) free(buf);
    }
    fflush(g_log);
}

static int sel_wants_dump(uint32_t sel)
{
    for (int i = 0; i < g_n_dump_sel; i++)
        if (g_dump_sel[i] == sel) return 1;
    return 0;
}

static uint64_t rd64(const uint8_t *p, size_t len, size_t off)
{
    if (off + 8 > len) return 0;
    uint64_t v = 0;
    for (int i = 0; i < 8; i++) v |= (uint64_t)p[off + i] << (8 * i);
    return v;
}

static void bo_add(uint64_t cpu, uint64_t size, uint64_t gpu_va, uint32_t handle)
{
    if (!looks_cpu(cpu) || size == 0) return;
    for (int i = 0; i < g_n_bo; i++)                 /* dedup by cpu base */
        if (g_bo[i].cpu == cpu) {
            if (size  > g_bo[i].size)   g_bo[i].size   = size;
            if (gpu_va)                 g_bo[i].gpu_va = gpu_va;
            return;
        }
    if (g_n_bo >= MAX_BO) return;
    g_bo[g_n_bo].cpu = cpu; g_bo[g_n_bo].size = size;
    g_bo[g_n_bo].gpu_va = gpu_va; g_bo[g_n_bo].handle = handle;
    g_n_bo++;
}

/* Parse the AGX resource-map call (selector 9).  Empirically (EXP-0009):
 *   IN  @0x38 = CPU base of a userspace-allocated BO (0 for kernel-allocated)
 *   IN  @0x48 = size
 *   OUT @0x00 = GPU virtual address of the (heap) region
 *   OUT @0x08 = CPU base when the kernel allocated it
 * We record any plausible CPU pointer + size so the BO's bytes can be dumped
 * later; we do NOT interpret the struct semantics here (that is Phase 2). */
static void parse_resource_map(const uint8_t *in, size_t inLen,
                               const uint8_t *out, size_t outLen)
{
    uint64_t in_cpu  = rd64(in,  inLen,  0x38);
    uint64_t in_size = rd64(in,  inLen,  0x48);
    uint64_t gpu_va  = rd64(out, outLen, 0x00);
    uint64_t out_cpu = rd64(out, outLen, 0x08);
    uint32_t handle  = (uint32_t)rd64(out, outLen, 0x20);
    if (in_cpu)  bo_add(in_cpu,  in_size ? in_size : 0x1000, gpu_va, handle);
    if (out_cpu) bo_add(out_cpu, in_size ? in_size : 0x1000, gpu_va, handle);
}

/* Snapshot every tracked BO's CPU-side bytes to a .hex text file (crash-safe). */
static void dump_all_bos(const char *reason)
{
    if (!g_dump_dir) return;
    fprintf(g_log, "BODUMP begin reason=%s n_bo=%d\n", reason, g_n_bo);
    for (int i = 0; i < g_n_bo; i++) {
        uint64_t cpu = g_bo[i].cpu, size = g_bo[i].size;
        uint64_t cap = size < g_max_map ? size : g_max_map;
        if (cap == 0) continue;
        uint64_t got = 0;
        uint8_t *buf = safe_read(cpu, cap, &got);
        if (!buf || got == 0) { if (buf) free(buf); continue; }
        char path[512];
        snprintf(path, sizeof(path),
                 "%s/bo_%s_h%u_va%llx_cpu%llx_sz%llx.hex", g_dump_dir, reason,
                 g_bo[i].handle, (unsigned long long)g_bo[i].gpu_va,
                 (unsigned long long)cpu, (unsigned long long)size);
        FILE *f = fopen(path, "w");
        if (f) {
            fprintf(f, "# BODUMP reason=%s handle=%u gpu_va=0x%llx cpu=0x%llx size=0x%llx read=0x%llx\n",
                    reason, g_bo[i].handle, (unsigned long long)g_bo[i].gpu_va,
                    (unsigned long long)cpu, (unsigned long long)size,
                    (unsigned long long)got);
            static const char H[] = "0123456789abcdef";
            for (uint64_t off = 0; off < got; off += 16) {
                fprintf(f, "%08llx: ", (unsigned long long)off);
                uint64_t line = (got - off < 16) ? (got - off) : 16;
                for (uint64_t j = 0; j < line; j++) {
                    uint8_t b = buf[off + j];
                    fputc(H[b >> 4], f); fputc(H[b & 0xf], f);
                    if ((j & 3) == 3) fputc(' ', f);
                }
                fputc('\n', f);
            }
            fclose(f);
            fprintf(g_log, "BODUMP handle=%u gpu_va=0x%llx cpu=0x%llx size=0x%llx read=0x%llx -> %s\n",
                    g_bo[i].handle, (unsigned long long)g_bo[i].gpu_va,
                    (unsigned long long)cpu, (unsigned long long)size,
                    (unsigned long long)got, path);
        }
        free(buf);
    }
    fprintf(g_log, "BODUMP end reason=%s\n", reason);
    fflush(g_log);
}

/* Dedicated thread: blocks on SIGUSR1 (raised by the harness after
 * waitUntilCompleted, while all BOs are still mapped) and dumps the BOs in
 * normal thread context — so the dump can safely take the log lock / use
 * stdio, unlike a signal handler would. */
static void *usr1_thread(void *arg)
{
    (void)arg;
    sigset_t set; sigemptyset(&set); sigaddset(&set, SIGUSR1);
    for (;;) {
        int sig = 0;
        if (sigwait(&set, &sig) != 0) continue;
        pthread_mutex_lock(&g_lock);
        dump_all_bos("sigusr1");
        dump_all_maps("sigusr1");
        pthread_mutex_unlock(&g_lock);
    }
    return NULL;
}

static int conn_filtered_out(uint64_t conn)
{
    return (g_only_conn != 0 && conn != g_only_conn);
}

/* ---- init / teardown ------------------------------------------------------ */
__attribute__((constructor))
static void iotrace_init(void)
{
    const char *lp = getenv("IOTRACE_LOG");
    if (lp && *lp) {
        g_log = fopen(lp, "w");
    }
    if (!g_log) g_log = stderr;
    setvbuf(g_log, NULL, _IOLBF, 0);

    g_dump_dir = getenv("IOTRACE_DUMP_DIR");
    if (!g_dump_dir || !*g_dump_dir) g_dump_dir = "iotrace_maps";
    mkdir(g_dump_dir, 0755);

    const char *ms = getenv("IOTRACE_MAX_STRUCT"); if (ms) g_max_struct = strtoul(ms, NULL, 0);
    const char *mm = getenv("IOTRACE_MAX_MAP");    if (mm) g_max_map    = strtoul(mm, NULL, 0);
    const char *oc = getenv("IOTRACE_ONLY_CONN");  if (oc) g_only_conn  = strtoull(oc, NULL, 0);
    const char *ax = getenv("IOTRACE_DUMP_ATEXIT");if (ax) g_dump_atexit = atoi(ax);
    const char *bs = getenv("IOTRACE_BO_SEL");     if (bs) g_bo_sel     = (uint32_t)strtoul(bs, NULL, 0);
    const char *u1 = getenv("IOTRACE_DUMP_ON_USR1");if (u1) g_dump_on_usr1 = atoi(u1);

    /* Block SIGUSR1 in every thread and let a dedicated thread wait for it, so
     * the harness can trigger a BO snapshot at a precise moment (post-submit).
     * Our constructor runs before main and before Metal spawns its threads, so
     * they all inherit the blocked mask. */
    if (g_dump_on_usr1) {
        sigset_t set; sigemptyset(&set); sigaddset(&set, SIGUSR1);
        pthread_sigmask(SIG_BLOCK, &set, NULL);
        pthread_t th;
        pthread_create(&th, NULL, usr1_thread, NULL);
        pthread_detach(th);
    }

    const char *ds = getenv("IOTRACE_DUMP_ON_SEL");
    if (ds && *ds) {
        char *tmp = strdup(ds), *tok, *save = NULL;
        for (tok = strtok_r(tmp, ",", &save); tok && g_n_dump_sel < MAX_DUMP_SEL;
             tok = strtok_r(NULL, ",", &save))
            g_dump_sel[g_n_dump_sel++] = (uint32_t)strtoul(tok, NULL, 0);
        free(tmp);
    }

    fprintf(g_log, "# iotrace init pid=%d dump_dir=%s max_struct=%lu max_map=%lu "
                   "dump_atexit=%d n_dump_sel=%d only_conn=0x%llx\n",
            getpid(), g_dump_dir, g_max_struct, g_max_map, g_dump_atexit,
            g_n_dump_sel, (unsigned long long)g_only_conn);
    fflush(g_log);
}

__attribute__((destructor))
static void iotrace_fini(void)
{
    if (g_dump_atexit) {
        pthread_mutex_lock(&g_lock);
        g_call_seq = 999999;   /* distinguish exit snapshot */
        dump_all_maps("atexit");
        pthread_mutex_unlock(&g_lock);
    }
    if (g_log && g_log != stderr) fclose(g_log);
}

/* ---- the real functions (interpose calls the original by name) ------------ */
extern kern_return_t IOServiceOpen(io_service_t, task_port_t, uint32_t, io_connect_t *);
extern kern_return_t IOConnectCallMethod(mach_port_t, uint32_t, const uint64_t *, uint32_t,
                                         const void *, size_t, uint64_t *, uint32_t *,
                                         void *, size_t *);
extern kern_return_t IOConnectCallScalarMethod(mach_port_t, uint32_t, const uint64_t *, uint32_t,
                                               uint64_t *, uint32_t *);
extern kern_return_t IOConnectCallStructMethod(mach_port_t, uint32_t, const void *, size_t,
                                               void *, size_t *);
extern kern_return_t IOConnectCallAsyncMethod(mach_port_t, uint32_t, mach_port_t, uint64_t *,
                                              uint32_t, const uint64_t *, uint32_t, const void *,
                                              size_t, uint64_t *, uint32_t *, void *, size_t *);
extern kern_return_t IOConnectMapMemory64(io_connect_t, uint32_t, task_port_t,
                                          mach_vm_address_t *, mach_vm_size_t *, IOOptionBits);

/* ---- shared call logger --------------------------------------------------- */
static void log_call_common(const char *fn, mach_port_t conn, uint32_t sel,
                            const uint64_t *input, uint32_t inputCnt,
                            const void *inStruct, size_t inStructCnt)
{
    uint64_t seq = ++g_call_seq;
    fprintf(g_log, "CALL seq=%llu fn=%s conn=%llx class=%s sel=%u(0x%x) inScalarCnt=%u inStructCnt=%zu",
            (unsigned long long)seq, fn, (unsigned long long)conn, conn_class(conn),
            sel, sel, inputCnt, inStructCnt);
    if (input && inputCnt) {
        fprintf(g_log, " inScalars=[");
        for (uint32_t i = 0; i < inputCnt; i++)
            fprintf(g_log, "%s0x%llx", i ? "," : "", (unsigned long long)input[i]);
        fputc(']', g_log);
    }
    fputc('\n', g_log);
    if (inStruct && inStructCnt) {
        size_t n = inStructCnt < g_max_struct ? inStructCnt : g_max_struct;
        fprintf(g_log, "  IN.struct len=%zu%s\n", inStructCnt,
                n < inStructCnt ? " (truncated)" : "");
        hexdump_block("  IN", (const uint8_t *)inStruct, n);
    }
}

static void log_call_ret(mach_port_t conn, uint32_t sel, kern_return_t ret,
                         uint64_t *output, uint32_t *outputCnt,
                         void *outStruct, size_t *outStructCntP)
{
    fprintf(g_log, "RET  seq=%llu conn=%llx sel=%u(0x%x) ret=0x%x",
            (unsigned long long)g_call_seq, (unsigned long long)conn, sel, sel, ret);
    if (output && outputCnt && *outputCnt) {
        fprintf(g_log, " outScalars=[");
        for (uint32_t i = 0; i < *outputCnt; i++)
            fprintf(g_log, "%s0x%llx", i ? "," : "", (unsigned long long)output[i]);
        fputc(']', g_log);
    }
    if (outStructCntP) fprintf(g_log, " outStructCnt=%zu", *outStructCntP);
    fputc('\n', g_log);
    if (outStruct && outStructCntP && *outStructCntP) {
        size_t n = *outStructCntP < g_max_struct ? *outStructCntP : g_max_struct;
        fprintf(g_log, "  OUT.struct len=%zu%s\n", *outStructCntP,
                n < *outStructCntP ? " (truncated)" : "");
        hexdump_block("  OUT", (const uint8_t *)outStruct, n);
    }
    fflush(g_log);
}

/* ---- wrappers ------------------------------------------------------------- */
kern_return_t wrap_IOServiceOpen(io_service_t service, task_port_t owningTask,
                                 uint32_t type, io_connect_t *connect)
{
    io_name_t cls; cls[0] = 0;
    IOObjectGetClass(service, cls);
    kern_return_t ret = IOServiceOpen(service, owningTask, type, connect);
    pthread_mutex_lock(&g_lock);
    if (ret == KERN_SUCCESS && connect && g_n_conn < MAX_CONN) {
        g_conn[g_n_conn].conn = *connect;
        strncpy(g_conn[g_n_conn].cls, cls, sizeof(g_conn[g_n_conn].cls) - 1);
        g_conn[g_n_conn].cls[sizeof(g_conn[g_n_conn].cls) - 1] = 0;
        g_n_conn++;
    }
    fprintf(g_log, "OPEN class=%s type=%u -> conn=%llx ret=0x%x\n",
            cls, type, connect ? (unsigned long long)*connect : 0ULL, ret);
    fflush(g_log);
    pthread_mutex_unlock(&g_lock);
    return ret;
}

kern_return_t wrap_IOConnectCallMethod(mach_port_t connection, uint32_t selector,
                                       const uint64_t *input, uint32_t inputCnt,
                                       const void *inputStruct, size_t inputStructCnt,
                                       uint64_t *output, uint32_t *outputCnt,
                                       void *outputStruct, size_t *outputStructCntP)
{
    if (conn_filtered_out(connection))
        return IOConnectCallMethod(connection, selector, input, inputCnt, inputStruct,
                                   inputStructCnt, output, outputCnt, outputStruct, outputStructCntP);
    pthread_mutex_lock(&g_lock);
    log_call_common("Method", connection, selector, input, inputCnt, inputStruct, inputStructCnt);
    int wantDump = sel_wants_dump(selector);
    if (wantDump) dump_all_maps("pre-submit");
    pthread_mutex_unlock(&g_lock);

    kern_return_t ret = IOConnectCallMethod(connection, selector, input, inputCnt, inputStruct,
                                            inputStructCnt, output, outputCnt, outputStruct, outputStructCntP);

    pthread_mutex_lock(&g_lock);
    log_call_ret(connection, selector, ret, output, outputCnt, outputStruct, outputStructCntP);
    if (ret == KERN_SUCCESS && selector == g_bo_sel && inputStruct && outputStruct && outputStructCntP)
        parse_resource_map((const uint8_t *)inputStruct, inputStructCnt,
                           (const uint8_t *)outputStruct, *outputStructCntP);
    if (wantDump) dump_all_maps("post-submit");
    pthread_mutex_unlock(&g_lock);
    return ret;
}

kern_return_t wrap_IOConnectCallScalarMethod(mach_port_t connection, uint32_t selector,
                                             const uint64_t *input, uint32_t inputCnt,
                                             uint64_t *output, uint32_t *outputCnt)
{
    if (conn_filtered_out(connection))
        return IOConnectCallScalarMethod(connection, selector, input, inputCnt, output, outputCnt);
    pthread_mutex_lock(&g_lock);
    log_call_common("Scalar", connection, selector, input, inputCnt, NULL, 0);
    int wantDump = sel_wants_dump(selector);
    if (wantDump) dump_all_maps("pre-submit");
    pthread_mutex_unlock(&g_lock);

    kern_return_t ret = IOConnectCallScalarMethod(connection, selector, input, inputCnt, output, outputCnt);

    pthread_mutex_lock(&g_lock);
    log_call_ret(connection, selector, ret, output, outputCnt, NULL, NULL);
    if (wantDump) dump_all_maps("post-submit");
    pthread_mutex_unlock(&g_lock);
    return ret;
}

kern_return_t wrap_IOConnectCallStructMethod(mach_port_t connection, uint32_t selector,
                                             const void *inputStruct, size_t inputStructCnt,
                                             void *outputStruct, size_t *outputStructCntP)
{
    if (conn_filtered_out(connection))
        return IOConnectCallStructMethod(connection, selector, inputStruct, inputStructCnt,
                                         outputStruct, outputStructCntP);
    pthread_mutex_lock(&g_lock);
    log_call_common("Struct", connection, selector, NULL, 0, inputStruct, inputStructCnt);
    int wantDump = sel_wants_dump(selector);
    if (wantDump) dump_all_maps("pre-submit");
    pthread_mutex_unlock(&g_lock);

    kern_return_t ret = IOConnectCallStructMethod(connection, selector, inputStruct, inputStructCnt,
                                                  outputStruct, outputStructCntP);

    pthread_mutex_lock(&g_lock);
    log_call_ret(connection, selector, ret, NULL, NULL, outputStruct, outputStructCntP);
    if (wantDump) dump_all_maps("post-submit");
    pthread_mutex_unlock(&g_lock);
    return ret;
}

kern_return_t wrap_IOConnectCallAsyncMethod(mach_port_t connection, uint32_t selector,
                                            mach_port_t wakePort, uint64_t *reference,
                                            uint32_t referenceCnt, const uint64_t *input,
                                            uint32_t inputCnt, const void *inputStruct,
                                            size_t inputStructCnt, uint64_t *output,
                                            uint32_t *outputCnt, void *outputStruct,
                                            size_t *outputStructCntP)
{
    if (conn_filtered_out(connection))
        return IOConnectCallAsyncMethod(connection, selector, wakePort, reference, referenceCnt,
                                        input, inputCnt, inputStruct, inputStructCnt, output,
                                        outputCnt, outputStruct, outputStructCntP);
    pthread_mutex_lock(&g_lock);
    log_call_common("Async", connection, selector, input, inputCnt, inputStruct, inputStructCnt);
    fprintf(g_log, "  ASYNC wakePort=%x refCnt=%u refs=[", wakePort, referenceCnt);
    for (uint32_t i = 0; i < referenceCnt && reference; i++)
        fprintf(g_log, "%s0x%llx", i ? "," : "", (unsigned long long)reference[i]);
    fprintf(g_log, "]\n");
    int wantDump = sel_wants_dump(selector);
    if (wantDump) dump_all_maps("pre-submit");
    pthread_mutex_unlock(&g_lock);

    kern_return_t ret = IOConnectCallAsyncMethod(connection, selector, wakePort, reference, referenceCnt,
                                                 input, inputCnt, inputStruct, inputStructCnt, output,
                                                 outputCnt, outputStruct, outputStructCntP);

    pthread_mutex_lock(&g_lock);
    log_call_ret(connection, selector, ret, output, outputCnt, outputStruct, outputStructCntP);
    if (wantDump) dump_all_maps("post-submit");
    pthread_mutex_unlock(&g_lock);
    return ret;
}

kern_return_t wrap_IOConnectMapMemory64(io_connect_t connect, uint32_t memoryType,
                                        task_port_t intoTask, mach_vm_address_t *atAddress,
                                        mach_vm_size_t *ofSize, IOOptionBits options)
{
    kern_return_t ret = IOConnectMapMemory64(connect, memoryType, intoTask, atAddress, ofSize, options);
    pthread_mutex_lock(&g_lock);
    uint64_t addr = (atAddress ? (uint64_t)*atAddress : 0);
    uint64_t size = (ofSize ? (uint64_t)*ofSize : 0);
    if (ret == KERN_SUCCESS && g_n_map < MAX_MAP) {
        g_map[g_n_map].conn = connect;
        g_map[g_n_map].memType = memoryType;
        g_map[g_n_map].addr = addr;
        g_map[g_n_map].size = size;
        g_n_map++;
    }
    fprintf(g_log, "MAP  conn=%llx class=%s memType=0x%08x opts=0x%x -> addr=0x%llx size=0x%llx ret=0x%x\n",
            (unsigned long long)connect, conn_class(connect), memoryType, options,
            (unsigned long long)addr, (unsigned long long)size, ret);
    fflush(g_log);
    pthread_mutex_unlock(&g_lock);
    return ret;
}

/* ---- interpose table ------------------------------------------------------ */
DYLD_INTERPOSE(wrap_IOServiceOpen,             IOServiceOpen)
DYLD_INTERPOSE(wrap_IOConnectCallMethod,       IOConnectCallMethod)
DYLD_INTERPOSE(wrap_IOConnectCallScalarMethod, IOConnectCallScalarMethod)
DYLD_INTERPOSE(wrap_IOConnectCallStructMethod, IOConnectCallStructMethod)
DYLD_INTERPOSE(wrap_IOConnectCallAsyncMethod,  IOConnectCallAsyncMethod)
DYLD_INTERPOSE(wrap_IOConnectMapMemory64,      IOConnectMapMemory64)
