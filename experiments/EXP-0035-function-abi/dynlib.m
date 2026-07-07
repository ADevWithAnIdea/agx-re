// dynlib.m — EXP-0035 part 3: MTLDynamicLibrary probe (A18 Pro / G17P).
// CLEAN-ROOM: PUBLIC Metal API on OUR OWN MSL. Reports whether a dynamic-library
// symbol reference produces a userspace-visible artifact (a serialized container
// with AGX code) or is loader/kernel-managed, and how a consumer that calls into
// it is compiled. Only our own compiled bytes are inspected (out-of-band).
//
// Build: clang -fobjc-arc -framework Metal -framework Foundation -o dynlib dynlib.m
// Usage: ./dynlib <dylib.metal> <consumer.metal> <dylibExternalFnName> <consumerKernel> <out_consumer.bin>
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>

static void die(const char*m, NSError*e){ fprintf(stderr,"dynlib: %s%s%s\n",m,e?": ":"",e?[[e localizedDescription] UTF8String]:""); exit(1);}
static NSString* rd(const char*p){ NSError*e=nil; NSString*s=[NSString stringWithContentsOfFile:[NSString stringWithUTF8String:p] encoding:NSUTF8StringEncoding error:&e]; if(!s) die("read",e); return s;}

int main(int argc, char**argv){
  @autoreleasepool{
    if(argc<6) die("usage: dylib.metal consumer.metal <unused> consumerKernel out.bin",nil);
    NSString *dylibSrc=rd(argv[1]), *consumerSrc=rd(argv[2]);
    const char *consumerKernel=argv[4], *outbin=argv[5];

    id<MTLDevice> dev=MTLCreateSystemDefaultDevice(); if(!dev) die("no device",nil);
    fprintf(stderr,"dynlib: device=%s\n",[[dev name] UTF8String]);
    NSError*err=nil;
    NSString *dlpath = [[[NSFileManager defaultManager] currentDirectoryPath]
                        stringByAppendingPathComponent:@"dylib.metallib"];
    MTLCompileOptions*o=[MTLCompileOptions new];
    o.libraryType = MTLLibraryTypeDynamic;   // <-- request a DYNAMIC library
    o.installName = dlpath;                   // loader resolves the dylib by this path

    // 1. Compile the dynamic library from our source.
    id<MTLLibrary> dylibLib=[dev newLibraryWithSource:dylibSrc options:o error:&err];
    if(!dylibLib) die("dylib compile failed",err);
    fprintf(stderr,"dynlib: dylib functions =");
    for(NSString*n in [dylibLib functionNames]) fprintf(stderr," %s",[n UTF8String]);
    fprintf(stderr,"\n");

    // 2. Wrap it as an MTLDynamicLibrary and SERIALIZE (the userspace artifact).
    id<MTLDynamicLibrary> dl=[dev newDynamicLibrary:dylibLib error:&err];
    if(!dl){ fprintf(stderr,"dynlib: newDynamicLibrary FAILED: %s\n", err?[[err localizedDescription] UTF8String]:"?"); }
    else {
      fprintf(stderr,"dynlib: MTLDynamicLibrary OK  installName=%s\n",
              [dl installName]?[[dl installName] UTF8String]:"(nil)");
      NSURL*u=[NSURL fileURLWithPath:dlpath];
      if([dl serializeToURL:u error:&err]) fprintf(stderr,"dynlib: serialized dynamic library -> %s\n",[dlpath UTF8String]);
      else fprintf(stderr,"dynlib: serialize failed: %s\n", err?[[err localizedDescription] UTF8String]:"?");
      // Reload it from the serialized URL so the loader resolves it by installName.
      id<MTLDynamicLibrary> dl2=[dev newDynamicLibraryWithURL:u error:&err];
      if(dl2){ dl=dl2; fprintf(stderr,"dynlib: reloaded dynamic library from URL (installName=%s)\n",[[dl installName] UTF8String]); }
      else fprintf(stderr,"dynlib: newDynamicLibraryWithURL failed: %s\n", err?[[err localizedDescription] UTF8String]:"?");
    }

    // 3. Compile a CONSUMER that links against the dynamic library.
    MTLCompileOptions*co=[MTLCompileOptions new];
    co.libraryType = MTLLibraryTypeExecutable;
    if(dl) co.libraries = @[dl];       // link the consumer against our dynamic library
    id<MTLLibrary> consumer=[dev newLibraryWithSource:consumerSrc options:co error:&err];
    if(!consumer){ fprintf(stderr,"dynlib: consumer compile FAILED: %s\n", err?[[err localizedDescription] UTF8String]:"?"); return 2; }
    fprintf(stderr,"dynlib: consumer functions =");
    for(NSString*n in [consumer functionNames]) fprintf(stderr," %s",[n UTF8String]);
    fprintf(stderr,"\n");

    // 4. Build a pipeline for the consumer kernel; preload the dynamic library.
    id<MTLFunction> kfn=[consumer newFunctionWithName:[NSString stringWithUTF8String:consumerKernel]];
    if(!kfn) die("consumer kernel not found",nil);
    MTLComputePipelineDescriptor*cd=[MTLComputePipelineDescriptor new];
    cd.computeFunction=kfn;
    if(dl) cd.preloadedLibraries=@[dl];
    id<MTLComputePipelineState> pso=[dev newComputePipelineStateWithDescriptor:cd options:MTLPipelineOptionNone reflection:nil error:&err];
    if(!pso){ fprintf(stderr,"dynlib: consumer pipeline FAILED: %s\n", err?[[err localizedDescription] UTF8String]:"?"); return 3; }
    fprintf(stderr,"dynlib: consumer pipeline OK\n");

    // 5. Serialize the consumer archive for out-of-band code extraction.
    MTLBinaryArchiveDescriptor*ad=[MTLBinaryArchiveDescriptor new];
    id<MTLBinaryArchive> arc=[dev newBinaryArchiveWithDescriptor:ad error:&err];
    if(![arc addComputePipelineFunctionsWithDescriptor:cd error:&err]) die("addComputePipeline",err);
    NSURL*ou=[NSURL fileURLWithPath:[NSString stringWithUTF8String:outbin]];
    if(![arc serializeToURL:ou error:&err]) die("serialize consumer",err);
    fprintf(stderr,"dynlib: wrote consumer archive %s\n",outbin);
    return 0;
  }
}
