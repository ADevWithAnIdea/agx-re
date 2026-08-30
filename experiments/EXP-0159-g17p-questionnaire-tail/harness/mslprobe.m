// mslprobe.m — EXP-0159. Authored by the clean-room RE team.
// Compiles an authored MSL source file through the PUBLIC runtime API
// (newLibraryWithSource:) and prints, verbatim, whether it succeeded and the
// full compiler diagnostic if it did not. It also dumps a set of public
// MTLDevice capability properties.
//
// Clean-room: PUBLIC API + OWN-SHADER only. No Apple binary is inspected.
// Build: clang -fobjc-arc -framework Metal -framework Foundation -o mslprobe mslprobe.m
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>

static void devinfo(id<MTLDevice> dev) {
    printf("DEV_NAME %s\n", [[dev name] UTF8String]);
    printf("DEV_REGISTRY_ID %llu\n", (unsigned long long)[dev registryID]);
    printf("DEV_ARGBUF_TIER %ld\n", (long)[dev argumentBuffersSupport]);
    printf("DEV_MAX_ARGBUF_SAMPLERS %lu\n", (unsigned long)[dev maxArgumentBufferSamplerCount]);
    printf("DEV_MAX_BUFLEN %llu\n", (unsigned long long)[dev maxBufferLength]);
    printf("DEV_MAX_TG_MEM %lu\n", (unsigned long)[dev maxThreadgroupMemoryLength]);
    printf("DEV_RECOMMENDED_WS %llu\n", (unsigned long long)[dev recommendedMaxWorkingSetSize]);
    for (int f = 1001; f <= 1010; f++) { // MTLGPUFamilyApple1..Apple10 = 1001..1010
        if ([dev supportsFamily:(MTLGPUFamily)f]) printf("DEV_FAMILY_APPLE %d\n", f - 1000);
    }
    printf("DEV_RT %d\n", (int)[dev supportsRaytracing]);
}

int main(int argc, char **argv) {
  @autoreleasepool {
    id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
    if (!dev) { printf("STATUS no_device\n"); return 2; }
    if (argc < 2) { devinfo(dev); printf("STATUS devinfo_only\n"); return 0; }
    devinfo(dev);
    NSError *err = nil;
    NSString *src = [NSString stringWithContentsOfFile:[NSString stringWithUTF8String:argv[1]]
                                              encoding:NSUTF8StringEncoding error:&err];
    if (!src) { printf("STATUS source_read_failed %s\n", [[err description] UTF8String]); return 2; }
    MTLCompileOptions *opt = [MTLCompileOptions new];
    // Optional 3rd arg: language version selector ("31" -> 3.1, "32" -> 3.2, "40" -> 4.0)
    if (argc >= 3) {
        int lv = atoi(argv[2]);
        if (lv == 31) opt.languageVersion = MTLLanguageVersion3_1;
        else if (lv == 32) opt.languageVersion = MTLLanguageVersion3_2;
    }
    err = nil;
    id<MTLLibrary> lib = [dev newLibraryWithSource:src options:opt error:&err];
    if (!lib) {
        printf("COMPILE_STATUS reject\n");
        printf("DIAG_BEGIN\n%s\nDIAG_END\n", [[err description] UTF8String]);
        printf("STATUS ok\n");
        return 0;
    }
    printf("COMPILE_STATUS accept\n");
    if (err) printf("DIAG_BEGIN\n%s\nDIAG_END\n", [[err description] UTF8String]);
    for (NSString *fn in [lib functionNames]) printf("FUNCTION %s\n", [fn UTF8String]);
    printf("STATUS ok\n");
    return 0;
  }
}
