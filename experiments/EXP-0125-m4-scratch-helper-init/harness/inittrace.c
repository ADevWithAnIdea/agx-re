/*
 * EXP-0125 DATA-TRACE interposer: our own process's IOKit boundary traffic,
 * CHECKPOINTED across the device/queue/pipeline lifecycle instead of dumped
 * once at the end.
 *
 * Derived from EXP-0107's harness/maptrace.c (itself derived from EXP-0041's),
 * which dumps the full BO inventory exactly ONCE, right before process exit,
 * after the pressure kernel has already run. This experiment's H1 requires
 * comparing the inventory AT MULTIPLE POINTS in a single process's lifetime
 * (device create -> queue create -> trivial-pipeline create -> spill-pipeline
 * create -> pre-dispatch -> post-dispatch), so the one-shot dump is replaced
 * with a repeatable one: every SIGUSR1 the harness sends increments an
 * internal checkpoint counter and writes a FRESH, independent dump under
 * <dump_dir>/cpNN/ (NN = 2-digit zero-padded counter), plus one line to
 * trace_log recording the checkpoint index and a monotonic timestamp so the
 * harness's own separate checkpoints.jsonl (label -> index, written by the
 * ObjC harness itself, append+fflush'd immediately) can be correlated to
 * these dumps purely by ordinal position -- never by wall-clock guessing.
 *
 * Every accounting choice from EXP-0107 is preserved unchanged:
 *   - the (class, gpu_va, size, handle) resource-map log is unconditional,
 *     for every selector-9 call, no allowlist;
 *   - content capture is a bounded PREFIX (env MAPTRACE_PREFIX_CAP) of every
 *     BO the process itself has registered via selector 9 -- this process's
 *     own memory, nothing dereferenced that this process did not itself map;
 *   - no pointer found INSIDE a mapped BO is ever followed to open another
 *     object.
 *
 * New in this experiment (still squarely DATA-TRACE): the selector-5
 * ("shared pages") call handler now ALSO attempts a bounded, best-effort
 * read of the two returned CPU-side pointers (offsets 8 and 16 in the output
 * struct, per EXP-0107's own SHARED_PAGES line) via mach_vm_read_overwrite.
 * docs/kernel-interface.md already documents that the doorbell store itself
 * is "not observable from the userspace interposer" -- this is not expected
 * to expose the store instruction, only whatever queue-context content sits
 * in those firmware-shared pages our own process already maps. A failed
 * read (invalid/unmapped address, wrong offset) fails closed: kr != 0, no
 * bytes captured, logged as absent -- never a crash, never a guess.
 */
#define _DARWIN_C_SOURCE
#import <IOKit/IOKitLib.h>
#import <CoreFoundation/CoreFoundation.h>
#include <mach/mach_vm.h>
#include <mach/mach_time.h>
#include <pthread.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#define DYLD_INTERPOSE(_replacement,_replacee) \
    __attribute__((used)) static struct { const void *replacement; const void *replacee; } \
    _interpose_##_replacee __attribute__((section("__DATA,__interpose"))) = \
    { (const void *)(unsigned long)&_replacement, (const void *)(unsigned long)&_replacee };

typedef struct {
    uint64_t cpu, size, gpu_va;
    uint32_t handle;
    char cls[64];
} BO;

static BO bos[8192];
static size_t nbo;
static FILE *trace_log;
static const char *dump_dir;
static size_t prefix_cap = 2048;
static unsigned checkpoint_idx = 0;
static pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;
static struct { mach_port_t port; char name[128]; } conns[64];
static size_t nconn;
static uint64_t shared_addr0[64], shared_addr1[64], shared_size[64];
static size_t nshared;

static uint64_t rd64(const void *vp, size_t len, size_t off) {
    const unsigned char *p = vp;
    uint64_t v = 0;
    if (!p || off + 8 > len) return 0;
    for (unsigned i = 0; i < 8; ++i) v |= (uint64_t)p[off + i] << (8 * i);
    return v;
}

static const char *cname(mach_port_t p) {
    for (size_t i = 0; i < nconn; ++i) if (conns[i].port == p) return conns[i].name;
    return "unknown";
}

