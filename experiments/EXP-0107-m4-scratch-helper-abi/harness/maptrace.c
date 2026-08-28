/*
 * EXP-0107 DATA-TRACE interposer: our own process's IOKit boundary traffic.
 *
 * Extends EXP-0041's harness/maptrace.c (a validated, non-quarantined P0.1
 * pattern) in one respect: EXP-0041 read the CONTENT of only four
 * pre-established command/state BOs (0x18000/0x58000/0x68000/0x100000b0000)
 * and left every other mapped BO's bytes unread. This experiment's task is
 * explicitly to LOCATE a scratch BO if one exists, so it additionally reads
 * a bounded PREFIX of every BO our own process maps (selector 9), not only
 * the four pre-established roles. This is still squarely DATA-TRACE
 * (CODEX.md): every byte read is our own process's own memory, already
 * registered into the GPU address space by our own resource-map call nothing
 * is disassembled, no Apple binary is opened, and no pointer found INSIDE a
 * mapped BO is ever followed to open another object -- the only BOs read are
 * those this process itself registered via selector 9.
 *
 * The full (class, gpu_va, size, handle) resource-map log is unconditional
 * and free (as in EXP-0041): it is written for every selector-9 call
 * regardless of any allowlist. Content is captured two ways:
 *   - allowlist (env MAPTRACE_DUMP_GPU_VAS): full read (capped 64 KiB) of
 *     named VAs -- reused verbatim from EXP-0041's four established roles.
 *   - all-BO prefix (always on): a bounded prefix (env
 *     MAPTRACE_PREFIX_CAP, default 2048 B) of EVERY remembered BO, written
 *     under <dump_dir>/allbo/. This is the new discovery capability.
 */
#define _DARWIN_C_SOURCE
#import <IOKit/IOKitLib.h>
#import <CoreFoundation/CoreFoundation.h>
#include <mach/mach_vm.h>
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
static uint64_t allow_va[64];
static size_t nallow;
static FILE *trace_log;
static const char *dump_dir;
static size_t prefix_cap = 2048;
static pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;
static struct { mach_port_t port; char name[128]; } conns[64];
static size_t nconn;

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

static int allowed(uint64_t va) {
    for (size_t i = 0; i < nallow; ++i) if (allow_va[i] == va) return 1;
    return 0;
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

static void dump_all(void) {
    char allow_dir[1200], all_dir[1200];
    snprintf(allow_dir, sizeof(allow_dir), "%s", dump_dir);
    snprintf(all_dir, sizeof(all_dir), "%s/allbo", dump_dir);
    mkdir(allow_dir, 0755);
    mkdir(all_dir, 0755);
    for (size_t i = 0; i < nbo; ++i) {
        char path[1400];
        if (allowed(bos[i].gpu_va)) {
            uint64_t cap = bos[i].size < 0x10000 ? bos[i].size : 0x10000;
            snprintf(path, sizeof(path), "%s/bo_va%llx_sz%llx.hex", allow_dir,
                     (unsigned long long)bos[i].gpu_va, (unsigned long long)bos[i].size);
            read_and_write(bos[i].cpu, cap, path, bos[i].gpu_va, bos[i].size, bos[i].cls, "ALLOWLIST");
        }
        uint64_t pcap = bos[i].size < prefix_cap ? bos[i].size : prefix_cap;
        snprintf(path, sizeof(path), "%s/bo_va%llx_sz%llx.hex", all_dir,
                 (unsigned long long)bos[i].gpu_va, (unsigned long long)bos[i].size);
        read_and_write(bos[i].cpu, pcap, path, bos[i].gpu_va, bos[i].size, bos[i].cls, "ALLBO_PREFIX");
    }
    fprintf(trace_log, "# dump_all complete nbo=%zu\n", nbo);
    fflush(trace_log);
}

static void *signal_thread(void *unused) {
    (void)unused;
    sigset_t set; sigemptyset(&set); sigaddset(&set, SIGUSR1);
    for (;;) {
        int sig = 0;
        if (sigwait(&set, &sig)) continue;
        pthread_mutex_lock(&lock); dump_all(); pthread_mutex_unlock(&lock);
    }
    return NULL;
}

__attribute__((constructor)) static void init(void) {
    const char *path = getenv("MAPTRACE_LOG");
    trace_log = path ? fopen(path, "w") : stderr;
    if (!trace_log) trace_log = stderr;
    setvbuf(trace_log, NULL, _IOLBF, 0);
    dump_dir = getenv("MAPTRACE_DUMP_DIR");
    if (!dump_dir) dump_dir = "maptrace_dumps";
    const char *pc = getenv("MAPTRACE_PREFIX_CAP");
    if (pc && *pc) prefix_cap = (size_t)strtoull(pc, NULL, 0);
    const char *s = getenv("MAPTRACE_DUMP_GPU_VAS");
    if (s && *s) {
        char *tmp = strdup(s), *save = NULL;
        for (char *tok = strtok_r(tmp, ",", &save); tok && nallow < 64;
             tok = strtok_r(NULL, ",", &save)) allow_va[nallow++] = strtoull(tok, NULL, 0);
        free(tmp);
    }
    sigset_t set; sigemptyset(&set); sigaddset(&set, SIGUSR1);
    pthread_sigmask(SIG_BLOCK, &set, NULL);
    pthread_t th; pthread_create(&th, NULL, signal_thread, NULL); pthread_detach(th);
    fprintf(trace_log, "# maptrace metadata_always_on=1 allowlisted_full_dump=%zu allbo_prefix_cap=%zu pointer_following=0\n",
            nallow, prefix_cap);
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
    if (kr == KERN_SUCCESS && sel == 5 && out && outc)
        fprintf(trace_log, "SHARED_PAGES class=%s addr0_present=%u addr1_present=%u size=0x%llx\n",
                cname(conn), rd64(out, *outc, 8) != 0, rd64(out, *outc, 16) != 0,
                (unsigned long long)rd64(out, *outc, 24));
    pthread_mutex_unlock(&lock);
    return kr;
}

DYLD_INTERPOSE(wrap_open, IOServiceOpen)
DYLD_INTERPOSE(wrap_method, IOConnectCallMethod)
