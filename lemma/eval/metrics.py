import json

def contradiction_retention(report,ground_truth):
    caveats=ground_truth.get("inflated",[])+ground_truth.get("misread_figure",[])
    rt=json.dumps(report).lower()
    kept=0
    for c in caveats:
        kws=[w for w in c.lower().split() if len(w)>4][:3]
        if any(w in rt for w in kws):kept+=1
    return kept/max(len(caveats),1)

def narrative_evidence_separation(report):
    has_obj="object_conclusion" in report
    has_nar="narrative_conclusion" in report
    has_div="divergence" in report
    has_sup="top_support" in report and len(report.get("top_support",[]))>0
    has_ctr="top_counter" in report and len(report.get("top_counter",[]))>0
    has_unr="unresolved" in report and len(report.get("unresolved",[]))>0
    return (int(has_obj)+int(has_nar)+int(has_div)+int(has_sup)+int(has_ctr)+int(has_unr))/6

def prior_reuse_lift(steps1,steps2):
    if steps1==0:return 0
    return max(0,1-steps2/steps1)

def compression_faithfulness(original,compressed):
    if not original:return 1.0
    ct=json.dumps(compressed).lower()
    kept=sum(1 for c in original if any(w in ct for w in c.lower().split()[:3]))
    return kept/len(original)

def posterior_calibration(preds):
    if not preds:return 1.0
    err=sum((p.get("confidence",0.5)-(1 if p.get("correct") else 0))**2 for p in preds)
    return 1-err/len(preds)

def temporal_belief_quality(step_metrics,ground_truth):
    if not step_metrics:return 1.0
    gt_text=json.dumps(ground_truth).lower()
    scores=[]
    for sm in step_metrics:
        step=sm.get("step",0)
        conf=sm.get("branch_conf",0.5)
        status=sm.get("hyp_status","open")
        if status=="proved":
            gt_match=any(w in gt_text for w in ["partial","real","genuine"])
            scores.append(1.0 if gt_match else 0.3)
        elif status=="broken":
            gt_match=any(w in gt_text for w in ["inflated","excluded","misleading"])
            scores.append(1.0 if gt_match else 0.3)
        else:
            scores.append(0.5+0.2*(1-abs(0.5-conf)))
    return sum(scores)/len(scores) if scores else 1.0

def toolization_lift(step_metrics):
    if len(step_metrics)<4:return 0.0
    mid=len(step_metrics)//2
    early_times=[s["time"] for s in step_metrics[:mid] if "time" in s]
    late_times=[s["time"] for s in step_metrics[mid:] if "time" in s]
    if not early_times or not late_times:return 0.0
    early_avg=sum(early_times)/len(early_times)
    late_avg=sum(late_times)/len(late_times)
    if early_avg==0:return 0.0
    return max(0,1-late_avg/early_avg)

def tool_call_efficiency(step_metrics):
    if not step_metrics:return 0.0
    total_artifacts=sum(s.get("artifacts_found",0) for s in step_metrics)
    total_steps=len(step_metrics)
    return total_artifacts/max(total_steps,1)

def proof_repair_score(proof_repairs,step_metrics):
    if not proof_repairs:return 1.0
    repairs=len(proof_repairs)
    total_affected=sum(len(r.get("affected_branches",[])) for r in proof_repairs)
    reopened_ratio=total_affected/max(len(step_metrics),1)
    return max(0,1-reopened_ratio*0.5)

def score_report(report,world):
    gt=world["ground_truth"]
    s={"contradiction_retention":contradiction_retention(report,gt),
       "narrative_evidence_sep":narrative_evidence_separation(report),
       "calibration":posterior_calibration(report.get("predictions",[]))}
    step_metrics=report.get("_step_metrics",[])
    if step_metrics:
        s["temporal_belief"]=temporal_belief_quality(step_metrics,gt)
        s["toolization_lift"]=toolization_lift(step_metrics)
        s["tool_efficiency"]=tool_call_efficiency(step_metrics)
    s["overall"]=sum(s.values())/len(s)
    return s
