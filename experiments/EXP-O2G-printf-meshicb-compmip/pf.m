// pf.m — EXP-O2G part 1: MSL shader printf / os_log lowering probe.
//
// Compiles our OWN compute kernel that calls printf(...) with distinctive marker
// arguments, attaches a MTLLogState (the shader-logging buffer), runs it under the
// tools/iotrace interposer, and SIGUSR1-dumps every registered BO so the printf/log
// buffer + the emitted records can be located and structurally decoded on the host.
//
// The log handler prints the runtime-DECODED message (end-to-end proof printf works),
// while the iotrace BO dump gives us the RAW buffer bytes (the record format the shader
// emits + what the runtime fills in). Marker args are distinctive constants so the raw
// records are greppable (host: pflog.py).
//
// CLEAN-ROOM: OWN-SHADER (our MSL) + DATA-TRACE (our own process's BOs). Nothing here
// disassembles any Apple binary; the log-buffer bytes are non-copyrightable data our
// own program produced. See ../../CLAUDE.md.
//
// Build (device): clang -fobjc-arc -framework Metal -framework Foundation -o pf pf.m
// Usage: pf [--grid N] [--tg N] [--bufsize BYTES] [--noprintf] [--dump]
//   --noprintf : compile/run the byte-identical kernel WITHOUT the printf call (control
//                for the cmdstream/argbuffer byte-diff: what does binding a log state add?)

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>

static void print_va(const char *label, uint64_t va) {
    unsigned char b[8];
    for (int i = 0; i < 8; i++) b[i] = (va >> (8 * i)) & 0xff;
    printf("VA %-12s = 0x%016llx  le=", label, (unsigned long long)va);
    for (int i = 0; i < 8; i++) printf("%02x", b[i]);
    printf("\n");
}

