#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
int main(int argc, char**argv){
  @autoreleasepool {
    id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
    NSError *err=nil;
    NSString *path = [NSString stringWithUTF8String:argv[1]];
    NSString *src = [NSString stringWithContentsOfFile:path encoding:NSUTF8StringEncoding error:&err];
    if(!src){ printf("READFAIL\n"); return 2; }
    id<MTLLibrary> lib = [dev newLibraryWithSource:src options:nil error:&err];
    if(!lib){ printf("COMPILEFAIL %s\n", err.localizedDescription.UTF8String); return 3; }
    printf("OK functions=%lu\n", (unsigned long)lib.functionNames.count);
    for (NSString *n in lib.functionNames) printf(" fn=%s\n", n.UTF8String);
    return 0;
  }
}
