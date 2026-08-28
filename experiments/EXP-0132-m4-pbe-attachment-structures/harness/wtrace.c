/*
 * EXP-0132 interposer. Forked from EXP-0108-m4-bg-eot-programs/harness/wtrace.c
 * (same broadened-inventory technique: full metadata for every registered
 * IOKit resource-map BO, full-content capture only for a known-role list of
 * small structured descriptor/control BOs, SHA-256 content hash -- never raw
 * bytes -- for everything else; no pointer following, no interpretation of
 * unknown-BO content).
 *
 * FIX over EXP-0108 (the named open item this experiment is dispatched to
 * resolve): EXP-0108's RESULTS.md section 2.3 documents a SIGUSR1-snapshot
 * `mach_vm_read_overwrite` timing race -- a role present with identical size
 * in both runs of a pair occasionally has `content_captured=False` in
 * exactly one run. EXP-0108 built two mitigations (a cross-run "reproducible
 * projection" that drops non-deterministic fields, and a <=5-flake budget)
 * but never removed the race itself. This file removes it by construction:
 *
 *   1. `wtrace_snapshot_now()` is exported (not `static`) so the probe can
 *      call it DIRECTLY, in-process, on the SAME thread, at the SAME point
 *      in program order (immediately after `waitUntilCompleted`) -- instead
 *      of posting an async SIGUSR1 that a separate signal-handling thread
 *      picks up nondeterministically relative to whatever the main thread
 *      (or Metal's own internal driver threads) do next. This eliminates
 *      the send/receive race entirely; it is not a timing mitigation, it is
 *      removal of the concurrent path. The old SIGUSR1 path is kept only as
 *      a compatibility fallback for a caller that cannot dlsym the direct
 *      entry point (e.g. a plain `kill -USR1 <pid>` from a shell); the two
 *      paths share the same `snapshot()` body and the same lock.
 *   2. Defense in depth: each individual `mach_vm_read_overwrite` call is
 *      retried up to `MAX_READ_TRIES` times with a short sleep between
 *      attempts if it fails or returns 0 bytes, in case a region is
 *      transiently busy for a reason unrelated to signal delivery (e.g. a
 *      brief internal Metal resource-recycling window). The retry count is
 *      recorded ONLY in the trace log (ungated, informational) -- never in
 *      a byte-compared record -- per the standing "no nondeterministic
 *      field in a gated record" rule.
 *
 * Everything else (known-role table, content-capture eligibility policy,
 * inventory format) is unchanged from EXP-0108 so this experiment's field
 * extraction can reuse the exact same trusted offsets/roles that prior work
 * established.
 */
#define _DARWIN_C_SOURCE
#import <IOKit/IOKitLib.h>
#import <CoreFoundation/CoreFoundation.h>
#include <CommonCrypto/CommonDigest.h>
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

/* This experiment's own pre-capture diagnostic (see PROGRESS.md) found that
 * 6 tries / 5ms was occasionally insufficient even for the SIMPLEST case in
 * a rapid-fire loop of many fresh processes (reliable standalone, flaky
 * back-to-back) -- consistent with a brief real backing-page/mapping delay
 * after waitUntilCompleted, not just signal-delivery timing. Widened with
 * margin: up to 40 tries * 10ms = 400ms worst case per region, still far
 * under any per-case timeout budget. */
#define MAX_READ_TRIES 40
#define RETRY_SLEEP_USEC 10000

typedef struct { uint64_t va, max_read; const char *role; } Known;
/* Named roles: exact fixed VAs correlated with a role by prior experiments
 * (EXP-0048, EXP-M4-08/09, EXP-0108) or by this experiment's own
 * exploration. Content is captured (capped) for these regardless of size
 * class. Unchanged from EXP-0108 -- reusing the same trusted roles. */