int main(int argc, char **argv) {
    @autoreleasepool {
        long grid = 4, tg = 4, bufsize = 4096, spin = 0, pings = 0;
        int doDump = 0, noprintf = 0, poll = 0, nohandler = 0;
        for (int i = 1; i < argc; i++) {
            if (!strcmp(argv[i], "--grid") && i + 1 < argc) grid = strtol(argv[++i], NULL, 0);
            else if (!strcmp(argv[i], "--tg") && i + 1 < argc) tg = strtol(argv[++i], NULL, 0);
            else if (!strcmp(argv[i], "--bufsize") && i + 1 < argc) bufsize = strtol(argv[++i], NULL, 0);
            else if (!strcmp(argv[i], "--spin") && i + 1 < argc) spin = strtol(argv[++i], NULL, 0);
            else if (!strcmp(argv[i], "--pings") && i + 1 < argc) pings = strtol(argv[++i], NULL, 0);
            else if (!strcmp(argv[i], "--noprintf")) noprintf = 1;
            else if (!strcmp(argv[i], "--poll")) poll = 1;       // dump BEFORE the runtime drains
            else if (!strcmp(argv[i], "--nohandler")) nohandler = 1;
            else if (!strcmp(argv[i], "--dump")) doDump = 1;
        }
        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        printf("DEVICE %s\n", [[dev name] UTF8String]);
        printf("CONFIG grid=%ld tg=%ld bufsize=%ld noprintf=%d\n", grid, tg, bufsize, noprintf);

        // Two format strings with different arg shapes -> lets the host decode which
        // record field is the format-id vs the packed args. Marker 0x51ABCDEF distinct.
        // macOS 26 / Metal 4: shader logging is os_log via <metal_logging>; C printf is not
        // exposed. os_log_default.log_info(fmt, args...) lowers the same way (format-id + packed
        // args into the MTLLogState buffer). We keep the "printf" naming for the concept.
        NSString *src = noprintf ?
          @"#include <metal_stdlib>\nusing namespace metal;\n"
           "kernel void k(device uint* o [[buffer(0)]], constant uint& spin [[buffer(1)]], uint i [[thread_position_in_grid]]) {\n"
           "  o[i] = i + 0x51ab0000u; }\n"
        :
          @"#include <metal_stdlib>\n#include <metal_logging>\nusing namespace metal;\n"
           "kernel void k(device uint* o [[buffer(0)]], constant uint& spin [[buffer(1)]], uint i [[thread_position_in_grid]]) {\n"
           "  o[i] = i + 0x51ab0000u;\n"
           "  if (i & 1u) os_log_default.log_info(\"ODD i=%u m=0x%08x\", i, 0x51abcdefu);\n"
           "  else        os_log_default.log_info(\"EVEN i=%u m=0x%08x g=%u f=%f\", i, 0x51abcdefu, 0xdd00u+i, float(i)+0.25f);\n"
           "  uint acc=i; for (uint s=0;s<spin;s++){ acc=acc*1664525u+1013904223u; }\n"
           "  o[i] += acc & 1u;\n"
           "}\n";

        NSError *err = nil;
        // enableLogging=YES is REQUIRED for shader os_log to emit (default is NO -> no-op).
        MTLCompileOptions *co = [MTLCompileOptions new];
        if (@available(macOS 15.0, *)) { if (!noprintf) co.enableLogging = YES; }
        id<MTLLibrary> lib = [dev newLibraryWithSource:src options:co error:&err];
        if (!lib) { printf("COMPILE_FAIL %s\n", [[err localizedDescription] UTF8String]); return 1; }
        id<MTLFunction> fn = [lib newFunctionWithName:@"k"];
        id<MTLComputePipelineState> pso = [dev newComputePipelineStateWithFunction:fn error:&err];
        if (!pso) { printf("PIPELINE_FAIL %s\n", [[err localizedDescription] UTF8String]); return 1; }

        // ---- shader logging buffer (MTLLogState). bufferSize = the GPU log buffer. ----
        id<MTLCommandQueue> q = nil;
        if (@available(macOS 15.0, *)) {
            MTLLogStateDescriptor *ld = [MTLLogStateDescriptor new];
            ld.level = MTLLogLevelDebug;
            ld.bufferSize = (NSInteger)bufsize;
            id<MTLLogState> logState = [dev newLogStateWithDescriptor:ld error:&err];
            if (!logState) { printf("LOGSTATE_FAIL %s\n", [[err localizedDescription] UTF8String]); }
            else {
                if (!nohandler)
                [logState addLogHandler:^(NSString *sub, NSString *cat, MTLLogLevel lvl, NSString *msg) {
                    printf("LOGHANDLER sub=%s cat=%s lvl=%ld msg=<<%s>>\n",
                           sub?[sub UTF8String]:"", cat?[cat UTF8String]:"", (long)lvl,
                           msg?[msg UTF8String]:"");
                }];
                MTLCommandQueueDescriptor *qd = [MTLCommandQueueDescriptor new];
                qd.logState = logState;
                q = [dev newCommandQueueWithDescriptor:qd];
                printf("LOGSTATE ok bufferSize=%ld level=%ld\n", (long)ld.bufferSize, (long)ld.level);
            }
        }
        if (!q) { q = [dev newCommandQueue]; printf("LOGSTATE unavailable -> plain queue\n"); }

        size_t n = (size_t)grid;
        id<MTLBuffer> ob = [dev newBufferWithLength:n * 4 + 256 options:MTLResourceStorageModeShared];
        print_va("outBuf", [ob gpuAddress]);

        uint32_t spinv = (uint32_t)spin;
        id<MTLBuffer> sb = [dev newBufferWithBytes:&spinv length:4 options:MTLResourceStorageModeShared];
        id<MTLCommandBuffer> cb = [q commandBuffer];
        id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
        [enc setComputePipelineState:pso];
        [enc setBuffer:ob offset:0 atIndex:0];
        [enc setBuffer:sb offset:0 atIndex:1];
        [enc dispatchThreads:MTLSizeMake(grid, 1, 1) threadsPerThreadgroup:MTLSizeMake(tg, 1, 1)];
        [enc endEncoding];
        [cb commit];
        if (pings > 0) {
            // Race the drain: spam SIGUSR1 while the kernel is still spinning (records already
            // written by os_log, not yet completed -> not yet drained). IOTRACE_DUMP_PERSIG=1
            // puts each snapshot in its own dumpNN/ dir; the host greps all for the marker.
            for (long p = 0; p < pings; p++) { kill(getpid(), SIGUSR1); usleep(2000); }
            [cb waitUntilCompleted];
            printf("SUBMIT done status=%ld (pinged %ld)\n", (long)[cb status], pings);
        } else if (poll) {
            // Busy-poll status and SIGUSR1-dump the instant the GPU completes, BEFORE the
            // runtime's completion drain reads/reuses the log buffer. No waitUntilCompleted
            // (that triggers the synchronous drain), no run-loop (that services the handler).
            while ([cb status] < MTLCommandBufferStatusCompleted) { /* spin */ }
            printf("SUBMIT done status=%ld (poll)\n", (long)[cb status]);
            if (doDump) { fflush(stdout); kill(getpid(), SIGUSR1); usleep(500000); }
        } else {
            [cb waitUntilCompleted];
            printf("SUBMIT done status=%ld\n", (long)[cb status]);
            if ([cb error]) printf("CB_ERROR %s\n", [[[cb error] localizedDescription] UTF8String]);
            if (doDump) { fflush(stdout); kill(getpid(), SIGUSR1); usleep(500000); }
            // Drain the run loop so the async shader-log handler delivers the DECODED strings.
            [[NSRunLoop currentRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.8]];
        }
        uint32_t *op = (uint32_t *)[ob contents];
        printf("OUT o[0..3]= %08x %08x %08x %08x\n", op[0], op[1], op[2], op[3]);
        return 0;
    }
}
