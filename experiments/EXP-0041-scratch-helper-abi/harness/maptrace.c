/*
 * EXP-0041 metadata-only clean-room DATA-TRACE interposer.
 *
 * This records only public IOKit call metadata and the resource-map boundary
 * fields established by earlier clean experiments. It does not read any mapped
 * BO by default. An explicit GPU-VA allowlist can dump only command/state BOs
 * whose roles were independently established before this experiment.
 * It never follows a pointer and never reads a pointed-to program BO.
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
} BO;

static BO bos[4096];
static size_t nbo;
static uint64_t allow_va[64];
static size_t nallow;
static FILE *trace_log;
static const char *dump_dir;
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

static void remember_bo(uint64_t cpu, uint64_t size, uint64_t va, uint32_t handle) {
    if (!cpu || !size) return;
    for (size_t i = 0; i < nbo; ++i) {
        if (bos[i].cpu == cpu) { bos[i].size = size; bos[i].gpu_va = va; bos[i].handle = handle; return; }
    }
    if (nbo < sizeof(bos) / sizeof(bos[0])) bos[nbo++] = (BO){cpu, size, va, handle};
}

static void log_resource(mach_port_t conn, const void *in, size_t inlen,
                         const void *out, size_t outlen) {
    uint64_t cpu = rd64(in, inlen, 0x38), size = rd64(in, inlen, 0x48);
    uint64_t va = rd64(out, outlen, 0), outcpu = rd64(out, outlen, 8);
    uint32_t handle = (uint32_t)rd64(out, outlen, 0x20);
    fprintf(trace_log, "RESOURCE_MAP class=%s gpu_va=0x%llx size=0x%llx handle=%u cpu_present=%u outcpu_present=%u\n",
            cname(conn), (unsigned long long)va, (unsigned long long)size, handle,
            cpu != 0, outcpu != 0);
    remember_bo(cpu ? cpu : outcpu, size, va, handle);
}

static int allowed(uint64_t va) {
    for (size_t i = 0; i < nallow; ++i) if (allow_va[i] == va) return 1;
    return 0;
}

static void dump_allowlisted(void) {
    static const char hex[] = "0123456789abcdef";
    mkdir(dump_dir, 0755);
    for (size_t i = 0; i < nbo; ++i) {
        if (!allowed(bos[i].gpu_va)) continue;
        uint64_t cap = bos[i].size < 0x10000 ? bos[i].size : 0x10000;
        unsigned char *buf = malloc((size_t)cap);
        mach_vm_size_t got = 0;
        kern_return_t kr = mach_vm_read_overwrite(mach_task_self(), bos[i].cpu, cap,
                                                   (mach_vm_address_t)buf, &got);
        char path[1024];
        snprintf(path, sizeof(path), "%s/bo_va%llx_sz%llx.hex", dump_dir,
                 (unsigned long long)bos[i].gpu_va, (unsigned long long)bos[i].size);
        FILE *f = (kr == KERN_SUCCESS && got) ? fopen(path, "w") : NULL;
        if (f) {
            fprintf(f, "# EXPLICIT COMMAND-BO ALLOWLIST gpu_va=0x%llx size=0x%llx read=0x%llx\n",
                    (unsigned long long)bos[i].gpu_va, (unsigned long long)bos[i].size,
                    (unsigned long long)got);
            for (uint64_t off = 0; off < got; off += 16) {
                fprintf(f, "%08llx: ", (unsigned long long)off);
                uint64_t end = off + 16 < got ? off + 16 : got;
                for (uint64_t j = off; j < end; ++j) {
                    fputc(hex[buf[j] >> 4], f); fputc(hex[buf[j] & 15], f);
                    if (((j - off) & 3) == 3) fputc(' ', f);
                }
                fputc('\n', f);
            }
            fclose(f);
        }
        fprintf(trace_log, "ALLOWLIST_DUMP gpu_va=0x%llx size=0x%llx kr=0x%x got=0x%llx path=%s\n",
                (unsigned long long)bos[i].gpu_va, (unsigned long long)bos[i].size, kr,
                (unsigned long long)got, f ? path : "NONE");
        free(buf);
    }
    fflush(trace_log);
}

static void *signal_thread(void *unused) {
    (void)unused;
    sigset_t set; sigemptyset(&set); sigaddset(&set, SIGUSR1);
    for (;;) {
        int sig = 0;
        if (sigwait(&set, &sig)) continue;
        pthread_mutex_lock(&lock); dump_allowlisted(); pthread_mutex_unlock(&lock);
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
    fprintf(trace_log, "# maptrace metadata_only=1 allowlisted_command_bos=%zu pointer_following=0\n", nallow);
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
