// EXP-0085 interlock_probe — single-case, single-process Metal harness for
// the MEM-13/MEM-14 interlock kernels (kernels/interlock.metal). One dispatch
// per process, one JSON record to stdout. Public Metal API only. Clean room:
// HW-PROBE + OWN-SHADER.
//
// Usage:
//   interlock_probe --source PATH --kernel NAME --n N [--afactor K]
//                    --timeout SEC
//
// afactor: buffer(0) "a" has n*afactor elements (K=48 for il_chain48; K=1
// for every other kernel, the default).
//
// Deterministic per-lane content (fixed, never parameterized):
//   a[j] = j % 97          (integer-valued float; exact under any summation
//                            order within the ranges this experiment uses)
//   b[i] = (i % 89) + 1     (integer-valued float, never 0)
//   idx[i] = (i * 7 + 3) % n   (a fixed permutation-like gather pattern;
//                                exact formula frozen so analysis.py can
//                                recompute expectations independently)
//   atom[0] = 0 (pre-zeroed)
//
// Output JSON fields: kernel, n, afactor, status, cb_status, err,
// gputime_ns, out_hex (n*4 bytes), atom_final (uint32, null if unused).

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void on_alarm(int sig) { (void)sig; _exit(98); }

static void hex_append(NSMutableString *s, const uint8_t *bytes, size_t n) {
    static const char *hx = "0123456789abcdef";
    for (size_t i = 0; i < n; i++) {
        [s appendFormat:@"%c%c", hx[(bytes[i] >> 4) & 0xf], hx[bytes[i] & 0xf]];
    }
}

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        const char *source_path = NULL, *kernel = NULL;
        long n = 0, afactor = 1, timeout_s = 30;

        for (int i = 1; i < argc; i++) {
            if (!strcmp(argv[i], "--source")) source_path = argv[++i];
            else if (!strcmp(argv[i], "--kernel")) kernel = argv[++i];
            else if (!strcmp(argv[i], "--n")) n = atol(argv[++i]);
            else if (!strcmp(argv[i], "--afactor")) afactor = atol(argv[++i]);
            else if (!strcmp(argv[i], "--timeout")) timeout_s = atol(argv[++i]);
            else { fprintf(stderr, "unknown arg %s\n", argv[i]); return 2; }
        }
        if (!source_path || !kernel || n <= 0) {
            fprintf(stderr, "usage: --source --kernel --n [--afactor] --timeout\n");
            return 2;
        }

        signal(SIGALRM, on_alarm);
        alarm((unsigned)timeout_s);

        NSMutableDictionary *out = [NSMutableDictionary dictionary];
        out[@"kernel"] = @(kernel);
        out[@"n"] = @(n);
        out[@"afactor"] = @(afactor);

        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        if (!dev) { printf("JSON {\"status\":\"no_device\"}\n"); return 1; }

        NSError *rerr = nil;
        NSString *src = [NSString stringWithContentsOfFile:@(source_path) encoding:NSUTF8StringEncoding error:&rerr];
        if (!src) { printf("JSON {\"status\":\"read_fail\"}\n"); return 1; }

        MTLCompileOptions *opts = [MTLCompileOptions new];
        opts.fastMathEnabled = NO;
        NSError *err = nil;
        id<MTLLibrary> lib = [dev newLibraryWithSource:src options:opts error:&err];
        if (!lib) {
            out[@"status"] = @"compile_fail";
            out[@"compile_err"] = err ? err.localizedDescription : @"unknown";
            NSData *j = [NSJSONSerialization dataWithJSONObject:out options:0 error:nil];
            printf("JSON %s\n", (const char*)j.bytes);
            return 0;
        }
        id<MTLFunction> fn = [lib newFunctionWithName:@(kernel)];
        if (!fn) {
            out[@"status"] = @"function_missing";
            NSData *j = [NSJSONSerialization dataWithJSONObject:out options:0 error:nil];
            printf("JSON %s\n", (const char*)j.bytes);
            return 0;
        }
        id<MTLComputePipelineState> pso = [dev newComputePipelineStateWithFunction:fn error:&err];
        if (!pso) {
            out[@"status"] = @"pipeline_fail";
            out[@"compile_err"] = err ? err.localizedDescription : @"unknown";
            NSData *j = [NSJSONSerialization dataWithJSONObject:out options:0 error:nil];
            printf("JSON %s\n", (const char*)j.bytes);
            return 0;
        }

        MTLResourceOptions ropt = MTLResourceStorageModeShared;
        long acount = n * afactor;
        id<MTLBuffer> b_a = [dev newBufferWithLength:acount * sizeof(float) options:ropt];
        {
            float *p = b_a.contents;
            for (long j = 0; j < acount; j++) p[j] = (float)(j % 97);
        }
        id<MTLBuffer> b_b = [dev newBufferWithLength:n * sizeof(float) options:ropt];
        {
            float *p = b_b.contents;
            for (long i = 0; i < n; i++) p[i] = (float)((i % 89) + 1);
        }
        id<MTLBuffer> b_idx = [dev newBufferWithLength:n * sizeof(uint32_t) options:ropt];
        {
            uint32_t *p = b_idx.contents;
            for (long i = 0; i < n; i++) p[i] = (uint32_t)((i * 7 + 3) % n);
        }
        id<MTLBuffer> b_atom = [dev newBufferWithLength:sizeof(uint32_t) options:ropt];
        memset(b_atom.contents, 0, sizeof(uint32_t));
        id<MTLBuffer> b_out = [dev newBufferWithLength:n * sizeof(float) options:ropt];
        memset(b_out.contents, 0xEE, n * sizeof(float));

        id<MTLCommandQueue> q = [dev newCommandQueue];
        id<MTLCommandBuffer> cb = [q commandBuffer];
        id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
        [enc setComputePipelineState:pso];
        [enc setBuffer:b_a offset:0 atIndex:0];
        [enc setBuffer:b_b offset:0 atIndex:1];
        [enc setBuffer:b_idx offset:0 atIndex:2];
        [enc setBuffer:b_atom offset:0 atIndex:3];
        [enc setBuffer:b_out offset:0 atIndex:4];
        NSUInteger tg = MIN((NSUInteger)n, (NSUInteger)pso.maxTotalThreadsPerThreadgroup);
        if (tg == 0) tg = 1;
        [enc dispatchThreads:MTLSizeMake((NSUInteger)n, 1, 1)
            threadsPerThreadgroup:MTLSizeMake(tg, 1, 1)];
        [enc endEncoding];

        [cb commit];
        [cb waitUntilCompleted];
        double gputime_ns = ([cb GPUEndTime] > 0) ? ([cb GPUEndTime] - [cb GPUStartTime]) * 1e9 : -1;
        alarm(0);

        MTLCommandBufferStatus cbs = cb.status;
        out[@"cb_status"] = @((long)cbs);
        out[@"status"] = (cbs == MTLCommandBufferStatusCompleted) ? @"ok" : @"cb_error";
        if (cb.error) out[@"err"] = cb.error.localizedDescription;
        out[@"gputime_ns"] = @(gputime_ns);

        NSMutableString *oh = [NSMutableString string];
        hex_append(oh, b_out.contents, n * sizeof(float));
        out[@"out_hex"] = oh;
        out[@"atom_final"] = @(*(uint32_t*)b_atom.contents);

        NSError *jerr = nil;
        NSData *j = [NSJSONSerialization dataWithJSONObject:out options:0 error:&jerr];
        if (!j) { fprintf(stderr, "json encode fail\n"); return 1; }
        fwrite("JSON ", 1, 5, stdout);
        fwrite(j.bytes, 1, j.length, stdout);
        fwrite("\n", 1, 1, stdout);
        int ok = (fflush(stdout) == 0) && (ferror(stdout) == 0);
        return ok ? 0 : 1;
    }
}