static void remember_bo(uint64_t cpu, uint64_t size, uint64_t va, uint32_t handle, const char *cls) {
    if (!cpu || !size) return;
    for (size_t i = 0; i < nbo; ++i) {
        if (bos[i].cpu == cpu) {
            bos[i].size = size; bos[i].gpu_va = va; bos[i].handle = handle;
            snprintf(bos[i].cls, sizeof(bos[i].cls), "%s", cls);
            return;
        }
    }
    if (nbo < sizeof(bos) / sizeof(bos[0])) {
        BO b = {cpu, size, va, handle, {0}};
        snprintf(b.cls, sizeof(b.cls), "%s", cls);
        bos[nbo++] = b;
    }
}

static void log_resource(mach_port_t conn, const void *in, size_t inlen,
                         const void *out, size_t outlen) {
    uint64_t cpu = rd64(in, inlen, 0x38), size = rd64(in, inlen, 0x48);
    uint64_t va = rd64(out, outlen, 0), outcpu = rd64(out, outlen, 8);
    uint32_t handle = (uint32_t)rd64(out, outlen, 0x20);
    const char *cls = cname(conn);
    fprintf(trace_log, "RESOURCE_MAP class=%s gpu_va=0x%llx size=0x%llx handle=%u cpu_present=%u outcpu_present=%u\n",
            cls, (unsigned long long)va, (unsigned long long)size, handle,
            cpu != 0, outcpu != 0);
    remember_bo(cpu ? cpu : outcpu, size, va, handle, cls);
}

static void hexdump(FILE *f, const unsigned char *buf, uint64_t n) {
    static const char hex[] = "0123456789abcdef";
    for (uint64_t off = 0; off < n; off += 16) {
        fprintf(f, "%08llx: ", (unsigned long long)off);
        uint64_t end = off + 16 < n ? off + 16 : n;
        for (uint64_t j = off; j < end; ++j) {
            fputc(hex[buf[j] >> 4], f); fputc(hex[buf[j] & 15], f);
            if (((j - off) & 3) == 3) fputc(' ', f);
        }
        fputc('\n', f);
    }
}

static void read_and_write(uint64_t cpu, uint64_t cap, const char *path,
                           uint64_t gpu_va, uint64_t size, const char *cls, const char *tag) {
    unsigned char *buf = malloc((size_t)cap);
    mach_vm_size_t got = 0;
    kern_return_t kr = mach_vm_read_overwrite(mach_task_self(), cpu, cap,
                                              (mach_vm_address_t)buf, &got);
    FILE *f = (kr == KERN_SUCCESS && got) ? fopen(path, "w") : NULL;
    if (f) {
        fprintf(f, "# %s gpu_va=0x%llx size=0x%llx class=%s captured=0x%llx\n",
                tag, (unsigned long long)gpu_va, (unsigned long long)size, cls,
                (unsigned long long)got);
        hexdump(f, buf, got);
        fclose(f);
    }
    fprintf(trace_log, "%s_DUMP gpu_va=0x%llx size=0x%llx class=%s kr=0x%x got=0x%llx path=%s\n",
            tag, (unsigned long long)gpu_va, (unsigned long long)size, cls, kr,
            (unsigned long long)got, f ? path : "NONE");
    free(buf);
}

static void dump_shared_pages(const char *cp_dir) {
    char sdir[1300];
    snprintf(sdir, sizeof(sdir), "%s/shared", cp_dir);
    mkdir(sdir, 0755);
    for (size_t i = 0; i < nshared; ++i) {
        char path[1500];
        uint64_t cap = shared_size[i] && shared_size[i] < prefix_cap ? shared_size[i] : prefix_cap;
        if (shared_addr0[i]) {
            snprintf(path, sizeof(path), "%s/shared_%zu_addr0.hex", sdir, i);
            read_and_write(shared_addr0[i], cap, path, 0, shared_size[i], "SHARED", "SHARED_ADDR0");
        }
        if (shared_addr1[i]) {
            snprintf(path, sizeof(path), "%s/shared_%zu_addr1.hex", sdir, i);
            read_and_write(shared_addr1[i], cap, path, 0, shared_size[i], "SHARED", "SHARED_ADDR1");
        }
    }
}

