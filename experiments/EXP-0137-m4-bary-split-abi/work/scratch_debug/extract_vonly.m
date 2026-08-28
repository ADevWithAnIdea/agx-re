#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
int main(int argc, char **argv) { @autoreleasepool {
    NSError *err=nil;
    id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
    NSString *src = [NSString stringWithContentsOfFile:[NSString stringWithUTF8String:argv[1]] encoding:NSUTF8StringEncoding error:&err];
    id<MTLLibrary> lib = [dev newLibraryWithSource:src options:[MTLCompileOptions new] error:&err];
    if (!lib) { printf("compile FAIL: %s\n", [[err localizedDescription] UTF8String]); return 1; }
    id<MTLFunction> vf = [lib newFunctionWithName:[NSString stringWithUTF8String:argv[2]]];
    MTLRenderPipelineDescriptor *rd = [MTLRenderPipelineDescriptor new];
    rd.vertexFunction = vf;
    rd.rasterizationEnabled = NO;
    id<MTLRenderPipelineState> pso = [dev newRenderPipelineStateWithDescriptor:rd error:&err];
    if (!pso) { printf("pipeline FAIL: %s\n", [[err localizedDescription] UTF8String]); return 1; }
    MTLBinaryArchiveDescriptor *ad = [MTLBinaryArchiveDescriptor new];
    id<MTLBinaryArchive> arc = [dev newBinaryArchiveWithDescriptor:ad error:&err];
    if (![arc addRenderPipelineFunctionsWithDescriptor:rd error:&err]) { printf("addfns FAIL: %s\n", [[err localizedDescription] UTF8String]); return 1; }
    if (![arc serializeToURL:[NSURL fileURLWithPath:[NSString stringWithUTF8String:argv[3]]] error:&err]) { printf("serialize FAIL\n"); return 1; }
    printf("OK\n");
    return 0;
}}
