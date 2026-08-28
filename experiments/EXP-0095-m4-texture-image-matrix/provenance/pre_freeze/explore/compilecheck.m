// Exploratory (NOT frozen evidence) compile-checker used only to shape the
// PRE_REGISTRATION.md matrix. Compiles a given .metal source and reports,
// per kernel/function name found via regex over the source text, whether a
// MTLComputePipelineState could be created for it. Public Metal API only.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <stdio.h>

int main(int argc, const char **argv) {
  @autoreleasepool {
    if (argc < 2) { fprintf(stderr, "usage: compilecheck <file.metal> [fnprefix]\n"); return 2; }
    NSError *e = nil;
    NSString *src = [NSString stringWithContentsOfFile:@(argv[1]) encoding:NSUTF8StringEncoding error:&e];
    if (!src) { printf("SOURCE_READ_FAIL %s\n", e.localizedDescription.UTF8String); return 3; }
    id<MTLDevice> d = MTLCreateSystemDefaultDevice();
    if (!d) { printf("NO_DEVICE\n"); return 3; }
    MTLCompileOptions *opt = [MTLCompileOptions new];
    id<MTLLibrary> lib = [d newLibraryWithSource:src options:opt error:&e];
    if (!lib) { printf("LIBRARY_FAIL %s\n", e.localizedDescription.UTF8String); return 0; }
    printf("LIBRARY_OK\n");
    for (NSString *name in lib.functionNames) {
      id<MTLFunction> f = [lib newFunctionWithName:name];
      NSError *pe = nil;
      id<MTLComputePipelineState> p = [d newComputePipelineStateWithFunction:f error:&pe];
      printf("FN %s %s %s\n", name.UTF8String, p ? "OK" : "FAIL", pe ? pe.localizedDescription.UTF8String : "");
    }
    return 0;
  }
}
