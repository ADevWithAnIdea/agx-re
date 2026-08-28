// struct_extract.m — EXP-0117 generic structural (compile+serialize) probe
// (OWN-SHADER + PUBLIC). Compiles OUR OWN MSL, builds a render pipeline
// with a fully configurable color-attachment-0 blend/format descriptor
// (blend factors/op/mask/enable, pixel format), validates it on the real
// device, and serializes the archive so agxparse.py (read-only, unmodified)
// extracts the fragment-stage AGX bytes. A pipeline-creation FAILURE (e.g.
// enabling blending on an integer pixel format) is itself a result: printed
// verbatim, exit 2, distinguishable from a usage error (exit 1).
//
// Adapted from EXP-0109's harness/mrt_extract.m pattern (our own prior
// authored code in this project), generalized to expose the blend
// descriptor fields on the CLI instead of hardcoding them.
//
// Build: clang -fobjc-arc -framework Metal -framework Foundation \
//          -o struct_extract struct_extract.m
// Usage: struct_extract -o out.bin --source S.metal --vertex V --fragment F
//   [--colorformat N] [--blendenabled 0|1]
//   [--sr N] [--dr N] [--sa N] [--da N] [--rgbop N] [--aop N] [--mask N]

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

enum { O_SRC = 128, O_VTX, O_FRAG, O_CFMT, O_BLEND, O_SR, O_DR, O_SA, O_DA, O_RGBOP, O_AOP, O_MASK, O_DFMT, O_SFMT };
static const struct option L[] = {
    {"source",       required_argument, 0, O_SRC},
    {"vertex",       required_argument, 0, O_VTX},
    {"fragment",     required_argument, 0, O_FRAG},
    {"colorformat",  required_argument, 0, O_CFMT},
    {"blendenabled", required_argument, 0, O_BLEND},
    {"sr", required_argument, 0, O_SR}, {"dr", required_argument, 0, O_DR},
    {"sa", required_argument, 0, O_SA}, {"da", required_argument, 0, O_DA},
    {"rgbop", required_argument, 0, O_RGBOP}, {"aop", required_argument, 0, O_AOP},
    {"mask", required_argument, 0, O_MASK},
    {"depthformat", required_argument, 0, O_DFMT}, {"stencilformat", required_argument, 0, O_SFMT},
    {0,0,0,0}
};

int main(int argc, char **argv) { @autoreleasepool {
    const char *out = 0, *srcp = 0, *vn = 0, *fn = 0;
    unsigned long cfmt = 125 /*RGBA32Float*/;
    int blendEnabled = 0;
    unsigned long sr = 1 /*One*/, dr = 0 /*Zero*/, sa = 1, da = 0, rgbop = 0 /*Add*/, aop = 0, mask = 0xf;
    unsigned long dfmt = 0, sfmt = 0;
    int c;
    while ((c = getopt_long(argc, argv, "o:", L, 0)) > 0) {
        switch (c) {
            case 'o': out = optarg; break;
            case O_SRC: srcp = optarg; break;
            case O_VTX: vn = optarg; break;
            case O_FRAG: fn = optarg; break;
            case O_CFMT: cfmt = strtoul(optarg, 0, 0); break;
            case O_BLEND: blendEnabled = atoi(optarg); break;
            case O_SR: sr = strtoul(optarg, 0, 0); break;
            case O_DR: dr = strtoul(optarg, 0, 0); break;
            case O_SA: sa = strtoul(optarg, 0, 0); break;
            case O_DA: da = strtoul(optarg, 0, 0); break;
            case O_RGBOP: rgbop = strtoul(optarg, 0, 0); break;
            case O_AOP: aop = strtoul(optarg, 0, 0); break;
            case O_MASK: mask = strtoul(optarg, 0, 0); break;
            case O_DFMT: dfmt = strtoul(optarg, 0, 0); break;
            case O_SFMT: sfmt = strtoul(optarg, 0, 0); break;
        }
    }
    if (!out || !srcp || !vn || !fn) usageDie("need -o, --source, --vertex, --fragment");

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
    rd.colorAttachments[0].pixelFormat = (MTLPixelFormat)cfmt;
    rd.colorAttachments[0].blendingEnabled = blendEnabled ? YES : NO;
    rd.colorAttachments[0].sourceRGBBlendFactor = (MTLBlendFactor)sr;
    rd.colorAttachments[0].destinationRGBBlendFactor = (MTLBlendFactor)dr;
    rd.colorAttachments[0].sourceAlphaBlendFactor = (MTLBlendFactor)sa;
    rd.colorAttachments[0].destinationAlphaBlendFactor = (MTLBlendFactor)da;
    rd.colorAttachments[0].rgbBlendOperation = (MTLBlendOperation)rgbop;
    rd.colorAttachments[0].alphaBlendOperation = (MTLBlendOperation)aop;
    rd.colorAttachments[0].writeMask = (MTLColorWriteMask)mask;
    if (dfmt != 0) rd.depthAttachmentPixelFormat = (MTLPixelFormat)dfmt;
    if (sfmt != 0) rd.stencilAttachmentPixelFormat = (MTLPixelFormat)sfmt;

    id<MTLRenderPipelineState> pso = [dev newRenderPipelineStateWithDescriptor:rd error:&err];
    if (!pso) { printf("FAIL: pipeline: %s\n", [[err localizedDescription] UTF8String]); return 2; }
    fprintf(stderr, "struct_extract: pipeline OK vertex=%s fragment=%s colorformat=%lu blend=%d\n",
            vn, fn, cfmt, blendEnabled);

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
