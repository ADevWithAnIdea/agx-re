// shdump_tile.m — clean-room OWN-SHADER tile-render-pipeline compile+serialize.
// Compiles OUR OWN MSL, builds a MTLTileRenderPipelineState (imageblock/tile
// kernel), and serializes the device-compiled pipeline into an MTLBinaryArchive.
// Parsed out-of-band by agxparse.py. Only public Metal API on OUR OWN source; no
// Apple binary disassembled. EXP-O2D.
//   clang -fobjc-arc -framework Metal -framework Foundation -o shdump_tile shdump_tile.m
//   ./shdump_tile -o out.bin -f tk_write [--fmt0 N --fmt1 N --fmt2 N] src.metal
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <getopt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void die(const char *m, NSError *e){ fprintf(stderr,"shdump_tile: %s%s%s\n",m,e?": ":"",e?[[e localizedDescription] UTF8String]:""); exit(1); }

enum { OPT_F0=200, OPT_F1, OPT_F2, OPT_NCA };
static const struct option L[] = {
    {"output",required_argument,0,'o'},{"function",required_argument,0,'f'},
    {"fmt0",required_argument,0,OPT_F0},{"fmt1",required_argument,0,OPT_F1},
    {"fmt2",required_argument,0,OPT_F2},{"nca",required_argument,0,OPT_NCA},{0,0,0,0}
};

int main(int argc, char *argv[]) { @autoreleasepool {
    const char *output=NULL, *want_fn=NULL;
    // GB default: color0/1 = RGBA16Float(115), color2 = R32Float(55)
    NSUInteger f0=115, f1=115, f2=55, nca=3; int c;
    while ((c=getopt_long(argc,argv,"o:f:",L,NULL))>0){ switch(c){
        case 'o': output=optarg; break; case 'f': want_fn=optarg; break;
        case OPT_F0: f0=strtoul(optarg,0,0); break; case OPT_F1: f1=strtoul(optarg,0,0); break;
        case OPT_F2: f2=strtoul(optarg,0,0); break; case OPT_NCA: nca=strtoul(optarg,0,0); break;
        default: die("bad args",nil); } }
    if(!output||optind>=argc) die("usage: -o out.bin -f fn src.metal",nil);

    NSError *err=nil;
    NSString *src=[NSString stringWithContentsOfFile:[NSString stringWithUTF8String:argv[optind]] encoding:NSUTF8StringEncoding error:&err];
    if(!src) die("read source",err);

    id<MTLDevice> dev=MTLCreateSystemDefaultDevice(); if(!dev) die("no device",nil);
    fprintf(stderr,"shdump_tile: device=%s\n",[[dev name] UTF8String]);
    MTLCompileOptions *opts=[MTLCompileOptions new];
    id<MTLLibrary> lib=[dev newLibraryWithSource:src options:opts error:&err];
    if(!lib) die("compile failed",err);

    id<MTLFunction> fn = want_fn ? [lib newFunctionWithName:[NSString stringWithUTF8String:want_fn]] : nil;
    if(!fn) die("function not found",nil);

    MTLTileRenderPipelineDescriptor *td=[MTLTileRenderPipelineDescriptor new];
    td.tileFunction=fn;
    td.threadgroupSizeMatchesTileSize=YES;
    NSUInteger fmts[3]={f0,f1,f2};
    for(NSUInteger i=0;i<nca;i++) td.colorAttachments[i].pixelFormat=(MTLPixelFormat)fmts[i];

    id<MTLRenderPipelineState> pso=[dev newRenderPipelineStateWithTileDescriptor:td options:0 reflection:nil error:&err];
    if(!pso) die("tile pipeline creation failed",err);
    fprintf(stderr,"shdump_tile: tile pipeline OK (nca=%lu, w=%lu)\n",(unsigned long)nca,(unsigned long)[pso maxTotalThreadsPerThreadgroup]);

    MTLBinaryArchiveDescriptor *ad=[MTLBinaryArchiveDescriptor new];
    id<MTLBinaryArchive> arc=[dev newBinaryArchiveWithDescriptor:ad error:&err];
    if(!arc) die("archive create",err);
    if(![arc addTileRenderPipelineFunctionsWithDescriptor:td error:&err]) die("addTileRenderPipelineFunctions",err);
    NSURL *url=[NSURL fileURLWithPath:[NSString stringWithUTF8String:output]];
    if(![arc serializeToURL:url error:&err]) die("serialize",err);
    fprintf(stderr,"shdump_tile: wrote %s\n",output);
    return 0;
} }
