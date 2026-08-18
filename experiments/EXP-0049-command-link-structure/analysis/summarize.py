#!/usr/bin/env python3
"""Regenerate concise EXP-0049 results from fixed raw run IDs and allowed BOs."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

HERE=Path(__file__).resolve().parents[1]
RAW=HERE/"raw"
MAIN=["m4-20260817-run01","m4-20260817-run02"]
REFINE=["m4-20260817-refine01","m4-20260817-refine02"]
POSITIVE=["cdm-direct","cdm-encoder1","cdm-pad7","vdm-state1","vdm-pad7"]
STOPPED=["cdm-indirect","vdm-stable","vdm-pass1"]
MAIN_MATRIX={
    "cdm-direct":("cdm",2048),"cdm-indirect":("cdm",2048),
    "cdm-encoder1":("cdm",2048),"cdm-pad7":("cdm",2048),
    "vdm-state1":("vdm",4096),"vdm-stable":("vdm",4096),
    "vdm-pass1":("vdm",4096),"vdm-pad7":("vdm",4096),
}
REFINE_MATRIX={"cdm-indirect":("cdm",2048),"vdm-stable":("vdm",4096),
               "vdm-pass1":("vdm",4096)}
ALLOWED={"va_100000b8000.bin","va_100000b8000.meta","va_10000158000.bin","va_10000158000.meta",
         "va_18000.bin","va_18000.meta","va_88000.bin","va_88000.meta"}
sys.path.insert(0,str(HERE/"analysis"))
from analyze_trial import vdm_draws  # authored, strict allowlisted helper

def sha(data:bytes)->str:return hashlib.sha256(data).hexdigest()

def load_json(path:Path):return json.loads(path.read_text())

def trial_dir(run:str,name:str)->Path:return RAW/run/"trials"/name

def parse_trials(run:str)->list[dict[str,object]]:
    rows=[]
    root=RAW/run/"trials"
    for expected_sequence,directory in enumerate(sorted(root.iterdir()),1):
        if directory.is_symlink() or not directory.is_dir():raise AssertionError(f"unsafe trial {directory}")
        match=re.fullmatch(r"(\d{3})_(.+)_(discover|repeat|approach|bisect)_n(\d{4})",directory.name)
        if not match or int(match[1])!=expected_sequence:raise AssertionError(f"trial name/sequence {directory}")
        rec=load_json(directory/"run.json");stdout=rec.get("stdout","")
        variants=re.findall(r"^VARIANT name=(\S+) engine=(\S+) count=(\d+) mutation=0$",stdout,re.M)
        if (re.findall(r"^DEVICE (.+)$",stdout,re.M)!=["Apple M4"] or len(variants)!=1 or
                re.findall(r"^COMMAND status=(\d+) error=(.*)$",stdout,re.M)!=[("4","none")] or
                re.findall(r"^RESULT ok=(\d+)$",stdout,re.M)!=["1"]):
            raise AssertionError(f"process output {directory}")
        variant,engine,count_text=variants[0];count=int(count_text)
        if (variant!=match[2] or match[3] not in {"discover","repeat","approach","bisect"} or
                count!=int(match[4])):raise AssertionError(f"trial identity {directory}")
        argv=rec.get("command")
        if (rec.get("exit")!=0 or rec.get("timeout",False) or rec.get("timeout_seconds")!=45 or
                not isinstance(argv,list) or len(argv)!=6 or Path(argv[0]).name!="probe" or
                argv[1:]!=["--variant",variant,"--count",count_text,"--dump"]):
            raise AssertionError(f"process command {directory}")
        state=directory/"state";entries=list(state.iterdir())
        if state.is_symlink() or any(p.is_symlink() or not p.is_file() for p in entries):
            raise AssertionError(f"unsafe state {directory}")
        captured=sorted(p.name for p in entries)
        if not set(captured)<=ALLOWED:raise AssertionError(f"state allowlist {directory}")
        source="va_100000b8000.bin" if engine=="cdm" else "va_18000.bin"
        target="va_10000158000.bin" if engine=="cdm" else "va_88000.bin"
        analysis_path=directory/"analysis.json"
        analysis=load_json(analysis_path) if analysis_path.exists() else None
        if analysis is not None and (analysis["trial"]!=directory.name or analysis["variant"]!=variant or
                                     analysis["engine"]!=engine or analysis["count"]!=count):
            raise AssertionError(f"trial analysis identity {directory}")
        rows.append({"directory":directory,"trial":directory.name,"variant":variant,"engine":engine,
                     "count":count,"phase":match[3],"captured":captured,"source_present":source in captured,
                     "target_present":target in captured,"analysis":analysis})
    return rows

def validate_main(run:str)->tuple[dict[str,object],list[dict[str,object]]]:
    rows=parse_trials(run);by_variant={name:[] for name in MAIN_MATRIX}
    for row in rows:
        if row["variant"] not in by_variant:raise AssertionError(f"unexpected main variant {row['variant']}")
        by_variant[row["variant"]].append(row)
    derived={}
    for variant,(engine,upper) in MAIN_MATRIX.items():
        group=by_variant[variant]
        if not group or any(row["engine"]!=engine for row in group):raise AssertionError(f"main engine {run}/{variant}")
        if [row["count"] for row in group[:2]]!=[1,upper] or any(row["phase"]!="discover" for row in group[:2]):
            raise AssertionError(f"main bracket {run}/{variant}")
        low_result,high_result=group[0]["analysis"],group[1]["analysis"]
        if low_result is None or low_result["known_link"]:raise AssertionError(f"main count1 {run}/{variant}")
        if high_result is None:
            if len(group)!=2 or not group[1]["target_present"]:raise AssertionError(f"main stop shape {run}/{variant}")
            derived[variant]={"status":"STOPPED","reason":"trial failure"}
            continue
        if not high_result["known_link"]:raise AssertionError(f"main upper link {run}/{variant}")
        low,high=1,upper;observations=[low_result,high_result]
        for row in group[2:-2]:
            middle=(low+high)//2
            if row["phase"]!="discover" or row["count"]!=middle or row["analysis"] is None:
                raise AssertionError(f"main bisection {run}/{variant}/{row['trial']}")
            observations.append(row["analysis"])
            if row["analysis"]["known_link"]:high=middle
            else:low=middle
        if high-low!=1 or len(group)<4:raise AssertionError(f"main boundary {run}/{variant}")
        repeat_low,repeat_high=group[-2:]
        if ([repeat_low["phase"],repeat_high["phase"]]!=["repeat","repeat"] or
                [repeat_low["count"],repeat_high["count"]]!=[low,high] or
                repeat_low["analysis"] is None or repeat_high["analysis"] is None or
                repeat_low["analysis"]["known_link"] or not repeat_high["analysis"]["known_link"]):
            raise AssertionError(f"main repeats {run}/{variant}")
        observations.extend((repeat_low["analysis"],repeat_high["analysis"]))
        ordered=sorted((x["count"],x["known_link"]) for x in observations)
        if any(link and any(not later for later_count,later in ordered if later_count>count)
               for count,link in ordered):raise AssertionError(f"main monotonicity {run}/{variant}")
        boundary_highs=[x for x in observations if x["count"]==high and x["known_link"]]
        if len(boundary_highs)!=2:raise AssertionError(f"main high repetitions {run}/{variant}")
        derived[variant]={"status":"PASS","engine":engine,"lower_no_link":low,
                          "first_known_link":high,"link_offsets":[x["link_offsets"] for x in boundary_highs],
                          "known_link_words":high_result["known_link_words"],"observations":observations}
    expected={"schema":1,"run_id":run,"scope":"local M4 only; structural correlations; no mutation; no A18 claim",
              "variants":derived}
    actual=load_json(RAW/run/"summary.json")
    if actual!=expected:raise AssertionError(f"raw main summary not derived from trials: {run}")
    return actual,rows

def validate_refinement(run:str)->tuple[dict[str,object],list[dict[str,object]]]:
    rows=parse_trials(run);by_variant={name:[] for name in REFINE_MATRIX}
    for row in rows:
        if row["variant"] not in by_variant:raise AssertionError(f"unexpected refinement variant {row['variant']}")
        by_variant[row["variant"]].append(row)
    derived={}
    for variant,(engine,upper) in REFINE_MATRIX.items():
        group=by_variant[variant];expected_count=1;observations=[]
        if not group or any(row["engine"]!=engine for row in group):raise AssertionError(f"refinement engine {run}/{variant}")
        for index,row in enumerate(group):
            if row["phase"]!="approach" or row["count"]!=expected_count:
                raise AssertionError(f"refinement approach {run}/{variant}/{row['trial']}")
            base={"trial":row["trial"],"variant":variant,"engine":engine,"count":row["count"],
                  "probe_exit":0,"source_present":row["source_present"],"target_present":row["target_present"],
                  "captured":row["captured"]}
            if not row["source_present"]:raise AssertionError(f"refinement source {run}/{variant}")
            if row["analysis"] is None:
                if index!=len(group)-1 or not row["target_present"]:
                    raise AssertionError(f"refinement unexplained stop {run}/{variant}")
                base["classification"]="TARGET_WITHOUT_EXACT_PAIR";observations.append(base);break
            if row["analysis"]["known_link"] or row["target_present"]:
                raise AssertionError(f"unexpected known refinement link {run}/{variant}")
            base.update(classification="NO_LINK",analysis=row["analysis"]);observations.append(base)
            if expected_count==upper:raise AssertionError(f"refinement upper without stop {run}/{variant}")
            expected_count=min(expected_count*2,upper)
        else:raise AssertionError(f"refinement missing stop {run}/{variant}")
        derived[variant]={"status":"STOPPED","reason":"TARGET_WITHOUT_EXACT_PAIR","observations":observations}
    expected={"schema":1,"run_id":run,"scope":"local M4 structural refinement; no mutation; no A18 claim",
              "variants":derived}
    actual=load_json(RAW/run/"summary.json")
    if actual!=expected:raise AssertionError(f"raw refinement summary not derived from trials: {run}")
    return actual,rows

def allowed_data(directory:Path,name:str)->bytes:
    state=directory/"state";actual={p.name for p in state.iterdir() if p.is_file()}
    if not actual<=ALLOWED:raise AssertionError(f"allowlist violation {directory}")
    p=state/name;m=p.with_suffix(".meta")
    fields=dict(line.split("=",1) for line in m.read_text().splitlines())
    if fields.get("fixed_allowlist")!="1" or fields.get("pointer_following")!="0" or fields.get("command_mutation")!="0":
        raise AssertionError(f"bad metadata {m}")
    data=p.read_bytes()
    if len(data)!=int(fields["read_size"],0) or len(data)>0x10000:raise AssertionError(f"size {p}")
    return data

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument("--json",type=Path,default=HERE/"analysis/summary.json");ap.add_argument("--report",type=Path,default=HERE/"analysis/report.txt");args=ap.parse_args()
    main_validated=[validate_main(r) for r in MAIN]
    refine_validated=[validate_refinement(r) for r in REFINE]
    mains=[item[0] for item in main_validated];refs=[item[0] for item in refine_validated]
    result={"schema":1,"scope":"local M4/G16G only; structural; no mutation; no A18 claim",
            "main_runs":MAIN,"refinement_runs":REFINE,"positive":{},"bounded_stops":{}}
    for variant in POSITIVE:
        rows=[]
        for summary in mains:
            v=summary["variants"][variant]
            if v["status"]!="PASS":raise AssertionError(f"unexpected stop {variant}")
            hits=[x for x in v["observations"] if x["count"]==v["first_known_link"] and x["known_link"]]
            lows=[x for x in v["observations"] if x["count"]==v["lower_no_link"] and not x["known_link"]]
            if len(hits)!=2 or len(lows)!=2:raise AssertionError(f"boundary repetition count {variant}")
            if len({(json.dumps(x["link_offsets"]),x["source"]["sha256"],x["target"]["sha256"]) for x in hits})!=1:
                raise AssertionError(f"boundary repetition bytes differ {variant}")
            rows.append({"lower_no_link":v["lower_no_link"],"first_known_link":v["first_known_link"],
                         "link_offsets":v["link_offsets"],"link_words":v["known_link_words"],
                         "source_sha256":hits[0]["source"]["sha256"],"target_sha256":hits[0]["target"]["sha256"]})
        if rows[0]!=rows[1]:raise AssertionError(f"run disagreement {variant}")
        result["positive"][variant]=rows[0]
    for variant in STOPPED:
        stops=[]
        for run,summary in zip(REFINE,refs):
            v=summary["variants"][variant]
            if v["status"]!="STOPPED" or v["reason"]!="TARGET_WITHOUT_EXACT_PAIR":
                raise AssertionError(f"unexpected refinement disposition {run}/{variant}")
            last=v["observations"][-1];d=trial_dir(run,last["trial"])
            source_name="va_100000b8000.bin" if last["engine"]=="cdm" else "va_18000.bin"
            target_name="va_10000158000.bin" if last["engine"]=="cdm" else "va_88000.bin"
            source=allowed_data(d,source_name);target=allowed_data(d,target_name)
            row={"stop_count":last["count"],"reason":v["reason"],"source_sha256":sha(source),
                 "target_sha256":sha(target)}
            if last["engine"]=="vdm":row.update(source_draw_packets=len(vdm_draws(source)),target_draw_packets=len(vdm_draws(target)))
            stops.append(row)
        if stops[0]!=stops[1]:raise AssertionError(f"refinement disagreement {variant}")
        result["bounded_stops"][variant]=stops[0]
    cdm_shape={(result["positive"][v]["lower_no_link"],result["positive"][v]["first_known_link"],
                json.dumps(result["positive"][v]["link_offsets"]),result["positive"][v]["source_sha256"],
                result["positive"][v]["target_sha256"]) for v in ("cdm-direct","cdm-encoder1","cdm-pad7")}
    vdm_shape={(result["positive"][v]["lower_no_link"],result["positive"][v]["first_known_link"],
                json.dumps(result["positive"][v]["link_offsets"]),result["positive"][v]["source_sha256"],
                result["positive"][v]["target_sha256"]) for v in ("vdm-state1","vdm-pad7")}
    if len(cdm_shape)!=1 or len(vdm_shape)!=1:raise AssertionError("matched-variant command bytes differ")
    # Stable VDM already leaves the preclassified source between the retained
    # 1024 and 2048 trials, even though no allowlisted target is captured there.
    stable_bounds=[]
    for summary in refs:
        obs=summary["variants"]["vdm-stable"]["observations"]
        a={x["count"]:x for x in obs}
        stable_bounds.append({"count_1024_source_draws":a[1024]["analysis"]["source_draw_packets"],
                              "count_2048_source_draws":a[2048]["analysis"]["source_draw_packets"]})
    if stable_bounds[0]!=stable_bounds[1]:raise AssertionError("stable bounds disagree")
    result["vdm_stable_source_bound"]=stable_bounds[0]
    # Verify every authored GPU process, including expected structural stops,
    # completed with status 4 and its target readback.
    processes=0
    for run,rows in zip(MAIN+REFINE,[item[1] for item in main_validated+refine_validated]):
        for row in rows:
            path=row["directory"]/"run.json"
            rec=load_json(path);stdout=rec.get("stdout","");processes+=1
            if rec.get("exit")!=0 or rec.get("timeout",False):raise AssertionError(f"GPU process failure {path}")
            if not re.search(r"^COMMAND status=4 error=none$",stdout,re.M) or not re.search(r"^RESULT ok=1$",stdout,re.M):
                raise AssertionError(f"bad status/readback {path}")
    result["gpu_processes"]={"count":processes,"nonzero_exit":0,"timeouts":0,"readback_failures":0}
    # Capture the authored client allocation movement from matched threshold repeats.
    addresses={}
    for variant in ("cdm-direct","cdm-pad7","vdm-state1","vdm-pad7"):
        observed=set()
        for _summary,rows in main_validated:
            for row in rows:
                if row["variant"]!=variant:continue
                stdout=load_json(row["directory"]/"run.json")["stdout"]
                m=re.search(r"^USER_VA output=(0x[0-9a-f]+) vertices=(0x[0-9a-f]+) render=(0x[0-9a-f]+) indirect=(0x[0-9a-f]+)$",stdout,re.M)
                if not m:raise AssertionError(f"addresses {variant}")
                observed.add(m.groups())
        if len(observed)!=1:raise AssertionError(f"client VA disagreement {variant}: {observed}")
        addresses[variant]={k:v for k,v in zip(("output","vertices","render","indirect"),observed.pop())}
    result["authored_client_addresses"]=addresses
    text=json.dumps(result,indent=2,sort_keys=True)+"\n"
    args.json.write_text(text)
    p=result["positive"];b=result["bounded_stops"]
    lines=[
      "EXP-0049 M4 command-link structural summary",
      "OBSERVATIONS",
      f"- {processes} authored GPU processes completed status 4 with exact target readback; no process timeout or GPU error.",
      f"- CDM direct: {p['cdm-direct']['lower_no_link']}/{p['cdm-direct']['first_known_link']} boundary, link offset {p['cdm-direct']['link_offsets'][0][0]}.",
      f"- CDM encoder-per-dispatch: identical boundary, link offset, and complete source/target hashes to direct.",
      f"- CDM pad7: identical boundary, link offset, and command hashes while authored output moved {addresses['cdm-direct']['output']}->{addresses['cdm-pad7']['output']}.",
      f"- VDM state-every-draw: {p['vdm-state1']['lower_no_link']}/{p['vdm-state1']['first_known_link']} boundary, link offset {p['vdm-state1']['link_offsets'][0][0]}.",
      f"- VDM pad7: identical boundary, link offset, and command hashes while authored vertices moved {addresses['vdm-state1']['vertices']}->{addresses['vdm-pad7']['vertices']}.",
      "",
      "BOUNDED STOPS",
      f"- CDM indirect: first retained known-target allocation at count {b['cdm-indirect']['stop_count']} lacks the exact EXP-0043 source pair in both refinements; threshold/address encoding UNKNOWN.",
      f"- VDM stable: the recognized direct-draw signature occurs 1024 times in the source at count 1024 and {result['vdm_stable_source_bound']['count_2048_source_draws']} times at count 2048. This is consistent with continuation or another record shape outside the recognized source sequence, but does not prove either. Known target at 4096 lacks the exact pair; threshold/destination UNKNOWN.",
      f"- VDM pass-per-draw: known target is allocated by count {b['vdm-pass1']['stop_count']}; the source has {b['vdm-pass1']['source_draw_packets']} recognized direct-draw signatures, the known target has none, and the exact pair is absent. Allocation is not promoted to a link or work-location proof.",
      "",
      "INTERPRETATION",
      "- DATA-TRACE-VALIDATED only for the repeated direct/state1 thresholds and unchanged command bytes under tested encoder/padding changes.",
      "- Link words remain STRUCTURAL. Changed-shape destinations, hardware consumption, arbitrary relocation, and A18 transfer remain UNKNOWN.",
    ]
    args.report.write_text("\n".join(lines)+"\n")
    print("\n".join(lines))
    return 0

if __name__=="__main__":raise SystemExit(main())