/*
 * CODE-WINDOW CONTENT EXCLUSION -- clean-room boundary, added after this
 * experiment's own run01 dry run found the fix was missing (see
 * PRE_REGISTRATION.md addendum / RESULTS.md "clean-room correction").
 *
 * EXP-0042 established VA 0x10000000000 (4 GiB-aligned) as the ONLY region
 * where our own compiled AGX machine code has ever been observed; EXP-0108
 * (harness/wtrace.c) made a deliberate, PRE_REGISTRATION-frozen decision to
 * exclude that VA range from content capture ENTIRELY, "by construction",
 * specifically because it may contain executable code and every other
 * region has only ever held our own data or small structured descriptors.
 * EXP-0107 never needed this exclusion because its single capture always
 * happened AFTER our own shader had already compiled -- any code-window
 * bytes it captured were therefore always attributable to OUR OWN
 * just-compiled program (OWN-SHADER), never to anything else.
 *
 * THIS experiment's I family captures BEFORE our first compile
 * (DEVICE_CREATED, QUEUE_CREATED), where that attribution does NOT hold: a
 * non-zero code-window BO was observed to exist and have non-zero content
 * at DEVICE_CREATED, before this process has compiled any MSL of its own.
 * Its content therefore cannot be presumed to be our own code and must not
 * be captured or read -- adopting EXP-0108's exact VA-range exclusion here,
 * for ALL checkpoints (not just the pre-compile ones), for uniformity and
 * because a byte-for-byte size match with EXP-0042/EXP-0108's own
 * established convention is what makes "code_window_present"/"size" a safe,
 * content-free structural fact to record at every checkpoint.
 */
#define CODE_WINDOW_VA_LO 0x10000000000ULL
#define CODE_WINDOW_VA_HI 0x10000020000ULL /* EXP-0108's own margin */

static void dump_checkpoint(void) {
    char cp_dir[1200], allow_dir[1250], all_dir[1250];
    snprintf(cp_dir, sizeof(cp_dir), "%s/cp%02u", dump_dir, checkpoint_idx);
    snprintf(allow_dir, sizeof(allow_dir), "%s/named", cp_dir);
    snprintf(all_dir, sizeof(all_dir), "%s/allbo", cp_dir);
    mkdir(dump_dir, 0755);
    mkdir(cp_dir, 0755);
    mkdir(allow_dir, 0755);
    mkdir(all_dir, 0755);
    uint64_t mt = mach_absolute_time();
    fprintf(trace_log, "CHECKPOINT idx=%u mach_time=%llu nbo=%zu nshared=%zu\n",
            checkpoint_idx, (unsigned long long)mt, nbo, nshared);
    for (size_t i = 0; i < nbo; ++i) {
        char path[1500];
        snprintf(path, sizeof(path), "%s/bo_va%llx_sz%llx.hex", all_dir,
                 (unsigned long long)bos[i].gpu_va, (unsigned long long)bos[i].size);
        if (bos[i].gpu_va >= CODE_WINDOW_VA_LO && bos[i].gpu_va < CODE_WINDOW_VA_HI) {
            /* Presence/size only -- write a content-free stub, never read
             * or capture bytes from this region. */
            FILE *f = fopen(path, "w");
            if (f) {
                fprintf(f, "# ALLBO_PREFIX gpu_va=0x%llx size=0x%llx class=%s captured=0x0\n",
                        (unsigned long long)bos[i].gpu_va, (unsigned long long)bos[i].size, bos[i].cls);
                fprintf(f, "# CONTENT EXCLUDED: code-window VA range (EXP-0108 convention) -- "
                        "may contain executable code not attributable to our own compiled "
                        "shader at this checkpoint; never read, never captured.\n");
                fclose(f);
            }
            fprintf(trace_log, "ALLBO_PREFIX_DUMP gpu_va=0x%llx size=0x%llx class=%s kr=0xCODE_WINDOW_EXCLUDED got=0x0 path=%s\n",
                    (unsigned long long)bos[i].gpu_va, (unsigned long long)bos[i].size, bos[i].cls, path);
            continue;
        }
        uint64_t pcap = bos[i].size < prefix_cap ? bos[i].size : prefix_cap;
        read_and_write(bos[i].cpu, pcap, path, bos[i].gpu_va, bos[i].size, bos[i].cls, "ALLBO_PREFIX");
    }
    dump_shared_pages(cp_dir);
    fprintf(trace_log, "# checkpoint %u complete nbo=%zu\n", checkpoint_idx, nbo);
    fflush(trace_log);
    checkpoint_idx++;
}