static const Known known[] = {
    {0x0000000000018000ULL, 0x10000, "vdm-command-state"},
    {0x0000000000058000ULL, 0x10000, "fixed-function-render-state"},
    {0x0000000000068000ULL, 0x10000, "tiling-state"},
    {0x0000010000018200ULL, 0x02000, "mrt-attachment-descriptors"},
    {0x0000010000110000ULL, 0x01000, "single-rt-color-descriptor"},
    {0x0000010000120000ULL, 0x01000, "attachment-slot-b"},
    {0x0000010000128000ULL, 0x01000, "clear-color-arena"},
    {0x0000010000140000ULL, 0x01000, "sparse-tiler-param-header"},
};

/* Content-capture eligibility policy -- byte-for-byte identical to
 * EXP-0108's PRE_REGISTRATION-frozen policy (see this experiment's own
 * PRE_REGISTRATION.md "content-capture policy", which reproduces the same
 * rule and the same rationale). */
static int capture_eligible(uint64_t va, uint64_t size, const char **role_out) {
    const Known *k = NULL;
    for (size_t i=0; i<sizeof(known)/sizeof(known[0]); ++i)
        if (known[i].va == va) { k = &known[i]; break; }
    if (k) { *role_out = k->role; return 1; }
    *role_out = "unnamed-descriptor-candidate";
    if (size > 0x20000ULL) return 0;
    if (va == 0x6f00000000ULL) return 0;
    if (va < 0x10000000000ULL) return 0;              /* only the 3 named low VAs qualify, handled above */
    if (va < 0x10000020000ULL) return 0;               /* code-window margin */
    return 1;
}

typedef struct { uint64_t cpu, size, va; uint32_t handle; } BO;
static BO bos[8192];
static size_t nbo;
static FILE *trace_file;
static const char *dump_dir;
static pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;
static struct { mach_port_t port; char name[128]; } conns[64];
static size_t nconn;
static int dump_seq = 0;

static uint64_t rd64(const void *vp, size_t len, size_t off) {
    const uint8_t *p = vp; uint64_t v = 0;
    if (!p || off + 8 > len) return 0;
    for (unsigned i = 0; i < 8; ++i) v |= (uint64_t)p[off+i] << (8*i);
    return v;
}

static const char *cname(mach_port_t p) {
    for (size_t i=0; i<nconn; ++i) if (conns[i].port == p) return conns[i].name;
    return "unknown";
}

static const Known *find_known(uint64_t va) {
    for (size_t i=0; i<sizeof(known)/sizeof(known[0]); ++i)
        if (known[i].va == va) return &known[i];
    return NULL;
}

static void remember(uint64_t cpu, uint64_t size, uint64_t va, uint32_t handle) {
    if (!cpu || !size) return;
    for (size_t i=0; i<nbo; ++i) if (bos[i].cpu == cpu) {
        bos[i] = (BO){cpu,size,va,handle}; return;
    }
    if (nbo < sizeof(bos)/sizeof(bos[0])) bos[nbo++] = (BO){cpu,size,va,handle};
}

static void sha256hex(const uint8_t *buf, size_t len, char out[65]) {
    unsigned char d[CC_SHA256_DIGEST_LENGTH];
    CC_SHA256(buf, (CC_LONG)len, d);
    for (int i = 0; i < CC_SHA256_DIGEST_LENGTH; ++i) sprintf(out + i*2, "%02x", d[i]);
    out[64] = 0;
}

/* Read one BO's content with bounded retry. Retry exists only as defense in
 * depth (see file header); the primary race fix is that this whole function
 * now runs synchronously in-process instead of behind an async signal.
 * Returns KERN_SUCCESS/got via out-params; *tries_out records the attempt
 * count actually used (ungated diagnostic only). */
