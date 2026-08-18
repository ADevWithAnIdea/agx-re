/*
 * EXP-0055 strict two-VA DATA-TRACE interposer.
 *
 * Only exact allocation-start GPU VAs 0x58000 and 0x68000 may be remembered
 * or read. Unknown allocations contribute metadata only. Captured words are
 * never interpreted as pointers, and executing memory is never changed.
 */
#define _DARWIN_C_SOURCE
#import <IOKit/IOKitLib.h>
#import <CoreFoundation/CoreFoundation.h>
#include <fcntl.h>
#include <mach/mach_vm.h>
#include <pthread.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#define DYLD_INTERPOSE(_replacement,_replacee) \
    __attribute__((used)) static struct { const void *replacement; const void *replacee; } \
    _interpose_##_replacee __attribute__((section("__DATA,__interpose"))) = \
    { (const void *)(unsigned long)&_replacement, (const void *)(unsigned long)&_replacee };

typedef struct { uint64_t va, expected_size, max_read; const char *role; } Allow;
static const Allow allowlist[] = {
    {0x0000000000058000ULL, 0x8000, 0x10000, "fixed-function-render-state"},
    {0x0000000000068000ULL, 0x88e0, 0x10000, "tiling-state"},
};

typedef struct {
    uint64_t cpu, size, va;
    uint32_t handle, occurrence;
} BO;
static BO bos[2];
static size_t nbo;
static FILE *trace_file;
static const char *dump_dir;
static pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;
static struct { mach_port_t port; char name[128]; } conns[64];
static size_t nconn;

static uint64_t rd64(const void *vp, size_t len, size_t off) {
    const uint8_t *p = vp;
    uint64_t v = 0;
    if (!p || off + 8 > len) return 0;
    for (unsigned i = 0; i < 8; ++i) v |= (uint64_t)p[off + i] << (8 * i);
    return v;
}

static const char *cname(mach_port_t p) {
    for (size_t i = 0; i < nconn; ++i)
        if (conns[i].port == p) return conns[i].name;
    return "unknown";
}

static const Allow *allowed(uint64_t va) {
    for (size_t i = 0; i < sizeof(allowlist) / sizeof(allowlist[0]); ++i)
        if (allowlist[i].va == va) return &allowlist[i];
    return NULL;
}

static void remember_allowed(uint64_t cpu, uint64_t size, uint64_t va,
                             uint32_t handle) {
    if (!cpu || !size || !allowed(va)) return;
    for (size_t i = 0; i < nbo; ++i) {
        if (bos[i].va == va) {
            ++bos[i].occurrence;
            return;
        }
    }
    if (nbo < sizeof(bos) / sizeof(bos[0]))
        bos[nbo++] = (BO){cpu, size, va, handle, 1};
}

static void snapshot(void) {
    if (mkdir(dump_dir, 0755) != 0) {
        fprintf(trace_file, "SNAPSHOT_ERROR phase=mkdir\n");
        fflush(trace_file);
        return;
    }
    for (size_t i = 0; i < nbo; ++i) {
        const Allow *a = allowed(bos[i].va);
        if (!a) continue;
        uint64_t cap = bos[i].size < a->max_read ? bos[i].size : a->max_read;
        uint8_t *buf = malloc((size_t)cap);
        if (!buf) {
            fprintf(trace_file, "SNAPSHOT_ERROR phase=malloc va=0x%llx\n",
                    (unsigned long long)bos[i].va);
            continue;
        }
        mach_vm_size_t got = 0;
        kern_return_t kr = mach_vm_read_overwrite(
            mach_task_self(), bos[i].cpu, cap, (mach_vm_address_t)buf, &got);
        char bin[1024], meta[1024];
        snprintf(bin, sizeof(bin), "%s/va_%llx.bin", dump_dir,
                 (unsigned long long)bos[i].va);
        snprintf(meta, sizeof(meta), "%s/va_%llx.meta", dump_dir,
                 (unsigned long long)bos[i].va);
        int binfd = -1, metafd = -1;
        if (kr == KERN_SUCCESS && got) {
            binfd = open(bin, O_WRONLY | O_CREAT | O_EXCL, 0644);
            if (binfd >= 0) {
                ssize_t written = write(binfd, buf, (size_t)got);
                close(binfd);
                if (written != (ssize_t)got) unlink(bin);
            }
            metafd = open(meta, O_WRONLY | O_CREAT | O_EXCL, 0644);
            if (metafd >= 0) {
                FILE *m = fdopen(metafd, "w");
                if (m) {
                    fprintf(m,
                        "gpu_va=0x%llx\nallocation_size=0x%llx\n"
                        "read_size=0x%llx\nrole=%s\nmapping_handle=%u\n"
                        "mapping_occurrence=%u\nfixed_allowlist=1\n"
                        "pointer_following=0\ncommand_mutation=0\n",
                        (unsigned long long)bos[i].va,
                        (unsigned long long)bos[i].size,
                        (unsigned long long)got, a->role, bos[i].handle,
                        bos[i].occurrence);
                    fclose(m);
                } else {
                    close(metafd);
                }
            }
        }
        fprintf(trace_file,
            "ALLOWLIST_DUMP va=0x%llx alloc=0x%llx cap=0x%llx got=0x%llx "
            "role=%s handle=%u occurrence=%u expected_size=0x%llx kr=0x%x "
            "bin_created=%u meta_created=%u\n",
            (unsigned long long)bos[i].va,
            (unsigned long long)bos[i].size,
            (unsigned long long)cap,
            (unsigned long long)got,
            a->role, bos[i].handle, bos[i].occurrence,
            (unsigned long long)a->expected_size, kr,
            binfd >= 0, metafd >= 0);
        free(buf);
    }
    fflush(trace_file);
}

