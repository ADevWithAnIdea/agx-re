// shdump.m — clean-room OWN-SHADER compile+serialize tool.
//
// Part of the A18 Pro GPU clean-room RE project. Takes OUR OWN MSL source,
// compiles it at runtime with the public Metal API, builds a compute OR render
// pipeline, and serializes the device-compiled pipeline into an MTLBinaryArchive
// container. The container is then parsed OUT-OF-BAND by our own parser
// (agxparse.py) to isolate the raw AGX machine-code bytes the GPU executes.
//
// CLEAN-ROOM: this only uses the *public* Metal API on OUR OWN source. It never
// disassembles or introspects any Apple binary. The only machine code we ever
// look at is the compiled form of the shader whose source we wrote.
//
// Build (on the A18 device, Command Line Tools only):
//   clang -fobjc-arc -framework Metal -framework Foundation -o shdump shdump.m
//
// Usage:
//   Compute (default):
//     ./shdump -o out.bin [-f functionName] [--no-fast-math] source.metal
//     ./shdump -o out.bin -                 (read MSL from stdin)
//   Render (vertex+fragment, EXP-0008):
//     ./shdump -o out.bin --render [--vertex vfn] [--fragment ffn]
//              [--color-format N] [--no-fast-math] source.metal
//
// Emits the serialized binary archive to the -o path. Prints metadata (library
// function names, chosen function(s), thread-execution width) to stderr.

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
    if (err) {
        fprintf(stderr, "shdump: %s: %s\n", msg, [[err localizedDescription] UTF8String]);
    } else {
        fprintf(stderr, "shdump: %s\n", msg);
    }
    exit(EXIT_FAILURE);
}

enum { OPT_NO_FAST_MATH = 128, OPT_RENDER, OPT_VERTEX, OPT_FRAGMENT, OPT_COLOR_FORMAT };

static const struct option longOpts[] = {
    {"output",       required_argument, NULL, 'o'},
    {"function",     required_argument, NULL, 'f'},
    {"no-fast-math", no_argument,       NULL, OPT_NO_FAST_MATH},
    {"render",       no_argument,       NULL, OPT_RENDER},
    {"vertex",       required_argument, NULL, OPT_VERTEX},
    {"fragment",     required_argument, NULL, OPT_FRAGMENT},
    {"color-format", required_argument, NULL, OPT_COLOR_FORMAT},
    {NULL, 0, NULL, 0}
};

// Pick a function of a given type from the library, optionally by name.
static id<MTLFunction> pickFunction(id<MTLLibrary> lib, const char *wantName,
                                    MTLFunctionType wantType, const char *label) {
    if (wantName) {
        id<MTLFunction> fn = [lib newFunctionWithName:[NSString stringWithUTF8String:wantName]];
        if (!fn) die("named function not found", nil);
        return fn;
    }
    for (NSString *n in [lib functionNames]) {
        id<MTLFunction> cand = [lib newFunctionWithName:n];
        if (cand && [cand functionType] == wantType) return cand;
    }
    fprintf(stderr, "shdump: no %s function found\n", label);
    exit(EXIT_FAILURE);
}

