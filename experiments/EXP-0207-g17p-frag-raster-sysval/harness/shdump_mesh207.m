// shdump_mesh207.m -- EXP-0207 copy of our own EXP-0187 pinned/shdump_mesh.m
// (originally EXP-0135), with --color-format added so the mesh binary archive
// key matches what harness/meshsweep207.m renders with.
// EXP-0135 shdump_mesh.m — OWN-SHADER compile+serialize for a mesh pipeline
// (M4 re-run of EXP-0030's harness/shdump_mesh.m, extended with --define for
// the same NV/NP/PAYLOAD_BYTES/AMP_COUNT macros mesh_probe.m uses, so Group R
// byte-extraction targets the exact same baseline configuration Groups B-D
// sweep from). Builds an MTLMeshRenderPipelineDescriptor, validates it
// compiles to a real device mesh pipeline, and serializes it into an
// MTLBinaryArchive container so our own parser (agxparse.py) can isolate the
// raw AGX bytes of each stage.
//
// Clean-room: public Metal API on OUR OWN source only.
//
// Build: clang -fobjc-arc -framework Metal -framework Foundation -o shdump_mesh shdump_mesh.m
// Usage: shdump_mesh -o out.bin --object O --mesh M --fragment F
//                     [--define K=V ...] [--no-object] src.metal
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
    if (err) fprintf(stderr, "shdump_mesh: %s: %s\n", msg, [[err localizedDescription] UTF8String]);
    else     fprintf(stderr, "shdump_mesh: %s\n", msg);
    exit(EXIT_FAILURE);
}

int main(int argc, char *argv[]) {
    @autoreleasepool {
        const char *output = NULL, *oName = "obj_main", *mName = "mesh_main", *fName = "frag_main";
        int noObject = 0;
        NSUInteger colorFormat = MTLPixelFormatRGBA32Float;   // EXP-0207
        NSMutableDictionary *macros = [NSMutableDictionary dictionary];
        static struct option longOpts[] = {
            {"output", required_argument, 0, 'o'}, {"object", required_argument, 0, 1},
            {"mesh", required_argument, 0, 2}, {"fragment", required_argument, 0, 3},
            {"define", required_argument, 0, 4}, {"no-object", no_argument, 0, 5},
            {"color-format", required_argument, 0, 6},
            {0, 0, 0, 0}
        };
        int c;
        while ((c = getopt_long(argc, argv, "o:", longOpts, NULL)) != -1) {
            switch (c) {
                case 'o': output = optarg; break;
                case 1: oName = optarg; break;
                case 2: mName = optarg; break;
                case 3: fName = optarg; break;
                case 4: {
                    char *eq = strchr(optarg, '=');
                    if (eq) {
                        NSString *k = [[NSString alloc] initWithBytes:optarg length:(eq - optarg) encoding:NSUTF8StringEncoding];
                        macros[k] = [NSString stringWithUTF8String:eq + 1];
                    }
                    break;
                }
                case 5: noObject = 1; break;
                case 6: colorFormat = (NSUInteger)strtoul(optarg, NULL, 0); break;
                default:
                    fprintf(stderr, "usage: %s -o out.bin [--define K=V]... src.metal\n", argv[0]);
                    return 1;
            }
        }
        if (!output || optind >= argc) { fprintf(stderr, "usage: %s -o out.bin src.metal\n", argv[0]); return 1; }

        NSError *err = nil;
        NSString *src = [NSString stringWithContentsOfFile:[NSString stringWithUTF8String:argv[optind]]
                                                    encoding:NSUTF8StringEncoding error:&err];
        if (!src) die("read source", err);

        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        if (!dev) die("no Metal device", nil);
        fprintf(stderr, "shdump_mesh: device = %s\n", [[dev name] UTF8String]);

        MTLCompileOptions *opts = [MTLCompileOptions new];
        if (macros.count) [opts setPreprocessorMacros:macros];
        id<MTLLibrary> lib = [dev newLibraryWithSource:src options:opts error:&err];
        if (!lib) die("compile failed", err);

        id<MTLFunction> ofn = noObject ? nil : [lib newFunctionWithName:[NSString stringWithUTF8String:oName]];
        id<MTLFunction> mfn = [lib newFunctionWithName:[NSString stringWithUTF8String:mName]];
        id<MTLFunction> ffn = [lib newFunctionWithName:[NSString stringWithUTF8String:fName]];
        if ((!noObject && !ofn) || !mfn || !ffn) die("function(s) not found", nil);

        MTLMeshRenderPipelineDescriptor *md = [MTLMeshRenderPipelineDescriptor new];
        md.objectFunction = ofn;
        md.meshFunction = mfn;
        md.fragmentFunction = ffn;
        md.colorAttachments[0].pixelFormat = (MTLPixelFormat)colorFormat;

        id<MTLRenderPipelineState> pso =
            [dev newRenderPipelineStateWithMeshDescriptor:md options:MTLPipelineOptionNone reflection:nil error:&err];
        if (!pso) die("mesh pipeline creation failed", err);
        fprintf(stderr, "shdump_mesh: mesh pipeline OK\n");

        MTLBinaryArchiveDescriptor *adesc = [MTLBinaryArchiveDescriptor new];
        id<MTLBinaryArchive> arc = [dev newBinaryArchiveWithDescriptor:adesc error:&err];
        if (!arc) die("binary archive creation failed", err);
        if (![arc addMeshRenderPipelineFunctionsWithDescriptor:md error:&err])
            die("addMeshRenderPipelineFunctions failed", err);

        NSURL *url = [NSURL fileURLWithPath:[NSString stringWithUTF8String:output]];
        if (![arc serializeToURL:url error:&err]) die("serializeToURL failed", err);
        fprintf(stderr, "shdump_mesh: wrote %s\n", output);
        return 0;
    }
}