static void *signal_thread(void *unused) {
    (void)unused;
    sigset_t set;
    sigemptyset(&set);
    sigaddset(&set, SIGUSR1);
    for (;;) {
        int sig = 0;
        if (sigwait(&set, &sig)) continue;
        pthread_mutex_lock(&lock);
        snapshot();
        pthread_mutex_unlock(&lock);
    }
    return NULL;
}

__attribute__((constructor)) static void init(void) {
    const char *path = getenv("ALLOWTRACE_LOG");
    trace_file = path ? fopen(path, "w") : stderr;
    if (!trace_file) trace_file = stderr;
    setvbuf(trace_file, NULL, _IOLBF, 0);
    dump_dir = getenv("ALLOWTRACE_DUMP_DIR");
    if (!dump_dir) dump_dir = "allowtrace_dumps";
    sigset_t set;
    sigemptyset(&set);
    sigaddset(&set, SIGUSR1);
    pthread_sigmask(SIG_BLOCK, &set, NULL);
    pthread_t th;
    pthread_create(&th, NULL, signal_thread, NULL);
    pthread_detach(th);
    fprintf(trace_file,
        "# EXP-0055 fixed_allowlist=2 unknown_bo_dump=0 pointer_following=0 "
        "shader_dump=0 command_mutation=0\n");
}

extern kern_return_t IOServiceOpen(io_service_t, task_port_t, uint32_t,
                                   io_connect_t *);
extern kern_return_t IOConnectCallMethod(mach_port_t, uint32_t, const uint64_t *,
    uint32_t, const void *, size_t, uint64_t *, uint32_t *, void *, size_t *);

static kern_return_t wrap_open(io_service_t service, task_port_t task,
                               uint32_t type, io_connect_t *out) {
    kern_return_t kr = IOServiceOpen(service, task, type, out);
    pthread_mutex_lock(&lock);
    if (kr == KERN_SUCCESS && out && nconn < 64) {
        io_name_t name = {0};
        IORegistryEntryGetName(service, name);
        conns[nconn].port = *out;
        snprintf(conns[nconn].name, sizeof(conns[nconn].name), "%s", name);
        ++nconn;
        fprintf(trace_file, "SERVICE_OPEN class=%s type=%u\n", name, type);
    }
    pthread_mutex_unlock(&lock);
    return kr;
}

static kern_return_t wrap_method(mach_port_t conn, uint32_t sel,
    const uint64_t *si, uint32_t sic, const void *st, size_t stc,
    uint64_t *so, uint32_t *soc, void *out, size_t *outc) {
    kern_return_t kr = IOConnectCallMethod(conn, sel, si, sic, st, stc,
                                           so, soc, out, outc);
    pthread_mutex_lock(&lock);
    fprintf(trace_file,
        "CALL class=%s sel=%u ret=0x%x in_struct=0x%zx out_struct=0x%zx\n",
        cname(conn), sel, kr, stc, outc ? *outc : 0);
    if (kr == KERN_SUCCESS && sel == 9 && st && out && outc) {
        uint64_t cpu = rd64(st, stc, 0x38);
        uint64_t size = rd64(st, stc, 0x48);
        uint64_t va = rd64(out, *outc, 0);
        uint64_t outcpu = rd64(out, *outc, 8);
        uint32_t handle = (uint32_t)rd64(out, *outc, 0x20);
        unsigned is_allowed = allowed(va) != NULL;
        fprintf(trace_file,
            "RESOURCE_MAP class=%s va=0x%llx size=0x%llx handle=%u "
            "cpu_present=%u outcpu_present=%u allowlisted=%u\n",
            cname(conn), (unsigned long long)va, (unsigned long long)size,
            handle, cpu != 0, outcpu != 0, is_allowed);
        if (is_allowed) remember_allowed(cpu ? cpu : outcpu, size, va, handle);
    }
    pthread_mutex_unlock(&lock);
    return kr;
}

DYLD_INTERPOSE(wrap_open, IOServiceOpen)
DYLD_INTERPOSE(wrap_method, IOConnectCallMethod)