static kern_return_t read_with_retry(uint64_t cpu, uint64_t cap, uint8_t *buf,
                                      mach_vm_size_t *got_out, int *tries_out) {
    kern_return_t kr = KERN_FAILURE;
    mach_vm_size_t got = 0;
    int tries;
    for (tries = 0; tries < MAX_READ_TRIES; ++tries) {
        got = 0;
        kr = mach_vm_read_overwrite(mach_task_self(), cpu, cap, (mach_vm_address_t)buf, &got);
        if (kr == KERN_SUCCESS && got) break;
        usleep(RETRY_SLEEP_USEC);
    }
    *got_out = got;
    *tries_out = tries + 1;
    return kr;
}

static void snapshot(void) {
    char sub[1200];
    snprintf(sub, sizeof(sub), "%s/dump%02d", dump_dir, dump_seq++);
    mkdir(dump_dir, 0755);
    mkdir(sub, 0755);
    /* Sort a stable view by va so output is deterministic in ordering. */
    for (size_t i=0; i<nbo; ++i) {
        for (size_t j=i+1; j<nbo; ++j) if (bos[j].va < bos[i].va) { BO t=bos[i]; bos[i]=bos[j]; bos[j]=t; }
    }
    char metaall[2048];
    snprintf(metaall, sizeof(metaall), "%s/inventory.tsv", sub);
    FILE *inv = fopen(metaall, "w");
    if (inv) fprintf(inv, "va\tsize\thandle\trole\tcontent_captured\tsha256\ttries\n");
    for (size_t i=0; i<nbo; ++i) {
        const char *role = "unclassified";
        int eligible = capture_eligible(bos[i].va, bos[i].size, &role);
        uint64_t cap = eligible ? (bos[i].size < 0x20000 ? bos[i].size : 0x20000)
                                 : (bos[i].size < 0x8000 ? bos[i].size : 0x8000);
        uint8_t *buf = malloc((size_t)cap);
        mach_vm_size_t got = 0;
        kern_return_t kr = KERN_FAILURE;
        int tries = 0;
        char hexhash[65] = {0};
        if (buf) {
            kr = read_with_retry(bos[i].cpu, cap, buf, &got, &tries);
            if (kr == KERN_SUCCESS && got) sha256hex(buf, (size_t)got, hexhash);
        }
        int captured = 0;
        if (eligible && kr == KERN_SUCCESS && got) {
            captured = 1;
            char bin[1200];
            snprintf(bin,sizeof(bin),"%s/va_%llx.bin",sub,(unsigned long long)bos[i].va);
            FILE *f = fopen(bin,"wb"); if (f) { fwrite(buf,1,(size_t)got,f); fclose(f); }
        }
        if (inv) fprintf(inv, "0x%llx\t0x%llx\t%u\t%s\t%d\t%s\t%d\n",
            (unsigned long long)bos[i].va, (unsigned long long)bos[i].size, bos[i].handle,
            role, captured, hexhash[0] ? hexhash : "NA", tries);
        fprintf(trace_file,"SNAPSHOT va=0x%llx size=0x%llx role=%s captured=%d cap=0x%llx got=0x%llx tries=%d sha256=%s\n",
            (unsigned long long)bos[i].va,(unsigned long long)bos[i].size,
            role, captured,
            (unsigned long long)cap,(unsigned long long)got, tries, hexhash[0] ? hexhash : "NA");
        free(buf);
    }
    if (inv) fclose(inv);
    fflush(trace_file);
}

/* Exported direct entry point -- the primary race fix. The caller (probe.m)
 * dlsym()s this symbol and calls it synchronously, on its own thread,
 * immediately after waitUntilCompleted and before any other action. */
void wtrace_snapshot_now(void) {
    pthread_mutex_lock(&lock);
    snapshot();
    pthread_mutex_unlock(&lock);
}

/* Compatibility fallback: an external `kill -USR1 <pid>` still works,
 * routed through the same snapshot()/lock. Not used by this experiment's
 * own probe.m (which calls wtrace_snapshot_now directly) but kept so the
 * dylib remains usable the old way if needed for manual investigation. */