static void *signal_thread(void *unused) {
    (void)unused;
    sigset_t set; sigemptyset(&set); sigaddset(&set, SIGUSR1);
    for (;;) {
        int sig = 0;
        if (sigwait(&set, &sig)) continue;
        pthread_mutex_lock(&lock); dump_checkpoint(); pthread_mutex_unlock(&lock);
    }
    return NULL;
}

__attribute__((constructor)) static void init(void) {
    const char *path = getenv("MAPTRACE_LOG");
    trace_log = path ? fopen(path, "w") : stderr;
    if (!trace_log) trace_log = stderr;
    setvbuf(trace_log, NULL, _IOLBF, 0);
    dump_dir = getenv("MAPTRACE_DUMP_DIR");
    if (!dump_dir) dump_dir = "inittrace_dumps";
    const char *pc = getenv("MAPTRACE_PREFIX_CAP");
    if (pc && *pc) prefix_cap = (size_t)strtoull(pc, NULL, 0);
    sigset_t set; sigemptyset(&set); sigaddset(&set, SIGUSR1);
    pthread_sigmask(SIG_BLOCK, &set, NULL);
    pthread_t th; pthread_create(&th, NULL, signal_thread, NULL); pthread_detach(th);
    fprintf(trace_log, "# inittrace metadata_always_on=1 allbo_prefix_cap=%zu pointer_following=0 "
            "checkpointed=1 shared_page_bestEffort=1\n", prefix_cap);
}

extern kern_return_t IOServiceOpen(io_service_t, task_port_t, uint32_t, io_connect_t *);
extern kern_return_t IOConnectCallMethod(mach_port_t, uint32_t, const uint64_t *, uint32_t,
                                         const void *, size_t, uint64_t *, uint32_t *, void *, size_t *);

static kern_return_t wrap_open(io_service_t service, task_port_t task, uint32_t type, io_connect_t *out) {
    kern_return_t kr = IOServiceOpen(service, task, type, out);
    pthread_mutex_lock(&lock);
    if (kr == KERN_SUCCESS && out && nconn < 64) {
        io_name_t name = {0}; IORegistryEntryGetName(service, name);
        conns[nconn].port = *out; snprintf(conns[nconn].name, sizeof(conns[nconn].name), "%s", name); ++nconn;
        fprintf(trace_log, "SERVICE_OPEN class=%s type=%u conn=0x%x\n", name, type, *out);
    }
    pthread_mutex_unlock(&lock);
    return kr;
}

static kern_return_t wrap_method(mach_port_t conn, uint32_t sel, const uint64_t *si, uint32_t sic,
                                 const void *st, size_t stc, uint64_t *so, uint32_t *soc,
                                 void *out, size_t *outc) {
    kern_return_t kr = IOConnectCallMethod(conn, sel, si, sic, st, stc, so, soc, out, outc);
    pthread_mutex_lock(&lock);
    fprintf(trace_log, "CALL class=%s sel=%u ret=0x%x in_struct=0x%zx out_struct=0x%zx\n",
            cname(conn), sel, kr, stc, outc ? *outc : 0);
    if (kr == KERN_SUCCESS && sel == 9 && st && out && outc) log_resource(conn, st, stc, out, *outc);
    if (kr == KERN_SUCCESS && sel == 5 && out && outc) {
        uint64_t a0 = rd64(out, *outc, 8), a1 = rd64(out, *outc, 16), sz = rd64(out, *outc, 24);
        fprintf(trace_log, "SHARED_PAGES class=%s addr0_present=%u addr1_present=%u size=0x%llx\n",
                cname(conn), a0 != 0, a1 != 0, (unsigned long long)sz);
        if (nshared < 64) {
            shared_addr0[nshared] = a0; shared_addr1[nshared] = a1; shared_size[nshared] = sz; nshared++;
        }
    }
    pthread_mutex_unlock(&lock);
    return kr;
}

DYLD_INTERPOSE(wrap_open, IOServiceOpen)
DYLD_INTERPOSE(wrap_method, IOConnectCallMethod)
