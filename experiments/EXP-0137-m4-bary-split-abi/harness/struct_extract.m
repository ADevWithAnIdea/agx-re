// struct_extract.m -- EXP-0129 generic structural (compile+serialize) probe
// (OWN-SHADER + PUBLIC). Compiles OUR OWN MSL, builds a render pipeline with
// 1-3 configurable color-attachment formats, validates it on the real
// device, and serializes the archive so agxparse.py (read-only, unmodified)
// extracts the vertex/fragment-stage AGX bytes. A pipeline-creation FAILURE
// is itself a result: printed verbatim, exit 2, distinguishable from a
// usage error (exit 1). Adapted from EXP-0117's harness/struct_extract.m
// (our own prior authored code in this project), generalized to N
// attachments for the barycentric output-count matrix.
//
// Build: clang -fobjc-arc -framework Metal -framework Foundation \
//          -o struct_extract struct_extract.m
// Usage: struct_extract -o out.bin --source S.metal --vertex V --fragment F
//   [--natt N] [--fmt0 N] [--fmt1 N] [--fmt2 N]

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <getopt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if !__has_feature(objc_arc)
#error compile with -fobjc-arc
#endif

static void usageDie(const char *m) {
    fprintf(stderr, "struct_extract: %s\n", m);
    exit(1);
}

enum { O_SRC = 128, O_VTX, O_FRAG, O_NATT, O_FMT0, O_FMT1, O_FMT2 };
static const struct option L[] = {
    {"source",   required_argument, 0, O_SRC},
    {"vertex",   required_argument, 0, O_VTX},
    {"fragment", required_argument, 0, O_FRAG},
    {"natt",     required_argument, 0, O_NATT},
    {"fmt0",     required_argument, 0, O_FMT0},
    {"fmt1",     required_argument, 0, O_FMT1},
    {"fmt2",     required_argument, 0, O_FMT2},
    {0,0,0,0}
};

int main(int argc, char **argv) { @autoreleasepool {
    const char *out = 0, *srcp = 0, *vn = 0, *fn = 0;
    int natt = 1;
    unsigned long fmt[3] = {125 /*RGBA32Float*/, 125, 125};
    int c;
    while ((c = getopt_long(argc, argv, "o:", L, 0)) > 0) {
        switch (c) {
            case 'o': out = optarg; break;
            case O_SRC: srcp = optarg; break;
            case O_VTX: vn = optarg; break;
            case O_FRAG: fn = optarg; break;
            case O_NATT: natt = atoi(optarg); break;
            case O_FMT0: fmt[0] = strtoul(optarg, 0, 0); break;
            case O_FMT1: fmt[1] = strtoul(optarg, 0, 0); break;
            case O_FMT2: fmt[2] = strtoul(optarg, 0, 0); break;
        }
    }
    if (!out || !srcp || !vn || !fn) usageDie("need -o, --source, --vertex, --fragment");
    if (natt < 1 || natt > 3) usageDie("natt must be 1..3");

    NSError *err = nil;
    id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
    if (!dev) usageDie("no device");
    NSString *src = [NSString stringWithContentsOfFile:[NSString stringWithUTF8String:srcp]
                                               encoding:NSUTF8StringEncoding error:&err];
    if (!src) usageDie("read src");

    MTLCompileOptions *co = [MTLCompileOptions new];
    id<MTLLibrary> lib = [dev newLibraryWithSource:src options:co error:&err];
    if (!lib) { printf("FAIL: compile: %s\n", [[err localizedDescription] UTF8String]); return 2; }
    id<MTLFunction> vf = [lib newFunctionWithName:[NSString stringWithUTF8String:vn]];
    id<MTLFunction> ff = [lib newFunctionWithName:[NSString stringWithUTF8String:fn]];
    if (!vf || !ff) {
        printf("FAIL: function missing (vertex=%s present=%d, fragment=%s present=%d)\n",
               vn, vf != nil, fn, ff != nil);
        return 2;
    }

    MTLRenderPipelineDescriptor *rd = [MTLRenderPipelineDescriptor new];
    rd.vertexFunction = vf;
    rd.fragmentFunction = ff;
    for (int i = 0; i < natt; i++) {
        rd.colorAttachments[i].pixelFormat = (MTLPixelFormat)fmt[i];
    }

    id<MTLRenderPipelineState> pso = [dev newRenderPipelineStateWithDescriptor:rd error:&err];
    if (!pso) { printf("FAIL: pipeline: %s\n", [[err localizedDescription] UTF8String]); return 2; }
    fprintf(stderr, "struct_extract: pipeline OK vertex=%s fragment=%s natt=%d\n", vn, fn, natt);

    MTLBinaryArchiveDescriptor *ad = [MTLBinaryArchiveDescriptor new];
    id<MTLBinaryArchive> arc = [dev newBinaryArchiveWithDescriptor:ad error:&err];
    if (!arc) usageDie("archive creation failed");
    if (![arc addRenderPipelineFunctionsWithDescriptor:rd error:&err]) {
        printf("FAIL: addRenderPipelineFunctions: %s\n", [[err localizedDescription] UTF8String]);
        return 2;
    }
    if (![arc serializeToURL:[NSURL fileURLWithPath:[NSString stringWithUTF8String:out]] error:&err])
        usageDie("serialize failed");
    printf("OK\n");
    return 0;
}}
