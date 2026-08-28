/*
 * EXP-0108 dev interposer (exploration only, not the frozen harness).
 * Broadens EXP-0048's allowtrace.c: full inventory metadata for every
 * registered BO (sel==9 resource-map), full-content capture only for a
 * known-role list of small structured descriptor/control BOs, SHA-256
 * content hash (never raw bytes) for everything else. No pointer following,
 * no interpretation of unknown-BO content.
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

typedef struct { uint64_t va, max_read; const char *role; } Known;
/* Named roles: exact fixed VAs correlated with a role by prior experiments
 * (EXP-0048, EXP-M4-08/09) or by this experiment's own exploration. Content
 * is captured (capped) for these regardless of size class. */
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

/*
 * Content-capture eligibility policy (applies to any BO not already in the
 * named list above; those get the exact "role" name; these get role
 * "unnamed-descriptor-candidate"):
 *
 *   capture iff  size <= 0x20000
 *            AND NOT (va is in [0, 0x10000000000) and va is not one of the
 *                     three named low VAs above)      -- excludes the small
 *                     low "boring" reserved slots we have not characterized
 *                     and have observed to be config-invariant.
 *            AND NOT (va in [0x10000000000, 0x10000020000))  -- excludes the
 *                     4GiB-aligned code window (EXP-0042: GPU-executable
 *                     machine code, ours+possibly driver-authored, has only
 *                     ever been observed here; doubled beyond the observed
 *                     0x10000 size as a margin) and its immediate neighbor
 *                     slab.
 *            AND va != 0x6f00000000            -- one distant, unclassified
 *                     one-off region out of this experiment's scope; left
 *                     hash-only pending its own dedicated investigation.
 *
 * This policy is a PRE_REGISTRATION-frozen decision (see PRE_REGISTRATION.md
 * "content-capture policy"), not an ad hoc runtime choice. It is deliberately
 * conservative: every region it captures has, in this experiment's own
 * exploration and in EXP-0048/EXP-0042/EXP-M4-08/09, been either our own
 * data or small structured descriptor/control content -- never observed
 * executable code outside the excluded code window.
 */
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
    if (inv) fprintf(inv, "va\tsize\thandle\trole\tcontent_captured\tsha256\n");
    for (size_t i=0; i<nbo; ++i) {
        const char *role = "unclassified";
        int eligible = capture_eligible(bos[i].va, bos[i].size, &role);
        uint64_t cap = eligible ? (bos[i].size < 0x20000 ? bos[i].size : 0x20000)
                                 : (bos[i].size < 0x8000 ? bos[i].size : 0x8000);
        uint8_t *buf = malloc((size_t)cap);
        mach_vm_size_t got = 0;
        kern_return_t kr = KERN_FAILURE;
        char hexhash[65] = {0};
        if (buf) {
            kr = mach_vm_read_overwrite(mach_task_self(), bos[i].cpu, cap,
                (mach_vm_address_t)buf, &got);
            if (kr == KERN_SUCCESS && got) sha256hex(buf, (size_t)got, hexhash);
        }
        int captured = 0;
        if (eligible && kr == KERN_SUCCESS && got) {
            captured = 1;
            char bin[1200];
            snprintf(bin,sizeof(bin),"%s/va_%llx.bin",sub,(unsigned long long)bos[i].va);
            FILE *f = fopen(bin,"wb"); if (f) { fwrite(buf,1,(size_t)got,f); fclose(f); }
        }
        if (inv) fprintf(inv, "0x%llx\t0x%llx\t%u\t%s\t%d\t%s\n",
            (unsigned long long)bos[i].va, (unsigned long long)bos[i].size, bos[i].handle,
            role, captured, hexhash[0] ? hexhash : "NA");
        fprintf(trace_file,"SNAPSHOT va=0x%llx size=0x%llx role=%s captured=%d cap=0x%llx got=0x%llx sha256=%s\n",
            (unsigned long long)bos[i].va,(unsigned long long)bos[i].size,
            role, captured,
            (unsigned long long)cap,(unsigned long long)got, hexhash[0] ? hexhash : "NA");
        free(buf);
    }
    if (inv) fclose(inv);
    fflush(trace_file);
}

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
    fprintf(trace_file,"# EXP-0108 dev wtrace known_roles=%zu unknown_bo_content=HASH_ONLY pointer_following=0\n",
        sizeof(known)/sizeof(known[0]));
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
