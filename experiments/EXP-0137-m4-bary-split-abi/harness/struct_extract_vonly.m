// struct_extract_vonly.m -- EXP-0129 structural (compile+serialize) probe
// for a rasterizationEnabled=NO, VERTEX-ONLY (void-returning) render
// pipeline (OWN-SHADER + PUBLIC). MTLRenderPipelineDescriptor requires a
// vertex function only; no fragment function, no color/depth/stencil
// attachment formats. Used for kernels/split_prolog.metal's v_split_prolog
// (H2's genuinely-called fetch "prolog").
//
// Build: clang -fobjc-arc -framework Metal -framework Foundation \
//          -o struct_extract_vonly struct_extract_vonly.m
// Usage: struct_extract_vonly -o out.bin --source S.metal --vertex V

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <getopt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if !__has_feature(objc_arc)
#error compile with -fobjc-arc
#endif

static void usageDie(const char *m) { fprintf(stderr, "struct_extract_vonly: %s\n", m); exit(1); }

enum { O_SRC = 128, O_VTX };
static const struct option L[] = {
    {"source", required_argument, 0, O_SRC},
    {"vertex", required_argument, 0, O_VTX},
    {0,0,0,0}
};

int main(int argc, char **argv) { @autoreleasepool {
    const char *out = 0, *srcp = 0, *vn = 0;
    int c;
    while ((c = getopt_long(argc, argv, "o:", L, 0)) > 0) {
        switch (c) {
            case 'o': out = optarg; break;
            case O_SRC: srcp = optarg; break;
            case O_VTX: vn = optarg; break;
        }
    }
    if (!out || !srcp || !vn) usageDie("need -o, --source, --vertex");

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
    if (!vf) { printf("FAIL: function missing (vertex=%s present=%d)\n", vn, vf != nil); return 2; }

    MTLRenderPipelineDescriptor *rd = [MTLRenderPipelineDescriptor new];
    rd.vertexFunction = vf;
    rd.rasterizationEnabled = NO;

    id<MTLRenderPipelineState> pso = [dev newRenderPipelineStateWithDescriptor:rd error:&err];
    if (!pso) { printf("FAIL: pipeline: %s\n", [[err localizedDescription] UTF8String]); return 2; }
    fprintf(stderr, "struct_extract_vonly: pipeline OK vertex=%s\n", vn);

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