int main(int argc, char *argv[]) {
    @autoreleasepool {
        const char *output = NULL;
        const char *want_fn = NULL;       // compute kernel name
        const char *want_vert = NULL;     // vertex fn name (render)
        const char *want_frag = NULL;     // fragment fn name (render)
        BOOL fastMath = YES;
        BOOL renderMode = NO;
        NSUInteger colorFormat = MTLPixelFormatBGRA8Unorm;  // 80
        int c;
        while ((c = getopt_long(argc, argv, "o:f:", longOpts, NULL)) > 0) {
            switch (c) {
                case 'o': output = optarg; break;
                case 'f': want_fn = optarg; break;
                case OPT_NO_FAST_MATH:   fastMath = NO; break;
                case OPT_RENDER:         renderMode = YES; break;
                case OPT_VERTEX:         want_vert = optarg; break;
                case OPT_FRAGMENT:       want_frag = optarg; break;
                case OPT_COLOR_FORMAT:   colorFormat = (NSUInteger)strtoul(optarg, NULL, 0); break;
                default:
                    fprintf(stderr, "usage: %s -o out.bin [--render [--vertex v] [--fragment f]] "
                                    "[-f fn] [--no-fast-math] src.metal\n", argv[0]);
                    return EXIT_FAILURE;
            }
        }
        if (!output || optind >= argc) {
            fprintf(stderr, "usage: %s -o out.bin [--render [--vertex v] [--fragment f]] "
                            "[-f fn] [--no-fast-math] src.metal\n", argv[0]);
            return EXIT_FAILURE;
        }

        // Read MSL source (ours).
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
        fprintf(stderr, "shdump: device = %s\n", [[dev name] UTF8String]);

        // Runtime-compile OUR source.
        MTLCompileOptions *opts = [MTLCompileOptions new];
        [opts setFastMathEnabled:fastMath];
        id<MTLLibrary> lib = [dev newLibraryWithSource:src options:opts error:&err];
        if (!lib) die("compile failed", err);

        fprintf(stderr, "shdump: functions =");
        for (NSString *n in [lib functionNames]) fprintf(stderr, " %s", [n UTF8String]);
        fprintf(stderr, "\n");

        // Build a binary archive and add the pipeline's functions to it.
        MTLBinaryArchiveDescriptor *adesc = [MTLBinaryArchiveDescriptor new];
        id<MTLBinaryArchive> arc = [dev newBinaryArchiveWithDescriptor:adesc error:&err];
        if (!arc) die("binary archive creation failed", err);

        if (renderMode) {
            // ---- RENDER PIPELINE (vertex + fragment), EXP-0008 --------------
            id<MTLFunction> vfn = pickFunction(lib, want_vert, MTLFunctionTypeVertex, "vertex");
            id<MTLFunction> ffn = pickFunction(lib, want_frag, MTLFunctionTypeFragment, "fragment");
            fprintf(stderr, "shdump: vertex = %s  fragment = %s\n",
                    [[vfn name] UTF8String], [[ffn name] UTF8String]);

            MTLRenderPipelineDescriptor *rdesc = [MTLRenderPipelineDescriptor new];
            [rdesc setVertexFunction:vfn];
            [rdesc setFragmentFunction:ffn];
            rdesc.colorAttachments[0].pixelFormat = (MTLPixelFormat)colorFormat;

            // Validate it compiles to a real device render pipeline.
            id<MTLRenderPipelineState> pso =
                [dev newRenderPipelineStateWithDescriptor:rdesc error:&err];
            if (!pso) die("render pipeline creation failed", err);
            fprintf(stderr, "shdump: render pipeline OK (colorFormat=%lu)\n",
                    (unsigned long)colorFormat);

            if (![arc addRenderPipelineFunctionsWithDescriptor:rdesc error:&err])
                die("addRenderPipelineFunctions failed", err);
        } else {
            // ---- COMPUTE PIPELINE (default) ---------------------------------
            id<MTLFunction> fn = pickFunction(lib, want_fn, MTLFunctionTypeKernel, "kernel");
            fprintf(stderr, "shdump: chosen function = %s\n", [[fn name] UTF8String]);

            id<MTLComputePipelineState> pso =
                [dev newComputePipelineStateWithFunction:fn error:&err];
            if (!pso) die("compute pipeline creation failed", err);
            fprintf(stderr, "shdump: threadExecutionWidth = %lu, maxThreadsPerThreadgroup = %lu\n",
                    (unsigned long)[pso threadExecutionWidth],
                    (unsigned long)[pso maxTotalThreadsPerThreadgroup]);

            MTLComputePipelineDescriptor *cdesc = [MTLComputePipelineDescriptor new];
            [cdesc setComputeFunction:fn];
            if (![arc addComputePipelineFunctionsWithDescriptor:cdesc error:&err])
                die("addComputePipelineFunctions failed", err);
        }

        NSURL *url = [NSURL fileURLWithPath:[NSString stringWithUTF8String:output]];
        if (![arc serializeToURL:url error:&err]) die("serializeToURL failed", err);

        fprintf(stderr, "shdump: wrote %s\n", output);
        return 0;
    }
}