static void *signal_thread(void *unused) {
    (void)unused; sigset_t set; sigemptyset(&set); sigaddset(&set,SIGUSR1);
    for (;;) { int sig=0; if (sigwait(&set,&sig)) continue;
        pthread_mutex_lock(&lock); snapshot(); pthread_mutex_unlock(&lock); }
    return NULL;
}

__attribute__((constructor)) static void init(void) {
    const char *path=getenv("WTRACE_LOG"); trace_file=path?fopen(path,"w"):stderr;
    if(!trace_file)trace_file=stderr; setvbuf(trace_file,NULL,_IOLBF,0);
    dump_dir=getenv("WTRACE_DUMP_DIR"); if(!dump_dir)dump_dir="wtrace_dumps";
    sigset_t set; sigemptyset(&set); sigaddset(&set,SIGUSR1); pthread_sigmask(SIG_BLOCK,&set,NULL);
    pthread_t th; pthread_create(&th,NULL,signal_thread,NULL); pthread_detach(th);
    fprintf(trace_file,"# EXP-0132 wtrace known_roles=%zu unknown_bo_content=HASH_ONLY pointer_following=0 "
        "direct_snapshot_entry=wtrace_snapshot_now max_read_tries=%d\n",
        sizeof(known)/sizeof(known[0]), MAX_READ_TRIES);
}

extern kern_return_t IOServiceOpen(io_service_t,task_port_t,uint32_t,io_connect_t*);
extern kern_return_t IOConnectCallMethod(mach_port_t,uint32_t,const uint64_t*,uint32_t,
    const void*,size_t,uint64_t*,uint32_t*,void*,size_t*);

static kern_return_t wrap_open(io_service_t service,task_port_t task,uint32_t type,io_connect_t*out) {
    kern_return_t kr=IOServiceOpen(service,task,type,out);
    pthread_mutex_lock(&lock);
    if(kr==KERN_SUCCESS&&out&&nconn<64){io_name_t name={0};IORegistryEntryGetName(service,name);
        conns[nconn].port=*out;snprintf(conns[nconn].name,sizeof(conns[nconn].name),"%s",name);++nconn;
        fprintf(trace_file,"SERVICE_OPEN class=%s type=%u\n",name,type);}
    pthread_mutex_unlock(&lock);return kr;
}

static kern_return_t wrap_method(mach_port_t conn,uint32_t sel,const uint64_t*si,uint32_t sic,
    const void*st,size_t stc,uint64_t*so,uint32_t*soc,void*out,size_t*outc) {
    kern_return_t kr=IOConnectCallMethod(conn,sel,si,sic,st,stc,so,soc,out,outc);
    pthread_mutex_lock(&lock);
    fprintf(trace_file,"CALL class=%s sel=%u ret=0x%x in_struct=0x%zx out_struct=0x%zx\n",
        cname(conn),sel,kr,stc,outc?*outc:0);
    if(kr==KERN_SUCCESS&&sel==9&&st&&out&&outc){
        uint64_t cpu=rd64(st,stc,0x38),size=rd64(st,stc,0x48),va=rd64(out,*outc,0);
        uint64_t outcpu=rd64(out,*outc,8);uint32_t handle=(uint32_t)rd64(out,*outc,0x20);
        fprintf(trace_file,"RESOURCE_MAP class=%s va=0x%llx size=0x%llx handle=%u cpu_present=%u outcpu_present=%u known=%u\n",
            cname(conn),(unsigned long long)va,(unsigned long long)size,handle,cpu!=0,outcpu!=0,find_known(va)!=NULL);
        remember(cpu?cpu:outcpu,size,va,handle);
    }
    pthread_mutex_unlock(&lock);return kr;
}

DYLD_INTERPOSE(wrap_open,IOServiceOpen)
DYLD_INTERPOSE(wrap_method,IOConnectCallMethod)
