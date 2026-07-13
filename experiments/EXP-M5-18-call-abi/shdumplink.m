// shdumplink.m — clean-room OWN-SHADER compile+LINK+serialize tool (EXP-M5-18).
//
// Sibling of tools/shdump/shdump.m. The plain shdump builds a compute pipeline
// for the kernel ALONE; when that kernel calls a `visible_function_table`, the
// serialized archive's kernel `_agc.main` is only a 4-byte STUB because the real
// call target is resolved at PIPELINE-LINK time, not in the standalone archive.
//
// This tool builds the LINKED pipeline: it sets MTLComputePipelineDescriptor's
// `linkedFunctions` to the library's [[visible]] functions (so the compiler emits
// the real out-of-line call site + links the callee bodies) and serializes THAT
// pipeline to an MTLBinaryArchive. The archive then carries the kernel's real
// code (with the call instruction) AND each callee's machine code as separate
// __text symbols. agxparse.py isolates them out-of-band.
//
// CLEAN-ROOM: only the *public* Metal API on OUR OWN MSL source. Never
// disassembles or introspects any Apple binary. The only machine code examined
// is the compiled form of shaders whose source we wrote.
//
// Build (device, Command Line Tools only):
//   clang -fobjc-arc -framework Metal -framework Foundation -o shdumplink shdumplink.m
//
// Usage:
//   ./shdumplink -o out.bin [-f kernelName] [--no-fast-math] src.metal
//     -f    kernel (MTLFunctionTypeKernel) to build; default = first kernel found.
//   All [[visible]] functions in the library are added as linkedFunctions.functions.
//
// Emits the serialized binary archive to -o. Prints metadata to stderr:
//   library functions, the chosen kernel, and each visible function linked.

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <getopt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if !__has_feature(objc_arc)
#error compile with -fobjc-arc
#endif

static void die(const char *msg, NSError *err) {
    if (err) fprintf(stderr, "shdumplink: %s: %s\n", msg, [[err localizedDescription] UTF8String]);
    else     fprintf(stderr, "shdumplink: %s\n", msg);
    exit(EXIT_FAILURE);
}

enum { OPT_NO_FAST_MATH = 128 };
static const struct option longOpts[] = {
    {"output",       required_argument, NULL, 'o'},
    {"function",     required_argument, NULL, 'f'},
    {"no-fast-math", no_argument,       NULL, OPT_NO_FAST_MATH},
    {NULL, 0, NULL, 0}
};

int main(int argc, char *argv[]) {
    @autoreleasepool {
        const char *output = NULL, *want_fn = NULL;
        BOOL fastMath = YES;
        int c;
        while ((c = getopt_long(argc, argv, "o:f:", longOpts, NULL)) > 0) {
            switch (c) {
                case 'o': output = optarg; break;
                case 'f': want_fn = optarg; break;
                case OPT_NO_FAST_MATH: fastMath = NO; break;
                default:
                    fprintf(stderr, "usage: %s -o out.bin [-f kernel] [--no-fast-math] src.metal\n", argv[0]);
                    return EXIT_FAILURE;
            }
        }
        if (!output || optind >= argc) {
            fprintf(stderr, "usage: %s -o out.bin [-f kernel] [--no-fast-math] src.metal\n", argv[0]);
            return EXIT_FAILURE;
        }

        NSError *err = nil;
        NSString *src;
        if (strcmp(argv[optind], "-") == 0) {
            NSData *d = [[NSFileHandle fileHandleWithStandardInput] readDataToEndOfFile];
            src = [[NSString alloc] initWithData:d encoding:NSUTF8StringEncoding];
        } else {
            src = [NSString stringWithContentsOfFile:[NSString stringWithUTF8String:argv[optind]]
                                            encoding:NSUTF8StringEncoding error:&err];
            if (!src) die("failed to read source", err);
        }

        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        if (!dev) die("no Metal device", nil);
        fprintf(stderr, "shdumplink: device = %s\n", [[dev name] UTF8String]);

        MTLCompileOptions *opts = [MTLCompileOptions new];
        [opts setFastMathEnabled:fastMath];
        id<MTLLibrary> lib = [dev newLibraryWithSource:src options:opts error:&err];
        if (!lib) die("compile failed", err);

        // Pick the kernel and collect ALL [[visible]] functions.
        id<MTLFunction> kernelFn = nil;
        NSMutableArray *visibleFns = [NSMutableArray array];
        fprintf(stderr, "shdumplink: functions =");
        for (NSString *n in [lib functionNames]) {
            id<MTLFunction> fn = [lib newFunctionWithName:n];
            if (!fn) continue;
            MTLFunctionType t = [fn functionType];
            fprintf(stderr, " %s(type=%lu)", [n UTF8String], (unsigned long)t);
            if (t == MTLFunctionTypeVisible) {
                [visibleFns addObject:fn];
            } else if (t == MTLFunctionTypeKernel) {
                if (want_fn) {
                    if (strcmp([n UTF8String], want_fn) == 0) kernelFn = fn;
                } else if (!kernelFn) {
                    kernelFn = fn;
                }
            }
        }
        fprintf(stderr, "\n");
        if (!kernelFn) die("no matching kernel function found", nil);
        fprintf(stderr, "shdumplink: kernel = %s ; visible-linked = %lu\n",
                [[kernelFn name] UTF8String], (unsigned long)[visibleFns count]);

        // Build the LINKED compute pipeline descriptor.
        MTLComputePipelineDescriptor *cdesc = [MTLComputePipelineDescriptor new];
        [cdesc setComputeFunction:kernelFn];
        if ([visibleFns count] > 0) {
            MTLLinkedFunctions *lf = [MTLLinkedFunctions linkedFunctions];
            [lf setFunctions:visibleFns];
            [cdesc setLinkedFunctions:lf];
        }

        // Validate it compiles to a real device pipeline (with the linked callees).
        id<MTLComputePipelineState> pso =
            [dev newComputePipelineStateWithDescriptor:cdesc
                                               options:MTLPipelineOptionNone
                                            reflection:nil
                                                 error:&err];
        if (!pso) die("linked compute pipeline creation failed", err);
        fprintf(stderr, "shdumplink: linked pipeline OK (threadExecWidth=%lu)\n",
                (unsigned long)[pso threadExecutionWidth]);

        // Serialize the LINKED pipeline into a binary archive.
        MTLBinaryArchiveDescriptor *adesc = [MTLBinaryArchiveDescriptor new];
        id<MTLBinaryArchive> arc = [dev newBinaryArchiveWithDescriptor:adesc error:&err];
        if (!arc) die("binary archive creation failed", err);
        if (![arc addComputePipelineFunctionsWithDescriptor:cdesc error:&err])
            die("addComputePipelineFunctions (linked) failed", err);

        NSURL *url = [NSURL fileURLWithPath:[NSString stringWithUTF8String:output]];
        if (![arc serializeToURL:url error:&err]) die("serializeToURL failed", err);

        fprintf(stderr, "shdumplink: wrote %s\n", output);
        return 0;
    }
}
