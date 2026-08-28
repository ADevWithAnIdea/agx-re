#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
int main(int argc, char *argv[]) {
    @autoreleasepool {
        if (argc < 2) { fprintf(stderr, "usage: trycompile <path.metal>\n"); return 2; }
        NSError *err = nil;
        NSString *src = [NSString stringWithContentsOfFile:[NSString stringWithUTF8String:argv[1]] encoding:NSUTF8StringEncoding error:&err];
        if (!src) { NSLog(@"READ FAIL: %@", err); return 2; }
        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        MTLCompileOptions *opts = [MTLCompileOptions new];
        id<MTLLibrary> lib = [dev newLibraryWithSource:src options:opts error:&err];
        if (!lib) { NSLog(@"COMPILE FAIL: %@", err); return 1; }
        NSLog(@"COMPILE OK, functions: %@", [lib functionNames]);
        return 0;
    }
}
